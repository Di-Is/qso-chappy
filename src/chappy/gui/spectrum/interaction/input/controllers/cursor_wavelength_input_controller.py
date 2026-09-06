"""Input-side controller reporting the wavelength under the pointer."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from chappy.gui.spectrum.interaction.input.mapping.pointer_coordinate_mapper import (
        SpectrumPointerCoordinateMapper,
    )
    from chappy.gui.spectrum.interaction.input.ports import SpectrumPlotWidgetPort
    from chappy.gui.utils.plot_coordinate_transform import PlotCoordinateTransform


class CursorWavelengthInputController:
    """Resolve the spectrum wavelength currently under the pointer."""

    def __init__(
        self,
        *,
        coordinate_mapper: SpectrumPointerCoordinateMapper,
        transform_provider: Callable[[], PlotCoordinateTransform | None],
        plot_widget_provider: Callable[[], SpectrumPlotWidgetPort | None],
    ) -> None:
        """Initialize the controller."""
        self._coordinate_mapper = coordinate_mapper
        self._transform_provider = transform_provider
        self._plot_widget_provider = plot_widget_provider

    def wavelength_under_cursor(self) -> float | None:
        """Return the wavelength under the pointer, or None when it is off the axes."""
        data_position = self._coordinate_mapper.optional_global_cursor_data_position(
            transform=self._transform_provider(), plot_widget=self._plot_widget_provider()
        )
        if data_position is None:
            return None
        return data_position.wavelength
