"""Reusable UI documentation fixtures."""

from __future__ import annotations

import logging
import math
import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtWidgets import QApplication

from chappy.core.constants import LIGHT_SPEED_KMS
from chappy.core.editing_mode import EditingMode
from chappy.core.identify_state import TemporaryLineContext
from chappy.core.spectroscopy_project import SpectroscopyProject
from chappy.core.spectrum import Spectrum
from chappy.gui.shell.main_window import MainWindow

if TYPE_CHECKING:
    from chappy.core.absorption import AbsorptionLine, AbsorptionRegion

# Type alias for fixture callbacks
FixtureCallable = Callable[[QApplication, MainWindow], None]

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FixtureDefinition:
    """Metadata for available documentation fixtures."""

    name: str
    apply: FixtureCallable
    description: str
    scopes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _LineSpec:
    species: str
    transition_name: str
    rest_wavelength: float
    center_z: float
    window_kms: float
    multiplet_label: str
    oscillator_strength: float
    gamma_value: float


def available_fixture_names() -> Iterable[str]:
    """Return available fixture identifiers."""
    return tuple(_FIXTURE_MAP)


def get_fixture(name: str) -> FixtureDefinition:
    """Return a fixture definition by name."""
    try:
        return _FIXTURE_MAP[name]
    except KeyError as exc:  # pragma: no cover - defensive
        msg = f"Unknown documentation fixture: {name}"
        raise ValueError(msg) from exc


def apply_fixture(name: str, app: QApplication, window: MainWindow) -> None:
    """Apply a named fixture to the provided window."""
    fixture = get_fixture(name)
    fixture.apply(app, window)


def _apply_analysis_demo_fixture(app: QApplication, window: MainWindow) -> None:
    """Populate the main window with Analysis Overview and Detail demo data."""
    debug_flag = os.environ.get("CHAPPY_DOC_DEBUG")
    project = create_analysis_demo_project(debug=debug_flag is not None)
    window.set_current_project(project)

    coordinator = getattr(window, "mode_shell_coordinator", None)
    if coordinator is not None:
        coordinator.switch_mode(EditingMode.ANALYSIS)
    else:
        mode_state_store = getattr(window, "mode_state_store", None)
        if (
            mode_state_store is not None
            and getattr(mode_state_store, "current_mode", None) != EditingMode.ANALYSIS
        ):
            mode_state_store.switch_mode(EditingMode.ANALYSIS)

    app.processEvents()


def _create_line(  # noqa: PLR0913
    project: SpectroscopyProject,
    region: AbsorptionRegion | None = None,
    *,
    species: str,
    transition_name: str,
    rest_wavelength: float,
    center_z: float,
    window_kms: float,
    multiplet_label: str,
    oscillator_strength: float,
    gamma_value: float,
) -> AbsorptionLine:
    """Create an absorption line with derived wavelength range."""
    observed = rest_wavelength * (1.0 + center_z)
    delta_lambda = observed * max(window_kms, 10.0) / LIGHT_SPEED_KMS
    lambda_range = (observed - delta_lambda, observed + delta_lambda)

    line = project.add_absorption_line(
        species=species,
        transition_name=transition_name,
        rest_wavelength=rest_wavelength,
        center_z=center_z,
        window_kms=window_kms,
        multiplet_label=multiplet_label,
        oscillator_strength=oscillator_strength,
        gamma_value=gamma_value,
        lambda_range=lambda_range,
        region_id=region.region_id if region else None,
        created_by="doc-fixture",
    )
    line.multiplet_ids = []
    return line


def _apply_identify_demo_fixture(app: QApplication, window: MainWindow) -> None:
    """Populate the main window with demo data for identify-mode documentation."""
    project = create_identify_demo_project()
    window.set_current_project(project)
    app.processEvents()


