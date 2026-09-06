"""Behavior tests for SpectrumInputAdapter."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent

from chappy.core.editing_mode import EditingMode
from chappy.gui.modes.analysis.contracts import SpectrumProfile
from chappy.gui.shell.analysis_surface_ui_adapter import analysis_spectrum_policy
from chappy.gui.shell.spectrum_mode_policy import spectrum_interaction_mode_policy
from chappy.gui.protocols.intent_types import (
    CenterOnWavelengthIntent,
    EndAbsorberDragIntent,
    PanIntent,
    SelectAbsorberIntent,
    ShowContextMenuIntent,
    ToggleVelocityPlotIntent,
    ZoomFactorIntent,
    ZoomRectIntent,
)
from chappy.gui.spectrum.interaction.input.ports import (
    ContinuumInteractionEventSink,
    SpectrumInputAdapterEventSink,
)
from chappy.gui.spectrum.interaction.input.spectrum_input_adapter import SpectrumInputAdapter
from chappy.gui.spectrum.interaction.support.errors import InteractionStateError
from chappy.presentation.interaction.interaction_contracts import (
    AbsorberDragContext,
    InteractionChannel,
    InteractionPhase,
    InteractionStateSnapshot,
    RectZoomContext,
)

InteractorContext = AbsorberDragContext | RectZoomContext


@dataclass
class _CanvasFake:
    """Canvas surface required by PlotCoordinateTransform."""

    def width(self) -> int:
        """Return a deterministic width."""
        return 800

    def height(self) -> int:
        """Return a deterministic height."""
        return 600

    def devicePixelRatio(self) -> float:  # noqa: N802
        """Return a deterministic device pixel ratio."""
        return 1.0


@dataclass
class _DataTransformFake:
    """Data transform surface required by PlotCoordinateTransform."""

    def transform(self, _position: tuple[float, float]) -> tuple[float, float]:
        """Return deterministic data coordinates."""
        return (5000.0, 1.0)


@dataclass
class _TransDataFake:
    """Invertible transform surface required by PlotCoordinateTransform."""

    def inverted(self) -> _DataTransformFake:
        """Return the inverse transform."""
        return _DataTransformFake()


@dataclass
class _AxesFake:
    """Axes surface required by PlotCoordinateTransform."""

    transData: _TransDataFake = field(default_factory=_TransDataFake)


@dataclass
class _RendererFake:
    """Renderer surface required by PlotCoordinateTransform."""

    axes: _AxesFake | None = field(default_factory=_AxesFake)


@dataclass
class _CoordinatorRecorder:
    """Record optimize cursor feedback from the interactor."""

    cursor_updates: list[tuple[float, bool]] = field(default_factory=list)

    def update_optimize_cursor(self, wavelength: float, shift_pressed: bool) -> None:
        """Store the latest optimize cursor feedback."""
        self.cursor_updates.append((wavelength, shift_pressed))


@dataclass
class _SpectrumPlotFake:
    """Small plot double exposing the public methods used by the interactor."""

    absorber_id: str | None = None
    canvas: _CanvasFake = field(default_factory=_CanvasFake)
    renderer: _RendererFake = field(default_factory=_RendererFake)
    cursors: list[Qt.CursorShape] = field(default_factory=list)
    mouse_input: SpectrumInputAdapterEventSink | None = None
    continuum_input: ContinuumInteractionEventSink | None = None
    detected_wavelengths: list[float] = field(default_factory=list)

    def setCursor(self, cursor: Qt.CursorShape) -> None:  # noqa: N802
        """Record cursor changes requested by interaction modes."""
        self.cursors.append(cursor)

    def get_absorber_at_position(self, wavelength: float) -> str | None:
        """Return the configured absorber marker for a wavelength."""
        self.detected_wavelengths.append(wavelength)
        return self.absorber_id

    def set_input_ports(
        self,
        *,
        mouse: SpectrumInputAdapterEventSink | None,
        continuum: ContinuumInteractionEventSink | None,
    ) -> None:
        """Record the input ports attached to the plot."""
        self.mouse_input = mouse
        self.continuum_input = continuum

    def continuum_points(self) -> list[tuple[float, float]]:
        """Return no continuum points by default."""
        return []

    def mapFromGlobal(self, _position: QPoint) -> QPointF:  # noqa: N802
        """Map a global cursor position to a deterministic local position."""
        return QPointF(10.0, 20.0)


@dataclass
class _SpectrumViewFake:
    """Small spectrum view double used by SpectrumInputAdapter."""

    spectrum_plot: _SpectrumPlotFake | None = None
    coordinator: _CoordinatorRecorder = field(default_factory=_CoordinatorRecorder)
    wavelength_range: tuple[float, float] = (4000.0, 5000.0)

    def get_wavelength_range(self) -> tuple[float, float]:
        """Return the visible wavelength range."""
        return self.wavelength_range


@dataclass
class _CoordinateTransformFake:
    """Deterministic coordinate transform for Qt event positions."""

    data_positions: list[tuple[float, float] | None]
    received_qt_positions: list[tuple[float, float]] = field(default_factory=list)

    def qt_to_data_coordinates(
        self, x_position: float, y_position: float
    ) -> tuple[float, float] | None:
        """Convert Qt coordinates to the next configured data coordinate."""
        self.received_qt_positions.append((x_position, y_position))
        if len(self.data_positions) == 1:
            return self.data_positions[0]
        return self.data_positions.pop(0)

    def is_valid_position(self, _x_position: float, _y_position: float) -> bool:
        """Return True for all configured test positions."""
        return True


@dataclass
class _SignalRecorder:
    """Collect emitted interactor signals for assertions."""

    zooms: list[object] = field(default_factory=list)
    pans: list[object] = field(default_factory=list)
    absorbers: list[object] = field(default_factory=list)
    context_menus: list[object] = field(default_factory=list)
    identify: list[object] = field(default_factory=list)
    centers: list[object] = field(default_factory=list)
    cursor_left_count: int = 0
    identify_shift_release_count: int = 0
    mode_velocity_shortcuts: list[bool] = field(default_factory=list)
    mode_clicks: list[tuple[float, float, int]] = field(default_factory=list)
    snapshots: list[InteractionStateSnapshot[InteractorContext]] = field(default_factory=list)

    def connect(self, interactor: SpectrumInputAdapter) -> None:
        """Connect this recorder to the interactor signals."""
        interactor.sig_zoom_requested.connect(self.zooms.append)
        interactor.sig_pan_requested.connect(self.pans.append)
        interactor.sig_absorber_action.connect(self.absorbers.append)
        interactor.sig_context_menu_requested.connect(self.context_menus.append)
        interactor.sig_identify_action.connect(self.identify.append)
        interactor.sig_center_requested.connect(self.centers.append)
        interactor.sig_cursor_left.connect(self._record_cursor_left)
        interactor.sig_identify_preview_shift_released.connect(self._record_identify_shift_release)
        interactor.sig_mode_velocity_shortcut_requested.connect(
            lambda: self.mode_velocity_shortcuts.append(True)
        )
        interactor.sig_mode_click_requested.connect(
            lambda wavelength, flux, modifiers: self.mode_clicks.append(
                (wavelength, flux, modifiers)
            )
        )
        interactor.sig_interaction_snapshot.connect(self.snapshots.append)

    def _record_cursor_left(self) -> None:
        """Record a cursor-left signal emission."""
        self.cursor_left_count += 1

    def _record_identify_shift_release(self) -> None:
        """Record a transient Identify Shift release."""
        self.identify_shift_release_count += 1


def _attach_absorber_plot(
    interactor: SpectrumInputAdapter, view: _SpectrumViewFake, *, absorber_id: str
) -> _SpectrumPlotFake:
    """Attach a plot fake through the required interactor boundary."""
    plot = _SpectrumPlotFake(absorber_id=absorber_id)
    view.spectrum_plot = plot
    interactor.attach_plot_widget(plot)
    return plot


def _key_event(
    key: Qt.Key, modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier
) -> QKeyEvent:
    """Create a key press event."""
    return QKeyEvent(QEvent.Type.KeyPress, key, modifiers)


def _key_release_event(key: Qt.Key) -> QKeyEvent:
    """Create a key-release event."""
    return QKeyEvent(QEvent.Type.KeyRelease, key, Qt.KeyboardModifier.NoModifier)


def _mouse_event(
    *,
    button: Qt.MouseButton = Qt.MouseButton.LeftButton,
    position: QPointF = QPointF(10.0, 20.0),
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    event_type: QEvent.Type = QEvent.Type.MouseButtonPress,
) -> QMouseEvent:
    """Create a mouse event with deterministic local/global positions."""
    return QMouseEvent(event_type, position, position, button, button, modifiers)


def _wheel_event(
    *,
    angle_delta: QPoint = QPoint(0, 0),
    pixel_delta: QPoint = QPoint(0, 0),
    position: QPointF = QPointF(150.0, 250.0),
) -> QWheelEvent:
    """Create a wheel event with deterministic deltas."""
    return QWheelEvent(
        position,
        position,
        pixel_delta,
        angle_delta,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


@pytest.fixture
def view() -> _SpectrumViewFake:
    """Create a spectrum view fake."""
    return _SpectrumViewFake()


@pytest.fixture
def interactor(view: _SpectrumViewFake) -> Iterator[SpectrumInputAdapter]:
    """Create a SpectrumInputAdapter instance."""
    adapter = SpectrumInputAdapter(view=view)
    yield adapter


def test_identify_velocity_key_routes_to_mode_owner(interactor: SpectrumInputAdapter) -> None:
    """V in identify mode routes to the mode owner without arming a channel."""
    interactor.set_mode_capabilities(
        spectrum_interaction_mode_policy(EditingMode.IDENTIFY).input_capabilities
    )
    recorder = _SignalRecorder()
    recorder.connect(interactor)

    handled = interactor.handle_key_event(_key_event(Qt.Key.Key_V))

    assert handled is True
    assert recorder.mode_velocity_shortcuts == [True]
    assert recorder.snapshots == []


class TestSpectrumInputAdapterKeyboardAndWheel:
    """Keyboard and wheel behavior for SpectrumInputAdapter."""

    def test_control_plus_emits_zoom_intent(self, interactor: SpectrumInputAdapter) -> None:
        """Primary modifier plus emits a zoom-in intent."""
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        handled = interactor.handle_key_event(
            _key_event(Qt.Key.Key_Plus, Qt.KeyboardModifier.ControlModifier)
        )

        assert handled is True
        assert len(recorder.zooms) == 1
        intent = recorder.zooms[0]
        assert isinstance(intent, ZoomFactorIntent)
        assert intent.factor == pytest.approx(1.1)

    def test_plus_without_modifier_is_ignored(self, interactor: SpectrumInputAdapter) -> None:
        """Bare plus does not zoom while typing numeric values."""
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        handled = interactor.handle_key_event(_key_event(Qt.Key.Key_Plus))

        assert handled is False
        assert recorder.zooms == []

    def test_navigation_key_emits_absorber_selection_intent(
        self, interactor: SpectrumInputAdapter
    ) -> None:
        """Navigation keys emit absorber selection intents."""
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        handled = interactor.handle_key_event(_key_event(Qt.Key.Key_N))

        assert handled is True
        assert len(recorder.absorbers) == 1
        intent = recorder.absorbers[0]
        assert isinstance(intent, SelectAbsorberIntent)
        assert intent.direction == "next"

    def test_unhandled_key_is_not_consumed(self, interactor: SpectrumInputAdapter) -> None:
        """Unhandled keys are returned to the caller."""
        event = _key_event(Qt.Key.Key_unknown)

        handled = interactor.handle_key_event(event)

        assert handled is False

    def test_identify_shift_release_emits_typed_preview_signal(
        self, interactor: SpectrumInputAdapter
    ) -> None:
        """Shift release is explicit and does not masquerade as cursor leave."""
        interactor.set_mode_capabilities(
            spectrum_interaction_mode_policy(EditingMode.IDENTIFY).input_capabilities
        )
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        handled = interactor.handle_key_release_event(_key_release_event(Qt.Key.Key_Shift))

        assert handled is True
        assert recorder.identify_shift_release_count == 1
        assert recorder.cursor_left_count == 0

    def test_shift_release_is_not_consumed_outside_identify(
        self, interactor: SpectrumInputAdapter
    ) -> None:
        """Other modes retain ownership of their key-release handling."""
        interactor.set_mode_capabilities(
            spectrum_interaction_mode_policy(EditingMode.ANALYSIS).input_capabilities
        )
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        handled = interactor.handle_key_release_event(_key_release_event(Qt.Key.Key_Shift))

        assert handled is False
        assert recorder.identify_shift_release_count == 0

    def test_wheel_event_to_zoom_intent(self, interactor: SpectrumInputAdapter) -> None:
        """Vertical wheel motion emits fixed-point zoom intent."""
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        handled = interactor.handle_wheel((4500.0, 0.7), (0, 120))

        assert handled is True
        assert len(recorder.zooms) == 1
        intent = recorder.zooms[0]
        assert isinstance(intent, ZoomFactorIntent)
        assert intent.factor == pytest.approx(1.1)
        assert intent.center_wavelength == pytest.approx(4500.0)
        assert intent.cursor_relative_position == pytest.approx(0.5)

    def test_wheel_zoom_cursor_at_edge(self, interactor: SpectrumInputAdapter) -> None:
        """Wheel zoom preserves cursor relative position near the edge."""
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        handled = interactor.handle_wheel((4950.0, 0.7), (0, 120))

        assert handled is True
        assert len(recorder.zooms) == 1
        intent = recorder.zooms[0]
        assert isinstance(intent, ZoomFactorIntent)
        assert intent.center_wavelength == pytest.approx(4950.0)
        assert intent.cursor_relative_position == pytest.approx(0.95)

    def test_horizontal_wheel_motion_emits_pan_intent(
        self, interactor: SpectrumInputAdapter
    ) -> None:
        """Horizontal wheel motion emits a pan intent without zooming."""
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        handled = interactor.handle_wheel((4500.0, 0.7), (120, 0))

        assert handled is True
        assert recorder.zooms == []
        assert len(recorder.pans) == 1
        intent = recorder.pans[0]
        assert isinstance(intent, PanIntent)
        assert intent.fraction > 0.0

    @pytest.mark.parametrize(
        ("delta", "expected_signal"), [((20, 120), "zoom"), ((120, 10), "pan")]
    )
    def test_minor_wheel_jitter_uses_dominant_axis(
        self, interactor: SpectrumInputAdapter, delta: tuple[int, int], expected_signal: str
    ) -> None:
        """Mixed wheel deltas use only the dominant gesture axis."""
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        handled = interactor.handle_wheel((4500.0, 0.7), delta)

        assert handled is True
        assert bool(recorder.zooms) is (expected_signal == "zoom")
        assert bool(recorder.pans) is (expected_signal == "pan")

    def test_wheel_zoom_records_cursor_relative_position(
        self, interactor: SpectrumInputAdapter
    ) -> None:
        """Wheel zoom stores cursor position inside the current wavelength range."""
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        handled = interactor.handle_wheel((4500.0, 0.7), QPoint(0, 120))

        assert handled is True
        intent = recorder.zooms[0]
        assert isinstance(intent, ZoomFactorIntent)
        assert intent.cursor_relative_position == pytest.approx(0.5)

    def test_wheel_zoom_invalid_current_range_omits_cursor_relative_position(
        self, interactor: SpectrumInputAdapter, view: _SpectrumViewFake
    ) -> None:
        """Invalid wavelength range falls back to zoom without cursor-relative anchoring."""
        view.wavelength_range = (5000.0, 4000.0)
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        handled = interactor.handle_wheel((4500.0, 0.7), QPoint(0, 120))

        assert handled is True
        intent = recorder.zooms[0]
        assert isinstance(intent, ZoomFactorIntent)
        assert intent.cursor_relative_position is None

    def test_wheel_zoom_view_range_error_omits_cursor_relative_position(
        self, interactor: SpectrumInputAdapter, view: _SpectrumViewFake
    ) -> None:
        """View range lookup errors fall back to zoom without cursor-relative anchoring."""

        def _raise_range_error() -> tuple[float, float]:
            """Raise the same user-state error handled by wheel routing."""
            raise ValueError("range unavailable")

        view.get_wavelength_range = _raise_range_error
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        handled = interactor.handle_wheel((4500.0, 0.7), QPoint(0, 120))

        assert handled is True
        intent = recorder.zooms[0]
        assert isinstance(intent, ZoomFactorIntent)
        assert intent.cursor_relative_position is None


class TestSpectrumInputAdapterMouseProcessing:
    """Mouse event processing behavior for SpectrumInputAdapter."""

    def test_mouse_click_without_mode_is_silent(self, interactor: SpectrumInputAdapter) -> None:
        """Plain left-click without interaction mode emits no absorber intent."""
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        handled = interactor.handle_mouse_click((5000.0, 0.8), "left")

        assert handled is False
        assert recorder.absorbers == []

    def test_process_mouse_press_converts_position_and_keeps_absorbers_silent(
        self, interactor: SpectrumInputAdapter
    ) -> None:
        """Mouse press through the Qt adapter uses converted data coordinates."""
        transform = _CoordinateTransformFake([(5000.0, 0.8)])
        interactor.coord_transform = transform
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        interactor.process_mouse_event(
            _mouse_event(position=QPointF(100.0, 200.0), event_type=QEvent.Type.MouseButtonPress)
        )

        assert transform.received_qt_positions == [(100.0, 200.0)]
        assert recorder.absorbers == []

    def test_process_mouse_event_without_transform_is_silent(
        self, interactor: SpectrumInputAdapter
    ) -> None:
        """Plot event forwarding without a transform emits no user-facing signals."""
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        interactor.process_mouse_event(
            _mouse_event(position=QPointF(100.0, 200.0), event_type=QEvent.Type.MouseButtonPress)
        )

        assert recorder.zooms == []
        assert recorder.pans == []
        assert recorder.absorbers == []
        assert recorder.context_menus == []
        assert recorder.identify == []

    def test_process_wheel_event_emits_zoom(self, interactor: SpectrumInputAdapter) -> None:
        """Qt wheel event with angle delta emits a zoom intent."""
        interactor.coord_transform = _CoordinateTransformFake([(4500.0, 0.7)])
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        interactor.process_mouse_event(_wheel_event(angle_delta=QPoint(0, 120)))

        assert len(recorder.zooms) == 1
        assert isinstance(recorder.zooms[0], ZoomFactorIntent)

    def test_process_wheel_event_uses_pixel_delta(self, interactor: SpectrumInputAdapter) -> None:
        """Pixel delta fallback supports smooth-scroll devices."""
        interactor.coord_transform = _CoordinateTransformFake([(4500.0, 0.7)])
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        interactor.process_mouse_event(_wheel_event(pixel_delta=QPoint(40, 0)))

        assert len(recorder.pans) == 1
        assert isinstance(recorder.pans[0], PanIntent)

    def test_attach_plot_widget_initializes_transform_and_links_interactor(
        self, interactor: SpectrumInputAdapter
    ) -> None:
        """A plot widget with renderer support receives an interactor link."""
        plot = _SpectrumPlotFake()

        interactor.attach_plot_widget(plot)

        assert interactor.coord_transform is not None
        assert plot.mouse_input is not interactor
        assert plot.mouse_input is not None
        assert plot.continuum_input is interactor

    def test_attach_plot_widget_rejects_none(self, interactor: SpectrumInputAdapter) -> None:
        """Attaching None is an internal wiring error, not teardown."""
        with pytest.raises(TypeError):
            interactor.attach_plot_widget(None)  # type: ignore[arg-type]

    def test_detach_plot_widget_clears_transform_and_link(
        self, interactor: SpectrumInputAdapter
    ) -> None:
        """Explicit detach clears the current transform and interactor link."""
        plot = _SpectrumPlotFake()
        interactor.attach_plot_widget(plot)

        interactor.detach_plot_widget()

        assert interactor.coord_transform is None
        assert plot.mouse_input is None
        assert plot.continuum_input is None

    def test_handle_mouse_leave_emits_cursor_left(self, interactor: SpectrumInputAdapter) -> None:
        """Mouse leave emits cursor-left feedback."""
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        interactor.handle_mouse_leave()

        assert recorder.cursor_left_count == 1

    def test_handle_double_click_center_emits_center_intent(
        self, interactor: SpectrumInputAdapter
    ) -> None:
        """Double-click center bridge emits a typed center intent."""
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        interactor.handle_double_click_center(5050.0)

        assert len(recorder.centers) == 1
        intent = recorder.centers[0]
        assert isinstance(intent, CenterOnWavelengthIntent)
        assert intent.wavelength == pytest.approx(5050.0)

    def test_right_click_context_menu_uses_data_position(
        self, interactor: SpectrumInputAdapter
    ) -> None:
        """Qt right-click forwarding emits a context menu intent for the data position."""
        interactor.coord_transform = _CoordinateTransformFake([(5000.0, 0.8)])
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        interactor.process_mouse_event(
            _mouse_event(
                button=Qt.MouseButton.RightButton,
                position=QPointF(100.0, 200.0),
                modifiers=Qt.KeyboardModifier.ShiftModifier,
                event_type=QEvent.Type.MouseButtonPress,
            )
        )

        assert len(recorder.context_menus) == 1
        intent = recorder.context_menus[0]
        assert isinstance(intent, ShowContextMenuIntent)
        assert intent.wavelength == pytest.approx(5000.0)
        assert intent.flux == pytest.approx(0.8)
        assert isinstance(intent.global_x, int)
        assert isinstance(intent.global_y, int)


class TestRectZoomFlow:
    """Rectangle zoom behavior for SpectrumInputAdapter."""

    def test_rect_zoom_release_emits_bounds_from_drag(
        self, interactor: SpectrumInputAdapter
    ) -> None:
        """Rectangle zoom emits final zoom bounds on mouse release."""
        transform = _CoordinateTransformFake([(5000.0, 0.6)])
        interactor.coord_transform = transform
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        interactor.set_rect_zoom_mode(True)
        interactor.handle_mouse_click((4000.0, 0.5), "left")
        handled = interactor.handle_mouse_release_event(
            _mouse_event(position=QPointF(10.0, 20.0), event_type=QEvent.Type.MouseButtonRelease)
        )

        assert handled is True
        assert transform.received_qt_positions == [(10.0, 20.0)]
        assert len(recorder.zooms) == 1
        intent = recorder.zooms[0]
        assert isinstance(intent, ZoomRectIntent)
        assert intent.min_wavelength == pytest.approx(4000.0)
        assert intent.max_wavelength == pytest.approx(5000.0)
        latest_snapshot = recorder.snapshots[-1]
        assert latest_snapshot.channel is InteractionChannel.RECT_ZOOM
        assert latest_snapshot.phase is InteractionPhase.IDLE
        context = latest_snapshot.context
        assert isinstance(context, RectZoomContext)
        assert context.bounds is not None
        assert context.bounds.min_wavelength == pytest.approx(4000.0)
        assert context.bounds.max_wavelength == pytest.approx(5000.0)

    def test_velocity_key_cancels_rect_zoom_before_routing(
        self, interactor: SpectrumInputAdapter
    ) -> None:
        """Velocity key cancels rectangle zoom and routes to the mode owner."""
        interactor.set_mode_capabilities(
            spectrum_interaction_mode_policy(EditingMode.IDENTIFY).input_capabilities
        )
        interactor.set_rect_zoom_mode(True)
        recorder = _SignalRecorder()
        recorder.connect(interactor)
        interactor.handle_mouse_click((4000.0, 0.5), "left")

        handled = interactor.handle_key_event(_key_event(Qt.Key.Key_V))

        assert handled is True
        assert interactor.is_rect_zoom_mode_enabled() is False
        assert recorder.mode_velocity_shortcuts == [True]
        assert [snapshot.phase for snapshot in recorder.snapshots] == [
            InteractionPhase.ARMED,
            InteractionPhase.CANCELLED,
        ]
        assert recorder.snapshots[0].channel is InteractionChannel.RECT_ZOOM
        assert recorder.snapshots[1].channel is InteractionChannel.RECT_ZOOM

    def test_velocity_shortcut_cancels_rect_zoom_before_routing(
        self, interactor: SpectrumInputAdapter
    ) -> None:
        """Global velocity shortcut cancels rectangle zoom and routes to the mode owner."""
        interactor.set_mode_capabilities(
            spectrum_interaction_mode_policy(EditingMode.IDENTIFY).input_capabilities
        )
        interactor.set_rect_zoom_mode(True)
        recorder = _SignalRecorder()
        recorder.connect(interactor)
        interactor.handle_mouse_click((4000.0, 0.5), "left")

        handled = interactor.trigger_velocity_shortcut()

        assert handled is True
        assert interactor.is_rect_zoom_mode_enabled() is False
        assert recorder.mode_velocity_shortcuts == [True]
        assert [snapshot.phase for snapshot in recorder.snapshots] == [
            InteractionPhase.ARMED,
            InteractionPhase.CANCELLED,
        ]


class TestVelocityFlow:
    """Velocity shortcut behavior for SpectrumInputAdapter."""

    def test_optimize_velocity_key_uses_optimize_toggle_signal(
        self, interactor: SpectrumInputAdapter
    ) -> None:
        """V in optimize mode emits the optimize velocity toggle signal."""
        interactor.set_mode_capabilities(
            analysis_spectrum_policy(SpectrumProfile.REGION_DETAIL).input_capabilities
        )
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        handled = interactor.handle_key_event(_key_event(Qt.Key.Key_V))

        assert handled is True
        assert recorder.mode_velocity_shortcuts == [True]


class TestAbsorberDragFlow:
    """Absorber drag behavior for SpectrumInputAdapter."""

    def test_absorber_drag_flow_emits_snapshots_and_intents(
        self, interactor: SpectrumInputAdapter, view: _SpectrumViewFake
    ) -> None:
        """Absorber drag emits start, update, and end through observable signals."""
        _attach_absorber_plot(interactor, view, absorber_id="abs-1")
        interactor.set_mode_capabilities(
            analysis_spectrum_policy(SpectrumProfile.REGION_DETAIL).input_capabilities
        )
        interactor.coord_transform = _CoordinateTransformFake(
            [(4100.0, 0.1), (4200.0, 0.15), (4300.0, 0.2)]
        )
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        handled_press = interactor.handle_mouse_press_event(_mouse_event())
        handled_move = interactor.handle_mouse_move_event(
            _mouse_event(position=QPointF(12.0, 22.0), event_type=QEvent.Type.MouseMove)
        )
        handled_release = interactor.handle_mouse_release_event(
            _mouse_event(position=QPointF(14.0, 24.0), event_type=QEvent.Type.MouseButtonRelease)
        )

        assert handled_press is True
        assert handled_move is True
        assert handled_release is True
        assert [snapshot.phase for snapshot in recorder.snapshots] == [
            InteractionPhase.ARMED,
            InteractionPhase.ACTIVE,
            InteractionPhase.IDLE,
        ]
        assert all(
            snapshot.channel is InteractionChannel.ABSORBER_DRAG for snapshot in recorder.snapshots
        )
        assert isinstance(recorder.absorbers[-1], EndAbsorberDragIntent)
        latest_context = recorder.snapshots[-1].context
        assert isinstance(latest_context, AbsorberDragContext)
        assert latest_context.absorber_id == "abs-1"
        assert latest_context.end == (4300.0, 0.2)

    def test_absorber_drag_cancel_on_transform_failure(
        self, interactor: SpectrumInputAdapter, view: _SpectrumViewFake
    ) -> None:
        """Absorber drag cancels gracefully when release transform fails."""
        _attach_absorber_plot(interactor, view, absorber_id="abs-2")
        interactor.set_mode_capabilities(
            analysis_spectrum_policy(SpectrumProfile.REGION_DETAIL).input_capabilities
        )
        interactor.coord_transform = _CoordinateTransformFake(
            [(4100.0, 0.1), (4150.0, 0.12), None]
        )
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        interactor.handle_mouse_press_event(_mouse_event())
        interactor.handle_mouse_move_event(
            _mouse_event(position=QPointF(6.0, 16.0), event_type=QEvent.Type.MouseMove)
        )
        handled_release = interactor.handle_mouse_release_event(
            _mouse_event(position=QPointF(7.0, 17.0), event_type=QEvent.Type.MouseButtonRelease)
        )

        assert handled_release is True
        assert len(recorder.absorbers) == 2
        latest_snapshot = recorder.snapshots[-1]
        assert latest_snapshot.phase is InteractionPhase.CANCELLED
        context = latest_snapshot.context
        assert isinstance(context, AbsorberDragContext)
        assert context.cancel_reason == "transform-failed"

    def test_velocity_key_is_ignored_during_absorber_drag(
        self, interactor: SpectrumInputAdapter, view: _SpectrumViewFake
    ) -> None:
        """V key is ignored while an absorber drag interaction is active."""
        _attach_absorber_plot(interactor, view, absorber_id="abs-1")
        interactor.set_mode_capabilities(
            analysis_spectrum_policy(SpectrumProfile.REGION_DETAIL).input_capabilities
        )
        interactor.coord_transform = _CoordinateTransformFake([(4100.0, 0.1), (4200.0, 0.2)])
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        interactor.handle_mouse_press_event(_mouse_event())
        handled = interactor.handle_key_event(_key_event(Qt.Key.Key_V))
        interactor.handle_mouse_release_event(
            _mouse_event(position=QPointF(12.0, 22.0), event_type=QEvent.Type.MouseButtonRelease)
        )

        assert handled is False
        assert recorder.mode_velocity_shortcuts == []
        assert [snapshot.phase for snapshot in recorder.snapshots] == [
            InteractionPhase.ARMED,
            InteractionPhase.IDLE,
        ]

    def test_rect_zoom_is_blocked_during_absorber_drag(
        self, interactor: SpectrumInputAdapter, view: _SpectrumViewFake
    ) -> None:
        """Rectangle zoom cannot replace an active absorber drag channel."""
        _attach_absorber_plot(interactor, view, absorber_id="abs-1")
        interactor.set_mode_capabilities(
            analysis_spectrum_policy(SpectrumProfile.REGION_DETAIL).input_capabilities
        )
        interactor.coord_transform = _CoordinateTransformFake([(4100.0, 0.1), (4200.0, 0.15)])
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        interactor.handle_mouse_press_event(_mouse_event())
        snapshot_count = len(recorder.snapshots)
        interactor.set_rect_zoom_mode(True)
        interactor.handle_mouse_release_event(
            _mouse_event(position=QPointF(12.0, 22.0), event_type=QEvent.Type.MouseButtonRelease)
        )

        assert interactor.is_rect_zoom_mode_enabled() is False
        assert len(recorder.snapshots) == snapshot_count + 1
        assert recorder.snapshots[-1].channel is InteractionChannel.ABSORBER_DRAG
        assert recorder.snapshots[-1].phase is InteractionPhase.IDLE


class TestMVPLiteFlow:
    """MVP-lite signal flow behavior from view to interactor."""

    def test_complete_mvp_flow_emits_zoom_intent(self, qtbot) -> None:
        """A real SpectrumView owns an interactor that emits zoom intents."""
        from chappy.gui.spectrum.spectrum_interaction_coordinator import (
            SpectrumInteractionCoordinator,
        )
        from chappy.gui.spectrum.spectrum_plot import create_default_spectrum_plot_host_factory
        from chappy.gui.spectrum.spectrum_view import SpectrumView

        view = SpectrumView(plot_host_factory=create_default_spectrum_plot_host_factory())
        qtbot.addWidget(view)
        interactor = view.spectrum_input_adapter
        interactor.sig_zoom_requested.disconnect(view.coordinator.handle_navigation_intent)
        emitted_zoom: list[object] = []
        interactor.sig_zoom_requested.connect(emitted_zoom.append)

        handled = interactor.handle_key_event(
            _key_event(Qt.Key.Key_Plus, Qt.KeyboardModifier.ControlModifier)
        )

        assert handled is True
        assert isinstance(view.coordinator, SpectrumInteractionCoordinator)
        assert len(emitted_zoom) == 1
        assert isinstance(emitted_zoom[0], ZoomFactorIntent)

    def test_signal_connection_delivers_zoom_intent(
        self, interactor: SpectrumInputAdapter
    ) -> None:
        """Qt signal connection delivers emitted intents to observers."""
        emitted_zoom: list[object] = []
        interactor.sig_zoom_requested.connect(emitted_zoom.append)
        intent = ZoomFactorIntent(factor=1.5)

        interactor.sig_zoom_requested.emit(intent)

        assert emitted_zoom == [intent]

    def test_identify_click_emits_raw_mode_click(self, interactor: SpectrumInputAdapter) -> None:
        """Identify mode left-click emits raw click facts for mode-owned handling."""
        interactor.set_mode_capabilities(
            spectrum_interaction_mode_policy(EditingMode.IDENTIFY).input_capabilities
        )
        recorder = _SignalRecorder()
        recorder.connect(interactor)

        handled = interactor.handle_mouse_click((5020.0, 0.6), "left", 0)

        assert handled is True
        assert recorder.identify == []
        assert recorder.mode_clicks == [(5020.0, 0.6, 0)]
