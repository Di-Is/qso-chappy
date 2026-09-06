"""Manifest-driven documentation pipeline."""

from __future__ import annotations

import os
import sys
import tempfile
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import PySide6.QtCore
from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication, QSettings, Qt
from PySide6.QtWidgets import QCheckBox

from chappy.core.editing_mode import EditingMode
from chappy.gui.modes.analysis.overview.panel import StructureSidePanel
from chappy.gui.modes.identify.presets.preset_store import IdentifyPresetStore
from chappy.gui.protocols.intent_types import ToggleVelocityPlotIntent
from chappy.gui.shell.composition import create_main_window
from chappy.gui.shell.dependencies import ShellDependencies
from chappy.gui.shell.main_window import MainWindow
from chappy.infrastructure.composition import create_default_infrastructure_dependencies
from chappy.presentation.velocity import VelocitySliceInfo, build_velocity_view_data
from chappy_user_manual_generator.annotations import apply_doc_annotations
from chappy_user_manual_generator.dialog_providers import DialogProvider, known_dialog_providers
from chappy_user_manual_generator.exporter import (
    CustomCaptureSpec,
    DocExportConfig,
    export_window_docs,
)
from chappy_user_manual_generator.fixtures import apply_fixture
from chappy_user_manual_generator.glossary import export_glossary
from chappy_user_manual_generator.html_exporter import convert_markdown_tree
from chappy_user_manual_generator.line_database_guide import export_line_database_guide
from chappy_user_manual_generator.markdown import format_markdown_text
from chappy_user_manual_generator.menu_exporter import (
    MenuDocConfig,
    MenuDocResult,
    export_menu_docs,
)
from chappy_user_manual_generator.menu_metadata import menu_action_metadata
from chappy_user_manual_generator.models import (
    CaptureDestination,
    DocManifest,
    MenuDocSpec,
    OperationFlow,
    OperationScenarioSpec,
    PanelDestination,
    ScenarioContext,
    ScreenDocSpec,
)
from chappy_user_manual_generator.panel_windows import AnalysisStructureDocWindow
from chappy_user_manual_generator.single_page import write_single_page_manual
from chappy_user_manual_generator.templates import mode_label_map
from chappy_user_manual_generator.translations import translate_manual_text
from chappy_user_manual_generator.tutorial_guide import export_tutorial_guide

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import ModuleType

    from PySide6.QtWidgets import QApplication

    type ScenarioWindow = MainWindow | AnalysisStructureDocWindow


DOC_AUTO_DISCARD_ENV_NAMES: tuple[str, ...] = ("CHAPPY_DOC_AUTO_DISCARD",)
DOC_HEADLESS_ENV_NAMES: tuple[str, ...] = ("CHAPPY_DOC_HEADLESS",)

_EXPORTER_CONTEXT = "ManualExporter"

# Representative detection threshold used for every Identify mode capture so
# screenshots do not depend on a developer's locally saved sigma value (F-02).
IDENTIFY_DOC_SIGMA_THRESHOLD = 5.0
_IDENTIFY_SIGMA_SETTINGS_KEY = "identify_panel/sigma_threshold"
_IDENTIFY_DOC_VELOCITY_WAVELENGTH = 1548.19 * (1.0 + 1.302)


@dataclass(slots=True)
class RuntimeOptions:
    """Common runtime options shared by manifest exports."""

    out_dir: Path
    html_out_dir: Path | None
    version: str
    scale_width: int
    show_internal_id: bool
    language: str | None = None
    headless: bool = False


def run_manifest(app: QApplication, manifest: DocManifest, options: RuntimeOptions) -> None:
    """Execute all manifest entries."""
    with _doc_environment(options.headless):
        for screen in manifest.screens:
            _run_screen_spec(app, screen, options)

        for flow_spec in manifest.flows:
            _run_flow_spec(app, flow_spec, options)

        for menu_spec in manifest.menus:
            _run_menu_spec(app, menu_spec, options)

        # 先に用語集を生成（JA/EN）
        glossary_dir = options.out_dir / "glossary"
        export_glossary(out_dir=glossary_dir, version=options.version)

        export_line_database_guide(out_dir=options.out_dir / "reference")
        export_tutorial_guide(out_dir=options.out_dir / "reference")

        if manifest.index is not None:
            write_single_page_manual(
                manifest.index, out_dir=options.out_dir, version=options.version
            )

    if options.html_out_dir is not None:
        convert_markdown_tree(options.out_dir, options.html_out_dir, language=options.language)


