"""Tests for resolving the wavelength under the pointer."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from chappy.gui.spectrum.interaction.input.controllers.cursor_wavelength_input_controller import (
    CursorWavelengthInputController,
)
from chappy.gui.spectrum.interaction.input.mapping.pointer_coordinate_mapper import DataPosition


@dataclass
class _CoordinateMapperFake:
    """Coordinate mapper fake for cursor wavelength tests."""

    global_position: DataPosition | None = None

    def optional_global_cursor_data_position(
        self, *, transform: object | None, plot_widget: object | None
    ) -> DataPosition | None:
        """Return the configured global cursor position when dependencies exist."""
        if transform is None or plot_widget is None:
            return None
        return self.global_position


def _controller(
    *,
    coordinate_mapper: _CoordinateMapperFake,
    transform: object | None = object(),
    plot_widget: object | None = object(),
) -> CursorWavelengthInputController:
    """Create a cursor wavelength controller with fakes."""
    return CursorWavelengthInputController(
        coordinate_mapper=coordinate_mapper,
        transform_provider=lambda: transform,
        plot_widget_provider=lambda: plot_widget,
    )


def test_wavelength_under_cursor_uses_global_cursor_position() -> None:
    """The live global cursor position provides the wavelength."""
    mapper = _CoordinateMapperFake(global_position=DataPosition(5200.0, 0.8))

    controller = _controller(coordinate_mapper=mapper)

    assert controller.wavelength_under_cursor() == pytest.approx(5200.0)


def test_wavelength_under_cursor_is_none_off_the_axes() -> None:
    """A pointer outside the plot resolves to no wavelength."""
    mapper = _CoordinateMapperFake(global_position=DataPosition(5200.0, 0.8))

    controller = _controller(coordinate_mapper=mapper, transform=None, plot_widget=None)

    assert controller.wavelength_under_cursor() is None