_FIXTURES: tuple[FixtureDefinition, ...] = (
    FixtureDefinition(
        name="analysis-demo",
        apply=_apply_analysis_demo_fixture,
        description="Populate Analysis Overview, Region Detail, and Structure with demo data.",
        scopes=("analysis_overview", "analysis_region_detail", "analysis_structure", "common"),
        tags=("demo", "user-manual"),
    ),
    FixtureDefinition(
        name="identify-demo",
        apply=_apply_identify_demo_fixture,
        description=(
            "Populate Identify mode with a registered doublet, unclaimed detection"
            " candidates at the pinned 5.0 sigma threshold, and one temporary line."
        ),
        scopes=("identify",),
        tags=("demo", "user-manual"),
    ),
)

_FIXTURE_MAP: dict[str, FixtureDefinition] = {fixture.name: fixture for fixture in _FIXTURES}


def _seed_observed_spectrum(
    project: SpectroscopyProject,
    *,
    debug: bool,
    redshifts: tuple[float, ...] = (1.292,),
    wavelength_range: tuple[float, float] = (3541.0, 3560.0),
    sample_count: int = 1024,
) -> None:
    """Attach a deterministic spectrum with one C IV doublet per redshift.

    Args:
        project: Project instance that receives the synthetic spectrum.
        debug: Flag that toggles debug-friendly logging and RNG seeding.
        redshifts: Absorber redshifts; each contributes a C IV doublet.
        wavelength_range: Observed wavelength span in Angstrom.
        sample_count: Number of wavelength samples.
    """
    wavelength = np.linspace(*wavelength_range, sample_count, dtype=np.float64)
    continuum = np.ones_like(wavelength)

    log_column_density = 14.5
    b_kms = 20.0
    signal_to_noise = 15.0
    redshift = redshifts[0]

    doublet = (
        {"rest": 1548.19, "oscillator_strength": 0.1908},
        {"rest": 1550.77, "oscillator_strength": 0.09522},
    )

    optical_depth = np.zeros_like(wavelength)
    for absorber_z in redshifts:
        for line in doublet:
            lambda_obs = line["rest"] * (1.0 + absorber_z)
            tau0 = _doppler_tau0(
                rest_angstrom=line["rest"],
                oscillator_strength=line["oscillator_strength"],
                log_column_density=log_column_density,
                b_kms=b_kms,
            )
            velocity = LIGHT_SPEED_KMS * (wavelength - lambda_obs) / lambda_obs
            optical_depth += tau0 * np.exp(-((velocity / b_kms) ** 2))

    flux = continuum * np.exp(-optical_depth)

    noise_sigma = 1.0 / signal_to_noise
    seed = 0 if debug else 42
    _LOGGER.debug("Seeding Analysis demo spectrum (debug=%s, seed=%d)", debug, seed)
    rng = np.random.default_rng(seed)
    noisy_flux = flux + rng.normal(0.0, noise_sigma, size=flux.shape)
    noisy_flux = noisy_flux.clip(0.0, None)
    error = np.full_like(flux, noise_sigma, dtype=np.float64)

    spectrum = Spectrum(
        wavelength=wavelength,
        flux=noisy_flux.astype(np.float64),
        error=error,
        header={
            "ORIGIN": "doc-fixture",
            "SPECIES": "C IV",
            "LINES": "1548.19/1550.77",
            "LOGN": log_column_density,
            "B_KMS": b_kms,
            "CFRAC": 1.0,
            "SNR": signal_to_noise,
            "REDSHIFT": redshift,
        },
    )
    project.model.set_observed_spectrum(spectrum)


def _doppler_tau0(
    *, rest_angstrom: float, oscillator_strength: float, log_column_density: float, b_kms: float
) -> float:
    """Return optical depth at line centre for a Doppler-broadened transition."""
    electron_charge_esu = 4.803204712570263e-10
    electron_mass_g = 9.1093837015e-28
    speed_of_light_cm_s = 2.99792458e10

    constant = (
        math.sqrt(math.pi) * (electron_charge_esu**2) / (electron_mass_g * speed_of_light_cm_s)
    )

    column_density = 10.0**log_column_density
    wavelength_cm = rest_angstrom * 1e-8
    b_cm_s = b_kms * 1e5

    return float(constant * oscillator_strength * wavelength_cm * column_density / b_cm_s)