def _run_screen_spec(app: QApplication, spec: ScreenDocSpec, options: RuntimeOptions) -> None:
    window = _create_window(spec.window_type, headless=options.headless)
    with suppress(AttributeError):
        window.resize(max(options.scale_width, 640), 800)
    window.show()
    app.processEvents()

    for fixture_name in spec.fixtures:
        apply_fixture(fixture_name, app, window)
        app.processEvents()

    # ドキュメント専用メタデータの注入（UIコードから分離）
    apply_doc_annotations(window)

    include_tabs = spec.include_tabs

    target_root = options.out_dir / (spec.output_subdir or spec.slug)

    if spec.include_common:
        _prepare_destination(window, CaptureDestination(EditingMode.ANALYSIS))
        app.processEvents()
        apply_doc_annotations(window)

        common_dir = target_root / "common"
        common_config = DocExportConfig(
            out_dir=common_dir,
            version=options.version,
            include_tabs=include_tabs,
            scale_width=options.scale_width,
            include_scopes={"common"},
            include_unscoped=False,
            show_internal_widget_name=options.show_internal_id,
        )
        export_window_docs(window, common_config)

    for destination in spec.destinations:
        fixtures_applied = _apply_destination_fixtures(app, window, spec, destination)
        if fixtures_applied:
            app.processEvents()

        _prepare_destination(window, destination)
        app.processEvents()
        apply_doc_annotations(window)

        target_dir = target_root / f"mode_{destination.scope}"
        custom_captures: list[CustomCaptureSpec] = []
        if destination.mode is EditingMode.IDENTIFY:
            custom_captures = _identify_custom_captures(window, app)
        config = DocExportConfig(
            out_dir=target_dir,
            version=options.version,
            include_tabs=include_tabs,
            scale_width=options.scale_width,
            include_scopes={destination.scope},
            include_unscoped=True,
            exclude_scopes={"common"},
            show_internal_widget_name=options.show_internal_id,
            custom_captures=custom_captures,
        )
        export_window_docs(window, config)

    window.close()
    app.processEvents()


def _run_flow_spec(
    app: QApplication, spec: OperationScenarioSpec, options: RuntimeOptions
) -> None:
    window = _create_window(spec.window_type, headless=options.headless)
    with suppress(AttributeError):
        window.resize(max(options.scale_width, 640), 800)
    window.show()
    app.processEvents()

    for fixture_name in spec.fixtures:
        apply_fixture(fixture_name, app, window)
        app.processEvents()

    if spec.destination is not None:
        _prepare_destination(window, spec.destination)
        app.processEvents()

    context = ScenarioContext(
        slug=spec.slug,
        title=spec.title,
        summary=spec.summary,
        window=window,
        app=app,
        window_type=spec.window_type,
        fixtures=spec.fixtures,
        destination=spec.destination,
        output_filename=f"{spec.slug}.md",
    )

    flow = spec.scenario(context)
    if flow is None:
        flow = context.build_flow()
    if not isinstance(flow, OperationFlow):
        msg = f"Scenario {spec.slug} returned unsupported result: {type(flow)!r}"
        raise TypeError(msg)
    if not flow.steps and not flow.sections:
        msg = f"Scenario {spec.slug} produced no content."
        raise ValueError(msg)

    _write_operation_flow(
        flow, base_dir=options.out_dir / spec.output_dir, version=options.version
    )

    window.close()
    app.processEvents()


