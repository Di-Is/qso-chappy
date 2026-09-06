"""Tests for Qt-independent structure tree presenter."""

from __future__ import annotations

from typing import cast

import pytest

from chappy.core.absorption.models import AbsorptionLine, AbsorptionRegion
from chappy.core.components.absorber import AbsorberComponent
from chappy.core.components.base import Parameter
from chappy.presentation.analysis.structure.tree_presenter import StructureTreePresenter


def _presenter() -> StructureTreePresenter:
    """Create a structure presenter with deterministic templates."""
    return StructureTreePresenter(
        range_tooltip_template="Observed range: {minimum:.2f} - {maximum:.2f} A",
        linked_line_header_template=("{species} {wavelengths} [z={redshift}, +/-{window} km/s]"),
        unknown_label="Unknown",
    )


def _line(
    line_id: str,
    *,
    rest_wavelength: float,
    multiplet_ids: list[str] | None = None,
    model_ids: list[str] | None = None,
    needs_optimization: bool = False,
) -> AbsorptionLine:
    """Create an absorption line for presenter tests."""
    return AbsorptionLine(
        line_id=line_id,
        species="Mg II",
        rest_wavelength=rest_wavelength,
        center_z=1.23456,
        window_kms=120.0,
        multiplet_label="Mg II",
        transition_name=f"Mg II {rest_wavelength:.0f}",
        oscillator_strength=0.6,
        gamma_value=1.0e8,
        lambda_range=(rest_wavelength * 2.0 - 1.0, rest_wavelength * 2.0 + 1.0),
        multiplet_ids=list(multiplet_ids or []),
        model_ids=list(model_ids or []),
        needs_optimization=needs_optimization,
    )


class _ComponentResolver:
    """Resolve one test absorber component."""

    def __init__(self, component: AbsorberComponent) -> None:
        """Initialize the resolver."""
        self._component = component

    def find_absorber_component(self, component_id: str) -> AbsorberComponent | None:
        """Return the test component for its ID."""
        if component_id == self._component.id:
            return self._component
        return None


def test_build_absorption_region_entry_consolidates_multiplet_rows() -> None:
    """Multiplet-related absorption lines become one linked-line row."""
    presenter = _presenter()
    blue = _line("mg2796", rest_wavelength=2796.0, multiplet_ids=["mg2803"])
    red = _line(
        "mg2803", rest_wavelength=2803.0, multiplet_ids=["mg2796"], needs_optimization=True
    )
    region = AbsorptionRegion(
        region_id="region-1", line_ids=["mg2796", "mg2803"], analysis_range=(5590.0, 5610.0)
    )

    entry = presenter.build_absorption_region_entry(
        region_id=region.region_id,
        region=region,
        lines={"mg2796": blue, "mg2803": red},
        component_resolver=None,
    )

    assert entry is not None
    assert entry.linked_line_count == 1
    assert entry.needs_optimization is True
    linked_line = entry.linked_line_nodes[0]
    assert linked_line.line_ids == ("mg2796", "mg2803")
    assert linked_line.multiplet_ids == ("mg2796", "mg2803")
    assert linked_line.tooltip == "Observed range: 5591.00 - 5607.00 A"


def test_build_absorption_region_entry_requires_resolver_for_model_backed_lines() -> None:
    """Model-backed structure lines require an explicit component resolver."""
    presenter = _presenter()
    line = _line("mg2796", rest_wavelength=2796.0, model_ids=["component-1"])
    region = AbsorptionRegion(
        region_id="region-1", line_ids=["mg2796"], analysis_range=(5590.0, 5610.0)
    )

    with pytest.raises(RuntimeError, match="component resolver"):
        presenter.build_absorption_region_entry(
            region_id=region.region_id,
            region=region,
            lines={"mg2796": line},
            component_resolver=None,
        )


def test_model_component_redshift_uses_component_value() -> None:
    """Model-backed rows use the component redshift, not the line fallback."""
    presenter = _presenter()
    component = AbsorberComponent(component_id="component-1", redshift=2.5)
    line = _line("mg2796", rest_wavelength=2796.0, model_ids=["component-1"])
    region = AbsorptionRegion(
        region_id="region-1", line_ids=["mg2796"], analysis_range=(5590.0, 5610.0)
    )

    entry = presenter.build_absorption_region_entry(
        region_id=region.region_id,
        region=region,
        lines={"mg2796": line},
        component_resolver=_ComponentResolver(component),
    )

    assert entry is not None
    assert entry.linked_line_nodes[0].components[0].redshift == 2.5


def test_model_component_missing_redshift_fails_fast() -> None:
    """A model-backed component without redshift is an invalid snapshot."""
    component = AbsorberComponent(component_id="component-1")
    component.parameters.pop("redshift")

    with pytest.raises(KeyError, match="redshift parameter"):
        StructureTreePresenter.component_redshift(component, None)


def test_model_component_invalid_redshift_fails_fast() -> None:
    """A model-backed component with malformed redshift is an invalid snapshot."""
    component = AbsorberComponent(component_id="component-1")
    malformed = Parameter("redshift", 0.0)
    malformed._value = cast(float, "bad")  # noqa: SLF001 - corrupt snapshot simulation
    component.parameters["redshift"] = malformed

    with pytest.raises(ValueError, match="invalid redshift"):
        StructureTreePresenter.component_redshift(component, None)


def test_model_component_line_redshift_fallback_fails_fast() -> None:
    """Line redshift fallback must not mask component redshift corruption."""
    component = AbsorberComponent(component_id="component-1")

    with pytest.raises(RuntimeError, match="component redshift"):
        StructureTreePresenter.component_redshift(component, 1.23456)
