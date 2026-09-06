"""Qt-free presentation payloads for identify cursor previews."""

from __future__ import annotations

from typing import Protocol, TypedDict


class PreviewEntry(TypedDict):
    """Type definition for cursor preview entry data."""

    line_id: str
    lambda_min: float
    lambda_max: float
    center: float
    label: str
    original_label: str
    transition_name: str
    color: str
    is_primary: bool
    fill_alpha: float
    line_alpha: float
    line_width: float
    line_style: str
    multiplet_id: str
    multiplet_label: str
    species: str
    rest_wavelength: float
    oscillator_strength: float
    gamma_value: float
    delta_velocity: float | None
    tie_group_key: str


class CursorPreviewPayload(TypedDict, total=False):
    """Typed payload for identify cursor preview rendering."""

    entries: list[PreviewEntry]
    observed_cursor: float
    modifiers: int
    hint_text: str


class PreviewEntryModelPort(Protocol):
    """Preview entry model fields required by presentation formatting."""

    @property
    def line_id(self) -> str:
        """Return the persistent line identifier."""
        ...

    @property
    def lambda_min(self) -> float:
        """Return the lower wavelength bound."""
        ...

    @property
    def lambda_max(self) -> float:
        """Return the upper wavelength bound."""
        ...

    @property
    def center(self) -> float:
        """Return the center wavelength."""
        ...

    @property
    def label(self) -> str:
        """Return the display label."""
        ...

    @property
    def original_label(self) -> str:
        """Return the unmodified display label."""
        ...

    @property
    def transition_name(self) -> str:
        """Return the transition name."""
        ...

    @property
    def color(self) -> str:
        """Return the display color."""
        ...

    @property
    def is_primary(self) -> bool:
        """Return whether this is the primary preview line."""
        ...

    @property
    def fill_alpha(self) -> float:
        """Return the fill opacity."""
        ...

    @property
    def line_alpha(self) -> float:
        """Return the outline opacity."""
        ...

    @property
    def line_width(self) -> float:
        """Return the outline width."""
        ...

    @property
    def line_style(self) -> str:
        """Return the outline style."""
        ...

    @property
    def multiplet_id(self) -> str:
        """Return the multiplet identifier."""
        ...

    @property
    def multiplet_label(self) -> str:
        """Return the multiplet display label."""
        ...

    @property
    def species(self) -> str:
        """Return the species label."""
        ...

    @property
    def rest_wavelength(self) -> float:
        """Return the rest wavelength."""
        ...

    @property
    def oscillator_strength(self) -> float:
        """Return the oscillator strength."""
        ...

    @property
    def gamma_value(self) -> float:
        """Return the damping gamma value."""
        ...

    @property
    def delta_velocity(self) -> float | None:
        """Return the velocity offset from the baseline line."""
        ...

    @property
    def tie_group_key(self) -> str:
        """Return the transient declarative tie-group key."""
        ...


def preview_entry_to_plot_payload(entry: PreviewEntryModelPort) -> PreviewEntry:
    """Convert an application preview model to a plot preview payload.

    Args:
        entry: Typed preview entry model.

    Returns:
        Plot preview payload.
    """
    return {
        "line_id": entry.line_id,
        "lambda_min": entry.lambda_min,
        "lambda_max": entry.lambda_max,
        "center": entry.center,
        "label": entry.label,
        "original_label": entry.original_label,
        "transition_name": entry.transition_name,
        "color": entry.color,
        "is_primary": entry.is_primary,
        "fill_alpha": entry.fill_alpha,
        "line_alpha": entry.line_alpha,
        "line_width": entry.line_width,
        "line_style": entry.line_style,
        "multiplet_id": entry.multiplet_id,
        "multiplet_label": entry.multiplet_label,
        "species": entry.species,
        "rest_wavelength": entry.rest_wavelength,
        "oscillator_strength": entry.oscillator_strength,
        "gamma_value": entry.gamma_value,
        "delta_velocity": entry.delta_velocity,
        "tie_group_key": entry.tie_group_key,
    }