def _identify_custom_captures(window: MainWindow, app: QApplication) -> list[CustomCaptureSpec]:
    def show_velocity_plot(target_window: MainWindow) -> None:
        target_window.identify_velocity_runtime.handle_identify_intent(
            ToggleVelocityPlotIntent(wavelength=_IDENTIFY_DOC_VELOCITY_WAVELENGTH)
        )
        app.processEvents()

        spectrum_view = getattr(target_window.view_stack, "spectrum_view", None)
        velocity_view = getattr(spectrum_view, "_velocity_view", None) if spectrum_view else None
        if velocity_view is None:
            return

        slices = list(getattr(velocity_view, "_slice_meta", []))
        if not slices:
            slices.append(
                VelocitySliceInfo(
                    rest_wavelength=1548.19,
                    label="Demo baseline",
                    tie_group_key="",
                    center_z=2.0,
                    line_id="doc_demo_0",
                    is_primary=True,
                    default_selected=True,
                    selected=True,
                    analysis_half_width_kms=200.0,
                )
            )

        while len(slices) < 8:
            index = len(slices) + 1
            slices.append(
                VelocitySliceInfo(
                    rest_wavelength=1548.19 + index,
                    label=f"Demo slice {index}",
                    tie_group_key="",
                    center_z=2.0,
                    line_id=f"doc_demo_{index}",
                    is_primary=False,
                    default_selected=False,
                    selected=False,
                    analysis_half_width_kms=200.0,
                )
            )

        velocity_view.apply_view_data(
            build_velocity_view_data(
                target_window.current_project,
                slices,
                display_half_width_kms=velocity_view.display_half_width.value,
                include_optimize_overlays=False,
            )
        )
        velocity_view.refresh_plot()
        with suppress(AttributeError):
            velocity_view._set_page(0)

        limit_velocity_annotations(target_window)

    def hide_velocity_plot(target_window: MainWindow) -> None:
        target_window.identify_velocity_runtime.hide_velocity_plot()
        app.processEvents()

    def limit_velocity_annotations(target_window: MainWindow) -> None:
        spectrum_view = getattr(target_window.view_stack, "spectrum_view", None)
        velocity_view = getattr(spectrum_view, "_velocity_view", None) if spectrum_view else None
        if velocity_view is None:
            return

        for index, subplot in enumerate(getattr(velocity_view, "_subplot_widgets", [])):
            include = index == 0
            subplot.setProperty("doc.include", include)
            checkbox = subplot.findChild(QCheckBox, "velocitySubplotSelection")
            if checkbox is not None:
                checkbox.setProperty("doc.include", include)
            if include:
                subplot.setProperty(
                    "doc.label",
                    translate_manual_text(
                        _EXPORTER_CONTEXT,
                        QT_TRANSLATE_NOOP("ManualExporter", "Representative subplot"),
                    ),
                )
                subplot.setProperty(
                    "doc.desc",
                    translate_manual_text(
                        _EXPORTER_CONTEXT,
                        QT_TRANSLATE_NOOP(
                            "ManualExporter",
                            "Highlights a sample subplot. Dashed boundaries show the New-candidate analysis range, while Display range controls only the shared view range.",
                        ),
                    ),
                )
                subplot.setProperty("doc.section", "identify_velocity")
            else:
                subplot.setProperty("doc.label", None)
                subplot.setProperty("doc.desc", None)
                subplot.setProperty("doc.section", None)

    window.setProperty("doc.captureProfile", "identify")

    # No section filter: the overview shows every identify-scope widget, so the
    # later unfiltered default capture dedupes against it instead of duplicating.
    return [
        CustomCaptureSpec(
            suffix="_overview",
            label_source=QT_TRANSLATE_NOOP("ManualExporter", "Identify Mode Overview"),
            position="before",
        ),
        CustomCaptureSpec(
            section="identify_velocity",
            suffix="_velocity",
            label_source=QT_TRANSLATE_NOOP("ManualExporter", "Identify Velocity Plot controls"),
            position="after",
            pre_capture=show_velocity_plot,
            post_capture=hide_velocity_plot,
            post_annotation=limit_velocity_annotations,
        ),
    ]