def _create_spec_line(project: SpectroscopyProject, spec: _LineSpec) -> AbsorptionLine:
    return _create_line(
        project,
        species=spec.species,
        transition_name=spec.transition_name,
        rest_wavelength=spec.rest_wavelength,
        center_z=spec.center_z,
        window_kms=spec.window_kms,
        multiplet_label=spec.multiplet_label,
        oscillator_strength=spec.oscillator_strength,
        gamma_value=spec.gamma_value,
    )


def create_analysis_demo_project(*, debug: bool = False) -> SpectroscopyProject:
    """Construct a demo project populated with regions and lines.

    Args:
        debug: Flag to enable verbose logging and deterministic RNG seeding.
    """
    project = SpectroscopyProject(name="Doc Analysis Demo")
    _seed_observed_spectrum(project, debug=debug)

    line_specs = (
        _LineSpec("C IV", "C IV λ1548", 1548.19, 1.292, 150.0, "C IV λ1548", 0.1908, 2.65e8),
        _LineSpec("C IV", "C IV λ1551", 1550.77, 1.292, 150.0, "C IV λ1551", 0.09522, 2.64e8),
    )

    created_lines: list[AbsorptionLine] = []
    for line_spec in line_specs:
        line = _create_spec_line(project, line_spec)
        created_lines.append(line)

    line_ids = [line.line_id for line in created_lines]
    primary_region = project.create_region_with_lines(line_ids)

    target_region_id = primary_region.region_id
    project.update_region_analysis_range(target_region_id)

    return project


_IDENTIFY_DEMO_EXTRA_REDSHIFT = 1.302
_CIV_1548_REST = 1548.19


def create_identify_demo_project() -> SpectroscopyProject:
    """Construct a demo project with registered, tentative, and unclaimed features.

    The z = 1.292 doublet is registered into a confirmed region, the 1548
    member of the z = 1.302 doublet carries a temporary line, and its 1550
    member stays unclaimed so detection at the pinned 5.0 sigma threshold
    shows all three candidate statuses.
    """
    project = SpectroscopyProject(name="Doc Identify Demo")
    _seed_observed_spectrum(
        project,
        debug=False,
        redshifts=(1.292, _IDENTIFY_DEMO_EXTRA_REDSHIFT),
        wavelength_range=(3541.0, 3585.0),
        sample_count=2368,
    )
    # Detection requires a continuum model; the default component is flat at 1.0,
    # matching the normalized synthetic spectrum.
    project.initialize_continuum()

    line_specs = (
        _LineSpec(
            "C IV", "C IV λ1548", _CIV_1548_REST, 1.292, 150.0, "C IV λ1548", 0.1908, 2.65e8
        ),
        _LineSpec("C IV", "C IV λ1551", 1550.77, 1.292, 150.0, "C IV λ1551", 0.09522, 2.64e8),
    )
    created_lines = [_create_spec_line(project, spec) for spec in line_specs]
    primary_region = project.create_region_with_lines([line.line_id for line in created_lines])
    project.update_region_analysis_range(primary_region.region_id)

    temporary_center = _CIV_1548_REST * (1.0 + _IDENTIFY_DEMO_EXTRA_REDSHIFT)
    project.identify_state.add_temporary_line(
        "C IV",
        temporary_center - 1.0,
        temporary_center + 1.0,
        creation_method="doc-fixture",
        context=TemporaryLineContext(
            line_id="doc_civ_1548",
            rest_wavelength=_CIV_1548_REST,
            multiplet_id="",
            multiplet_label="C IV λ1548",
            transition_name="C IV λ1548",
            oscillator_strength=0.1908,
            gamma_value=2.65e8,
            tie_group_key="",
            center_z=_IDENTIFY_DEMO_EXTRA_REDSHIFT,
        ),
    )
    return project


__all__ = [
    "apply_fixture",
    "available_fixture_names",
    "create_analysis_demo_project",
    "create_identify_demo_project",
    "get_fixture",
]
