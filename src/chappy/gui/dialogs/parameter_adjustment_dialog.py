"""Modeless dialog to fine-tune absorber component parameters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from PySide6.QtCore import QSignalBlocker, QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from chappy.core.components.absorber import AbsorberComponent
from chappy.gui.dialog_sizing import enforce_translated_minimum_size
from chappy.gui.theme import Colors, Fonts, apply_action_row_sizing, apply_button_variant
from chappy.gui.visual_tokens import DialogMetrics
from chappy.i18n import get_language_switcher

if TYPE_CHECKING:
    from PySide6.QtGui import QCloseEvent

    from chappy.core.absorption.models import AbsorptionLine
    from chappy.core.components.base import Parameter

#: Measured against faithful ja/en renders: layout-driven minimum is ~874x306
#: (ja) / ~904x306 (en); this floor is a safety net below both.
_MINIMUM_SIZE_FLOOR: Final[QSize] = QSize(*DialogMetrics.MIN_SIZE_PARAMETER_ADJUSTMENT)
_SPIN_WIDTH_SAMPLE: Final[str] = "00.000000"


@dataclass(slots=True)
class _SliderConfig:
    """Configuration for translating floating point values to slider ticks."""

    minimum: float
    step: float
    maximum: float


@dataclass(slots=True)
class _ParameterControlGroup:
    """Bundle together widgets governed by a single fix checkbox."""

    slider: QSlider | None
    spin: QDoubleSpinBox
    fix_box: QCheckBox
    auxiliary: tuple[QWidget, ...] = ()


@dataclass(slots=True)
class _ParameterRowMeta:
    """Track widgets and source texts for a parameter grid row."""

    title_source: str
    tooltip_source: str
    name_label: QLabel
    slider: QSlider
    spin: QDoubleSpinBox


@dataclass(slots=True)
class _ParameterRowSpec:
    """Describe the static content and widgets of a single parameter row."""

    name: str
    title: str
    title_source: str
    tooltip: str
    tooltip_source: str
    slider: QSlider
    spin: QDoubleSpinBox
    fix_box: QCheckBox
    unit: str
    extra_widget: QWidget | None = None


class ParameterAdjustmentDialog(QDialog):
    """Provide non-blocking controls to tweak absorber parameters."""

    value_changed = Signal(AbsorberComponent, str, float)
    fix_toggled = Signal(AbsorberComponent, str, bool)
    dialog_closed = Signal()

    _LOGN_STEP: Final[float] = 0.01
    _B_STEP: Final[float] = 0.1
    _CF_STEP: Final[float] = 0.01
    _Z_SLIDER_RESOLUTION: Final[int] = 1000

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setWindowFlag(Qt.WindowType.Window, True)

        self._language_switcher = get_language_switcher(self)
        self._component: AbsorberComponent | None = None
        self._line: AbsorptionLine | None = None
        self._z_bounds: tuple[float, float] | None = None
        self._line_display_id: int | None = None
        self._component_index: int | None = None
        self._logn_slider_config: _SliderConfig | None = None
        self._b_slider_config: _SliderConfig | None = None
        self._cf_slider_config: _SliderConfig | None = None
        self._b_default_max: float = 0.0
        self._b_full_max: float = 0.0
        self._header_label: QLabel | None = None
        self._realtime_note_label: QLabel | None = None
        self._close_button: QPushButton | None = None
        self._parameter_rows: dict[str, _ParameterRowMeta] = {}

        self._logn_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._logn_spin = QDoubleSpinBox(self)
        self._logn_fix = QCheckBox(self)
        self._b_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._b_spin = QDoubleSpinBox(self)
        self._b_fix = QCheckBox(self)
        self._b_extend_checkbox = QCheckBox(self)

        self._z_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._z_spin = QDoubleSpinBox(self)
        self._z_fix = QCheckBox(self)

        self._cf_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._cf_spin = QDoubleSpinBox(self)
        self._cf_fix = QCheckBox(self)

        self._control_groups: dict[str, _ParameterControlGroup] = {}

        self._build_layout()
        self._connect_signals()
        self._language_switcher.language_changed.connect(self._on_language_changed)
        self._apply_translations()
        enforce_translated_minimum_size(self, floor=_MINIMUM_SIZE_FLOOR)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Emit lifecycle signal before closing."""
        self.dialog_closed.emit()
        super().closeEvent(event)

    def _build_layout(self) -> None:
        """Construct the dialog header, parameter grid, and footer."""
        self.setWindowTitle(self.tr("Adjust Absorber Parameters"))

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QLabel(self)
        header.setObjectName("parameterDialogHeader")
        header.setStyleSheet(
            f"font-weight: {Fonts.WEIGHT_BOLD}; "
            f"font-size: {Fonts.SIZE_MEDIUM}; "
            f"color: {Colors.TEXT_PRIMARY};"
        )
        self._header_label = header
        root.addWidget(header)

        root.addWidget(self._build_separator())
        root.addLayout(self._build_parameter_grid())

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(12)

        note_label = QLabel(self)
        note_label.setWordWrap(True)
        note_label.setObjectName("realtimeNote")
        note_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        self._realtime_note_label = note_label
        footer.addWidget(note_label, 1)

        close_button = QPushButton(self)
        close_button.setObjectName("closeButton")
        apply_button_variant(close_button, "secondary")
        apply_action_row_sizing(close_button)
        close_button.clicked.connect(self.close)
        self._close_button = close_button
        footer.addWidget(close_button)

        root.addLayout(footer)

    def _build_separator(self) -> QFrame:
        """Return a thin horizontal separator line."""
        line = QFrame(self)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setObjectName("sectionSeparator")
        return line

    def _spin_box_width(self) -> int:
        """Compute a fixed spin box width that fits the widest sample value."""
        metrics = QFontMetrics(self._logn_spin.font())
        text_width = metrics.horizontalAdvance(_SPIN_WIDTH_SAMPLE)
        option_frame = self._logn_spin.sizeHint().width() - metrics.horizontalAdvance("0")
        return text_width + option_frame

    def _build_parameter_grid(self) -> QGridLayout:
        """Create a row-per-parameter grid: name, slider, spin, unit, fix, extra."""
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(1, 1)

        spin_width = self._spin_box_width()
        for spin in (self._logn_spin, self._b_spin, self._z_spin, self._cf_spin):
            spin.setFixedWidth(spin_width)
            spin.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._add_parameter_row(
            grid,
            row=0,
            spec=_ParameterRowSpec(
                name="column_density",
                title=self.tr("logN (column density)"),
                title_source="logN (column density)",
                tooltip=self.tr(
                    "Logarithmic column density (log10 N/cm^2). "
                    "Adjust this to match the absorber strength."
                ),
                tooltip_source=(
                    "Logarithmic column density (log10 N/cm^2). "
                    "Adjust this to match the absorber strength."
                ),
                slider=self._logn_slider,
                spin=self._logn_spin,
                fix_box=self._logn_fix,
                unit="log(cm⁻²)",
            ),
        )
        self._register_control_group(
            "column_density",
            _ParameterControlGroup(
                slider=self._logn_slider, spin=self._logn_spin, fix_box=self._logn_fix
            ),
        )

        self._add_parameter_row(
            grid,
            row=1,
            spec=_ParameterRowSpec(
                name="b_parameter",
                title=self.tr("b (Doppler parameter)"),
                title_source="b (Doppler parameter)",
                tooltip=self.tr(
                    "Doppler broadening parameter in km/s. "
                    "Extend the range for highly turbulent absorbers."
                ),
                tooltip_source=(
                    "Doppler broadening parameter in km/s. "
                    "Extend the range for highly turbulent absorbers."
                ),
                slider=self._b_slider,
                spin=self._b_spin,
                fix_box=self._b_fix,
                unit="km/s",
                extra_widget=self._b_extend_checkbox,
            ),
        )
        self._register_control_group(
            "b_parameter",
            _ParameterControlGroup(
                slider=self._b_slider,
                spin=self._b_spin,
                fix_box=self._b_fix,
                auxiliary=(self._b_extend_checkbox,),
            ),
        )

        self._add_parameter_row(
            grid,
            row=2,
            spec=_ParameterRowSpec(
                name="redshift",
                title=self.tr("z (redshift)"),
                title_source="z (redshift)",
                tooltip=self.tr(
                    "Component redshift. Use the slider to stay within allowed bounds."
                ),
                tooltip_source=(
                    "Component redshift. Use the slider to stay within allowed bounds."
                ),
                slider=self._z_slider,
                spin=self._z_spin,
                fix_box=self._z_fix,
                unit="",
            ),
        )
        self._register_control_group(
            "redshift",
            _ParameterControlGroup(slider=self._z_slider, spin=self._z_spin, fix_box=self._z_fix),
        )

        self._add_parameter_row(
            grid,
            row=3,
            spec=_ParameterRowSpec(
                name="covering_factor",
                title=self.tr("Cf (covering factor)"),
                title_source="Cf (covering factor)",
                tooltip=self.tr("Fraction of the background light covered by the absorber (0-1)."),
                tooltip_source="Fraction of the background light covered by the absorber (0-1).",
                slider=self._cf_slider,
                spin=self._cf_spin,
                fix_box=self._cf_fix,
                unit="",
            ),
        )
        self._register_control_group(
            "covering_factor",
            _ParameterControlGroup(
                slider=self._cf_slider, spin=self._cf_spin, fix_box=self._cf_fix
            ),
        )

        return grid

    def _add_parameter_row(self, grid: QGridLayout, *, row: int, spec: _ParameterRowSpec) -> None:
        """Populate a single grid row for one adjustable parameter."""
        name_label = QLabel(spec.title, self)
        name_label.setObjectName("parameterName")
        tooltip_text = spec.tooltip
        name_label.setToolTip(tooltip_text)
        grid.addWidget(name_label, row, 0)

        slider = spec.slider
        slider.setTracking(True)
        slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        slider.setMinimumWidth(180)
        slider.setToolTip(tooltip_text)
        grid.addWidget(slider, row, 1)

        spec.spin.setToolTip(tooltip_text)
        grid.addWidget(spec.spin, row, 2)

        unit_label = QLabel(spec.unit, self)
        unit_label.setObjectName("parameterUnit")
        unit_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        grid.addWidget(unit_label, row, 3)

        spec.fix_box.setText(self.tr("Lock"))
        spec.fix_box.setToolTip(self.tr("Prevent the fitter from changing this parameter."))
        grid.addWidget(spec.fix_box, row, 4)

        if spec.extra_widget is not None:
            grid.addWidget(spec.extra_widget, row, 5)

        self._parameter_rows[spec.name] = _ParameterRowMeta(
            title_source=spec.title_source,
            tooltip_source=spec.tooltip_source,
            name_label=name_label,
            slider=slider,
            spin=spec.spin,
        )

    def _register_control_group(self, name: str, group: _ParameterControlGroup) -> None:
        """Track widgets affected by a parameter's fixed state."""
        self._control_groups[name] = group

    def _apply_translations(self) -> None:
        """Refresh all static strings to match the active language."""
        self.setWindowTitle(self.tr("Adjust Absorber Parameters"))

        if self._realtime_note_label is not None:
            self._realtime_note_label.setText(
                self.tr("Changes are applied to the model immediately.")
            )
        if self._close_button is not None:
            self._close_button.setText(self.tr("Close"))

        extend_text = self.tr("Extended range")
        extend_tip = self.tr(
            "Allow the Doppler parameter slider to use the full configured bounds."
        )
        self._b_extend_checkbox.setText(extend_text)
        self._b_extend_checkbox.setToolTip(extend_tip)

        fix_text = self.tr("Lock")
        fix_tip = self.tr("Prevent the fitter from changing this parameter.")
        for group in self._control_groups.values():
            group.fix_box.setText(fix_text)
            group.fix_box.setToolTip(fix_tip)

        for row in self._parameter_rows.values():
            title_text = self.tr(row.title_source)
            tooltip_text = self.tr(row.tooltip_source)
            row.name_label.setText(title_text)
            row.name_label.setToolTip(tooltip_text)
            row.slider.setToolTip(tooltip_text)
            row.spin.setToolTip(tooltip_text)

        self._refresh_header_label()

    def _apply_fix_state(self, name: str, fixed: bool) -> None:
        """Disable or enable widgets based on the parameter fixed flag."""
        group = self._control_groups.get(name)
        if group is None:
            return
        with QSignalBlocker(group.fix_box):
            group.fix_box.setChecked(fixed)
        if group.slider is not None:
            group.slider.setEnabled(not fixed)
        group.spin.setEnabled(not fixed)
        for widget in group.auxiliary:
            widget.setEnabled(not fixed)

    def _refresh_header_label(self) -> None:
        """Ensure the header text reflects the latest language and component state."""
        if self._header_label is None:
            return
        line_id_text = str(self._line_display_id) if self._line_display_id is not None else "-"
        component_text = str(self._component_index) if self._component_index is not None else "-"
        #: Placeholders {id} and {index} are formatted after translation.
        template = self.tr("Line {id} · Component {index}")
        summary = template.format(id=line_id_text, index=component_text)
        line_label = self._format_line_label(self._line)
        self._header_label.setText(f"{summary} — {line_label}")

    def _format_line_label(self, line: AbsorptionLine | None) -> str:
        """Return the translated description for the active absorption line."""
        if line:
            return f"{line.species} {line.rest_wavelength:.2f}Å"
        return self.tr("No associated line")

    def _on_language_changed(self, _code: str) -> None:
        """React to LanguageSwitcher updates by reapplying translations."""
        self._apply_translations()
        enforce_translated_minimum_size(self, floor=_MINIMUM_SIZE_FLOOR)

    def _on_fix_toggled(self, param_name: str, fixed: bool) -> None:
        """Apply UI updates then forward the fix event upstream."""
        self._apply_fix_state(param_name, fixed)
        self._emit_fix(param_name, fixed)

    def _connect_signals(self) -> None:
        self._logn_slider.valueChanged.connect(self._on_logn_slider_changed)
        self._logn_spin.valueChanged.connect(self._on_logn_spin_changed)
        self._logn_fix.toggled.connect(
            lambda checked: self._on_fix_toggled("column_density", checked)
        )

        self._b_slider.valueChanged.connect(self._on_b_slider_changed)
        self._b_spin.valueChanged.connect(self._on_b_spin_changed)
        self._b_fix.toggled.connect(lambda checked: self._on_fix_toggled("b_parameter", checked))
        self._b_extend_checkbox.toggled.connect(self._on_b_extend_toggled)

        self._z_slider.setRange(0, self._Z_SLIDER_RESOLUTION)
        self._z_slider.valueChanged.connect(self._on_z_slider_changed)
        self._z_spin.valueChanged.connect(self._on_z_spin_changed)
        self._z_fix.toggled.connect(lambda checked: self._on_fix_toggled("redshift", checked))

        self._cf_slider.valueChanged.connect(self._on_cf_slider_changed)
        self._cf_spin.valueChanged.connect(self._on_cf_spin_changed)
        self._cf_fix.toggled.connect(
            lambda checked: self._on_fix_toggled("covering_factor", checked)
        )

    def set_component(
        self,
        component: AbsorberComponent,
        *,
        line: AbsorptionLine | None,
        z_bounds: tuple[float, float] | None,
        line_display_id: int | None = None,
        component_index: int | None = None,
    ) -> None:
        """Populate controls with the provided component state."""
        self._component = component
        self._line = line
        self._z_bounds = z_bounds
        self._line_display_id = line_display_id
        self._component_index = component_index

        self._refresh_header_label()

        self._sync_parameter_controls("column_density", component.parameters.get("column_density"))
        self._sync_b_controls(component.parameters.get("b_parameter"))
        self._sync_redshift_controls(component.parameters.get("redshift"))
        self._sync_parameter_controls("covering_factor", component.parameters["covering_factor"])

    def _sync_parameter_controls(self, name: str, parameter: Parameter | None) -> None:
        if parameter is None:
            return

        if name == "column_density":
            self._logn_slider_config = _SliderConfig(
                parameter.min_val, self._LOGN_STEP, parameter.max_val
            )
            self._configure_slider(self._logn_slider, self._logn_slider_config)
            self._configure_spin(self._logn_spin, parameter, decimals=3, step=self._LOGN_STEP)
            self._update_numeric_controls(
                parameter.value, self._logn_slider, self._logn_spin, self._logn_slider_config
            )
            self._apply_fix_state("column_density", parameter.fixed)
            return

        if name == "covering_factor":
            self._cf_slider_config = _SliderConfig(
                parameter.min_val, self._CF_STEP, parameter.max_val
            )
            self._configure_slider(self._cf_slider, self._cf_slider_config)
            self._configure_spin(self._cf_spin, parameter, decimals=3, step=self._CF_STEP)
            self._update_numeric_controls(
                parameter.value, self._cf_slider, self._cf_spin, self._cf_slider_config
            )
            self._apply_fix_state("covering_factor", parameter.fixed)

    def _sync_b_controls(self, parameter: Parameter | None) -> None:
        if parameter is None:
            return

        self._b_default_max = min(50.0, float(parameter.max_val))
        self._b_full_max = float(parameter.max_val)
        self._b_slider_config = _SliderConfig(parameter.min_val, self._B_STEP, self._b_default_max)
        if parameter.value > self._b_default_max:
            self._b_extend_checkbox.setChecked(True)
        else:
            self._b_extend_checkbox.setChecked(False)
        self._configure_b_slider()
        self._configure_spin(self._b_spin, parameter, decimals=2, step=self._B_STEP)
        self._update_numeric_controls(
            parameter.value, self._b_slider, self._b_spin, self._b_slider_config
        )
        self._apply_fix_state("b_parameter", parameter.fixed)

    def _sync_redshift_controls(self, parameter: Parameter | None) -> None:
        if parameter is None:
            return

        self._configure_spin(self._z_spin, parameter, decimals=6, step=1e-4)
        self._apply_fix_state("redshift", parameter.fixed)

        bounds = self._z_bounds
        if bounds and bounds[1] > bounds[0]:
            self._z_slider.setEnabled(True)
            slider_value = self._value_to_z_slider(parameter.value)
            with QSignalBlocker(self._z_slider):
                self._z_slider.setValue(slider_value)
        else:
            self._z_slider.setEnabled(False)

        with QSignalBlocker(self._z_spin):
            self._z_spin.setValue(parameter.value)

    def _configure_slider(self, slider: QSlider, config: _SliderConfig | None) -> None:
        if config is None:
            slider.setEnabled(False)
            return
        slider.setEnabled(True)
        slider.setMinimum(0)
        steps = int(max(0, round((config.maximum - config.minimum) / config.step)))
        slider.setMaximum(steps)

    def _configure_spin(
        self, spin: QDoubleSpinBox, parameter: Parameter, *, decimals: int, step: float
    ) -> None:
        with QSignalBlocker(spin):
            spin.setDecimals(decimals)
            spin.setSingleStep(step)
            spin.setRange(parameter.min_val, parameter.max_val)

    def _configure_b_slider(self) -> None:
        if self._b_slider_config is None:
            return
        slider_max = (
            self._b_default_max if not self._b_extend_checkbox.isChecked() else self._b_full_max
        )
        self._b_slider_config = _SliderConfig(
            self._b_slider_config.minimum, self._b_slider_config.step, slider_max
        )
        self._configure_slider(self._b_slider, self._b_slider_config)

    def _update_numeric_controls(
        self, value: float, slider: QSlider, spin: QDoubleSpinBox, config: _SliderConfig | None
    ) -> None:
        with QSignalBlocker(spin):
            spin.setValue(value)
        if config is None:
            return
        slider_value = round((value - config.minimum) / config.step)
        slider_value = max(slider.minimum(), min(slider.maximum(), slider_value))
        with QSignalBlocker(slider):
            slider.setValue(slider_value)

    def _on_logn_slider_changed(self, slider_value: int) -> None:
        if self._logn_slider_config is None:
            return
        value = self._logn_slider_config.minimum + slider_value * self._logn_slider_config.step
        with QSignalBlocker(self._logn_spin):
            self._logn_spin.setValue(value)
        self._emit_value("column_density", value)

    def _on_logn_spin_changed(self, value: float) -> None:
        if self._logn_slider_config is None:
            self._emit_value("column_density", value)
            return
        slider_value = round(
            (value - self._logn_slider_config.minimum) / self._logn_slider_config.step
        )
        slider_value = max(
            self._logn_slider.minimum(), min(self._logn_slider.maximum(), slider_value)
        )
        with QSignalBlocker(self._logn_slider):
            self._logn_slider.setValue(slider_value)
        self._emit_value("column_density", value)

    def _on_b_slider_changed(self, slider_value: int) -> None:
        if self._b_slider_config is None:
            return
        value = self._b_slider_config.minimum + slider_value * self._b_slider_config.step
        with QSignalBlocker(self._b_spin):
            self._b_spin.setValue(value)
        self._emit_value("b_parameter", value)

    def _on_b_spin_changed(self, value: float) -> None:
        if self._b_slider_config is None:
            self._emit_value("b_parameter", value)
            return
        slider_value = round((value - self._b_slider_config.minimum) / self._b_slider_config.step)
        slider_value = max(self._b_slider.minimum(), min(self._b_slider.maximum(), slider_value))
        with QSignalBlocker(self._b_slider):
            self._b_slider.setValue(slider_value)
        self._emit_value("b_parameter", value)

    def _on_b_extend_toggled(self, _checked: bool) -> None:
        self._configure_b_slider()
        if self._component is None or self._b_slider_config is None:
            return
        current_value = self._component.parameters["b_parameter"].value
        self._update_numeric_controls(
            current_value, self._b_slider, self._b_spin, self._b_slider_config
        )

    def _on_z_slider_changed(self, slider_value: int) -> None:
        bounds = self._z_bounds
        if not bounds:
            return
        delta = bounds[1] - bounds[0]
        if delta <= 0:
            return
        ratio = slider_value / self._Z_SLIDER_RESOLUTION
        value = bounds[0] + delta * ratio
        with QSignalBlocker(self._z_spin):
            self._z_spin.setValue(value)
        self._emit_value("redshift", value)

    def _on_z_spin_changed(self, value: float) -> None:
        bounds = self._z_bounds
        if not bounds or bounds[1] <= bounds[0]:
            self._emit_value("redshift", value)
            return
        slider_value = self._value_to_z_slider(value)
        with QSignalBlocker(self._z_slider):
            self._z_slider.setValue(slider_value)
        self._emit_value("redshift", value)

    def _value_to_z_slider(self, value: float) -> int:
        bounds = self._z_bounds
        if not bounds or bounds[1] <= bounds[0]:
            return 0
        ratio = (value - bounds[0]) / (bounds[1] - bounds[0])
        slider_value = round(ratio * self._Z_SLIDER_RESOLUTION)
        return max(self._z_slider.minimum(), min(self._z_slider.maximum(), slider_value))

    def _on_cf_slider_changed(self, slider_value: int) -> None:
        if self._cf_slider_config is None:
            return
        value = self._cf_slider_config.minimum + slider_value * self._cf_slider_config.step
        with QSignalBlocker(self._cf_spin):
            self._cf_spin.setValue(value)
        self._emit_value("covering_factor", value)

    def _on_cf_spin_changed(self, value: float) -> None:
        if self._cf_slider_config is None:
            self._emit_value("covering_factor", value)
            return
        slider_value = round(
            (value - self._cf_slider_config.minimum) / self._cf_slider_config.step
        )
        slider_value = max(self._cf_slider.minimum(), min(self._cf_slider.maximum(), slider_value))
        with QSignalBlocker(self._cf_slider):
            self._cf_slider.setValue(slider_value)
        self._emit_value("covering_factor", value)

    def _emit_value(self, param_name: str, value: float) -> None:
        if self._component is None:
            return
        self.value_changed.emit(self._component, param_name, value)

    def _emit_fix(self, param_name: str, fixed: bool) -> None:
        if self._component is None:
            return
        self.fix_toggled.emit(self._component, param_name, fixed)

    def refresh(self) -> None:
        """Re-synchronise widgets from the current component state."""
        if self._component is None:
            return
        self.set_component(
            self._component,
            line=self._line,
            z_bounds=self._z_bounds,
            line_display_id=self._line_display_id,
            component_index=self._component_index,
        )