def _run_menu_spec(
    app: QApplication, spec: MenuDocSpec, options: RuntimeOptions
) -> MenuDocResult | None:
    window = _create_window(spec.window_type, headless=options.headless)
    with suppress(AttributeError):
        window.resize(max(options.scale_width, 640), 800)
    window.show()
    app.processEvents()

    for fixture_name in spec.fixtures:
        apply_fixture(fixture_name, app, window)
        app.processEvents()

    target_root = options.out_dir / (spec.output_subdir or spec.slug)
    providers_by_slug = known_dialog_providers()
    action_meta = menu_action_metadata()
    action_dialog_providers: dict[str, tuple[DialogProvider, ...]] = {}
    for key, meta in action_meta.items():
        providers: list[DialogProvider] = []
        if meta.dialog_slug:
            provider = providers_by_slug.get(meta.dialog_slug)
            if provider is not None:
                providers.append(provider)
        for slug in meta.extra_dialog_slugs:
            provider = providers_by_slug.get(slug)
            if provider is not None:
                providers.append(provider)
        if providers:
            action_dialog_providers[key] = tuple(providers)

    config = MenuDocConfig(
        out_dir=target_root,
        version=options.version,
        include_shortcuts=spec.include_shortcuts,
        include_modes=spec.include_modes,
        include_status=spec.include_status,
        mode_labels=mode_label_map(),
        # 参照されないページは生成しない
        overview_filename=None,
        write_individual_pages=False,
        include_screenshot=True,
        screenshot_scale_width=min(800, max(480, options.scale_width // 2)),
        dialog_output_subdir="dialogs",
        dialog_providers=action_dialog_providers,
    )

    try:
        result = export_menu_docs(window, spec, config)
    except Exception:
        window.close()
        app.processEvents()
        raise

    window.close()
    app.processEvents()
    return result


def _create_window(window_type: str, *, headless: bool) -> ScenarioWindow:
    window: ScenarioWindow
    if window_type == "analysis-structure-panel":
        window = AnalysisStructureDocWindow()
    else:
        # Isolate preset persistence so local user presets never leak into the
        # manual and scenario edits never touch the real ~/.chappy/presets.json.
        doc_preset_path = Path(tempfile.mkdtemp(prefix="chappy-doc-presets-")) / "presets.json"
        dependencies = create_default_infrastructure_dependencies(
            translate_presets=str, preset_storage_path=doc_preset_path
        )
        window = create_main_window(
            ShellDependencies(
                project_io_usecase=dependencies.project_io_usecase,
                atomic_data=dependencies.atomic_repository,
                preset_store=IdentifyPresetStore(dependencies.preset_store),
                optimize_model_addition_usecase=dependencies.optimize_model_addition_usecase,
            )
        )

    if headless:
        with suppress(AttributeError):
            window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    return window


def _switch_mode(window: ScenarioWindow, mode: EditingMode) -> None:
    switcher = getattr(window, "switch_mode", None)
    coordinator = getattr(window, "mode_shell_coordinator", None)
    if callable(switcher):
        switcher(mode)
        return
    if coordinator is not None and hasattr(coordinator, "switch_mode"):
        coordinator.switch_mode(mode)


def _prepare_destination(window: ScenarioWindow, destination: CaptureDestination) -> None:
    """Prepare the requested mode, Analysis surface, and nested panel."""
    _switch_mode(window, destination.mode)
    if not isinstance(window, MainWindow) or destination.mode is not EditingMode.ANALYSIS:
        return

    if destination.panel is PanelDestination.ANALYSIS_REGION_DETAIL:
        region_id = _first_analysis_region_id(window)
        if region_id is None or not window.open_analysis_region(region_id):
            msg = "Analysis Region Detail capture requires an analysis-capable region."
            raise RuntimeError(msg)
        return

    window.back_to_analysis_overview()
    panel = window.findChild(StructureSidePanel, "structureSidePanel")
    if panel is not None:
        panel.set_structure_editor_visible(
            destination.panel is PanelDestination.ANALYSIS_STRUCTURE
        )
    if destination.panel is PanelDestination.ANALYSIS_STRUCTURE:
        if panel is None or not window.open_analysis_structure():
            msg = "Analysis Structure capture requires the Overview structure panel."
            raise RuntimeError(msg)
        region_id = _first_analysis_region_id(window)
        if region_id is not None:
            panel.restore_selection((region_id,), ())


def _first_analysis_region_id(window: MainWindow) -> str | None:
    project = window.current_project
    if project is None:
        return None
    return next(
        (
            region_id
            for region_id in project.absorption_regions
            if project.is_region_analysis_capable(region_id)
        ),
        None,
    )


def _apply_destination_fixtures(
    app: QApplication, window: ScenarioWindow, spec: ScreenDocSpec, destination: CaptureDestination
) -> bool:
    if not isinstance(window, MainWindow):
        return False

    fixtures_to_apply: tuple[str, ...] | None = spec.destination_fixtures.get(destination)

    if fixtures_to_apply is None:
        if destination.mode is EditingMode.START:
            return False
        fixtures_to_apply = spec.fixtures

    if not fixtures_to_apply:
        return False

    for fixture_name in fixtures_to_apply:
        apply_fixture(fixture_name, app, window)

    return True


def _write_operation_flow(flow: OperationFlow, *, base_dir: Path, version: str) -> None:
    _ = version  # version is surfaced at manual index level (per-page表示なし)
    base_dir.mkdir(parents=True, exist_ok=True)
    filename = flow.output_filename or f"{flow.slug}.md"
    target = base_dir / filename

    prereq_heading = translate_manual_text(
        _EXPORTER_CONTEXT, QT_TRANSLATE_NOOP("ManualExporter", "Prerequisites")
    )
    steps_heading = translate_manual_text(
        _EXPORTER_CONTEXT, QT_TRANSLATE_NOOP("ManualExporter", "Procedure")
    )
    notes_heading = translate_manual_text(
        _EXPORTER_CONTEXT, QT_TRANSLATE_NOOP("ManualExporter", "Tips and Best Practices")
    )
    related_heading = translate_manual_text(
        _EXPORTER_CONTEXT, QT_TRANSLATE_NOOP("ManualExporter", "Related References")
    )

    lines = [f"# {flow.title}"]

    if flow.summary:
        lines.extend(["", flow.summary])

    if flow.prerequisites:
        lines.extend(["", f"## {prereq_heading}", ""])
        lines.extend(f"- {item}" for item in flow.prerequisites)

    if flow.sections:
        for section in flow.sections:
            lines.extend(["", f"## {section.heading}", ""])
            if section.description:
                lines.append(section.description)
                lines.append("")
            if section.items:
                for item in section.items:
                    line = f"- **{item.title}** — {item.description}"
                    lines.append(line)
                    lines.extend(f"  - {detail}" for detail in item.details)
                lines.append("")
            if section.blocks:
                for block in section.blocks:
                    lines.extend([block.content, ""])

        if lines and lines[-1] == "":
            lines.pop()

    if flow.steps:
        steps_header = translate_manual_text(
            _EXPORTER_CONTEXT,
            QT_TRANSLATE_NOOP("ManualExporter", "| Step | Action | Expected Result |"),
        )
        lines.extend(["", f"## {steps_heading}", "", steps_header, "| --- | --- | --- |"])

        lines.extend(f"| {step.order} | {step.action} | {step.expected} |" for step in flow.steps)

    if flow.notes:
        lines.extend(["", f"## {notes_heading}", ""])
        lines.extend(f"- {note}" for note in flow.notes)

    if flow.related_links:
        lines.extend(["", f"## {related_heading}", ""])
        lines.extend(f"- [{link.label}]({link.path})" for link in flow.related_links)

    lines.append("")
    formatted_flow = format_markdown_text("\n".join(lines))
    if not formatted_flow.endswith("\n"):
        formatted_flow += "\n"
    target.write_text(formatted_flow, encoding="utf-8")


@contextmanager
def _doc_environment(headless: bool) -> Iterator[None]:
    prev_auto_discard = {name: os.environ.get(name) for name in DOC_AUTO_DISCARD_ENV_NAMES}
    prev_headless_flag = {name: os.environ.get(name) for name in DOC_HEADLESS_ENV_NAMES}
    try:
        if headless:
            for name in DOC_AUTO_DISCARD_ENV_NAMES:
                os.environ[name] = "1"
            for name in DOC_HEADLESS_ENV_NAMES:
                os.environ[name] = "1"
        with _isolated_qsettings():
            yield
    finally:
        if headless:
            for name, previous in prev_auto_discard.items():
                _restore_env_var(name, previous)
            for name, previous in prev_headless_flag.items():
                _restore_env_var(name, previous)


def _restore_env_var(key: str, previous: str | None) -> None:
    if previous is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = previous


class _IsolatedQSettings(QSettings):
    """``QSettings`` subclass that always resolves to an isolated ``IniFormat`` store.

    ``QSettings(organization, application)`` — the two-argument form used
    throughout ``chappy`` — is hardcoded to ``QSettings::NativeFormat`` and
    ignores ``QSettings.setDefaultFormat()``/``setPath()`` entirely (verified
    against PySide6: calling ``setDefaultFormat(IniFormat)`` beforehand still
    reports ``format() == NativeFormat`` for this constructor form). On macOS,
    NativeFormat is backed by the system preferences daemon keyed to the real
    login session, so it also ignores ``$HOME``/``$XDG_CONFIG_HOME`` overrides
    for actual reads/writes. The only override Qt honours is requesting
    ``IniFormat`` explicitly via the four-argument constructor, combined with
    ``QSettings.setPath(IniFormat, ...)`` to pick the directory.

    Only the two constructor forms actually used in ``chappy`` are supported:
    zero-argument (falls back to the app's organization/application name) and
    the two-argument ``(organization, application)`` form.
    """

    def __init__(self, organization: str | None = None, application: str | None = None) -> None:
        resolved_organization = organization or QCoreApplication.organizationName()
        resolved_application = application or QCoreApplication.applicationName()
        super().__init__(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            resolved_organization,
            resolved_application,
        )


def _bind_isolated_qsettings() -> list[ModuleType]:
    """Rebind every already-imported module's ``QSettings`` name to the isolated subclass.

    ``from PySide6.QtCore import QSettings`` binds the name into each
    importing module's own namespace, so patching ``PySide6.QtCore.QSettings``
    alone does not affect modules imported before this call. Patching
    ``PySide6.QtCore.QSettings`` in addition covers modules imported for the
    first time later in the same doc run (e.g. a mode not yet constructed).
    """
    PySide6.QtCore.QSettings = _IsolatedQSettings
    patched_modules: list[ModuleType] = []
    for module in list(sys.modules.values()):
        if module is None:
            continue
        try:
            attribute = getattr(module, "QSettings", None)
        except Exception:  # noqa: BLE001, S112 - defensive against exotic module __getattr__
            continue
        if attribute is QSettings:
            module.QSettings = _IsolatedQSettings  # type: ignore[attr-defined]
            patched_modules.append(module)
    return patched_modules


def _unbind_isolated_qsettings(patched_modules: list[ModuleType]) -> None:
    PySide6.QtCore.QSettings = QSettings
    for module in patched_modules:
        module.QSettings = QSettings  # type: ignore[attr-defined]


@contextmanager
def _isolated_qsettings() -> Iterator[None]:
    """Redirect every ``QSettings`` store to a throwaway directory for a doc run.

    Without this isolation, a developer's real tab index, splitter
    positions, collapsed sections, and detection threshold leak into
    generated screenshots, so the same commit produces different manuals
    depending on who runs the generator (F-02).
    """
    settings_home = Path(tempfile.mkdtemp(prefix="chappy-doc-settings-"))
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(settings_home))
    patched_modules = _bind_isolated_qsettings()
    try:
        settings = _IsolatedQSettings("Chappy", "Chappy")
        settings.setValue(_IDENTIFY_SIGMA_SETTINGS_KEY, IDENTIFY_DOC_SIGMA_THRESHOLD)
        settings.sync()
        yield
    finally:
        _unbind_isolated_qsettings(patched_modules)
