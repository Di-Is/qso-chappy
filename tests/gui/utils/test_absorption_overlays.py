from __future__ import annotations

from chappy.gui.utils.absorption_overlays import (
    compute_confirmed_line_regions,
    compute_temporary_line_regions,
    merge_region_payloads,
)


class FakeRegion:
    def __init__(self, region_id: str, display_color: str | None = None) -> None:
        self.region_id = region_id
        self.display_color = display_color or "#2ecc71"


class FakeLine:
    def __init__(
        self,
        line_id: str,
        species: str,
        rest_wavelength: float,
        center_z: float,
        window_kms: float,
        *,
        lambda_range: tuple[float, float] | None = None,
        region_id: str | None = None,
        transition_name: str | None = None,
    ) -> None:
        self.line_id = line_id
        self.species = species
        self.rest_wavelength = rest_wavelength
        self.center_z = center_z
        self.window_kms = window_kms
        self.lambda_range = lambda_range
        self.region_id = region_id
        self.multiplet_ids: list[str] = []
        self.transition_name = transition_name or species

    def observed_wavelength(self) -> float:
        return self.rest_wavelength * (1.0 + self.center_z)


class FakeTemporaryLine:
    def __init__(
        self,
        line_id: str,
        species: str,
        lambda_min: float,
        lambda_max: float,
        *,
        status: str = "pending",
        transition_name: str | None = None,
        rest_wavelength: float | None = None,
    ) -> None:
        self.line_id = line_id
        self.temporary_line_id = line_id  # For compatibility with TemporaryLine interface
        self.species = species
        self.lambda_min = lambda_min
        self.lambda_max = lambda_max
        self.status = status
        self.transition_name = transition_name or species
        self.rest_wavelength = rest_wavelength or (lambda_min + lambda_max) / 2.0
        self.center_wavelength = (lambda_min + lambda_max) / 2.0
        if self.rest_wavelength:
            self.center_z = (self.center_wavelength / self.rest_wavelength) - 1.0
        else:  # pragma: no cover - defensive fallback
            self.center_z = None


class DummyProject:
    def __init__(self, lines: list[FakeLine], regions: list[FakeRegion]) -> None:
        self._lines = lines
        self.absorption_regions = {region.region_id: region for region in regions}

    def list_absorption_lines(self) -> list[FakeLine]:
        return self._lines


def test_compute_confirmed_line_regions_uses_group_color() -> None:
    region = FakeRegion("g1", "#123456")
    line = FakeLine(
        "s1",
        "C IV",
        rest_wavelength=1548.2,
        center_z=1.5,
        window_kms=150.0,
        lambda_range=(4500.0, 4550.0),
        region_id=region.region_id,
    )
    project = DummyProject([line], [region])

    overlays = compute_confirmed_line_regions(project)

    assert overlays
    entry = overlays[0]
    assert entry["lambda_start"] == 4500.0
    assert entry["lambda_end"] == 4550.0
    assert entry["color"] == region.display_color
    assert entry["category"] == "confirmed"
    assert "C IV" in entry["label"]


def test_compute_confirmed_line_regions_filters_by_region_id() -> None:
    first_region = FakeRegion("g1", "#123456")
    second_region = FakeRegion("g2", "#654321")
    first_line = FakeLine(
        "s1",
        "C IV",
        rest_wavelength=1548.2,
        center_z=1.5,
        window_kms=150.0,
        region_id=first_region.region_id,
    )
    second_line = FakeLine(
        "s2",
        "Si IV",
        rest_wavelength=1393.8,
        center_z=1.5,
        window_kms=150.0,
        region_id=second_region.region_id,
    )
    project = DummyProject([first_line, second_line], [first_region, second_region])

    overlays = compute_confirmed_line_regions(project, region_id=second_region.region_id)

    assert [entry["id"] for entry in overlays] == [second_line.line_id]


def test_compute_temporary_line_regions_respects_status_palette() -> None:
    pending = FakeTemporaryLine("t1", "Si II", 5000.0, 5005.0, status="pending")
    preview = FakeTemporaryLine("t2", "O VI", 4800.0, 4804.0, status="preview")

    overlays = compute_temporary_line_regions([pending, preview])

    assert overlays
    assert overlays[0]["lambda_start"] == 4800.0  # Sorted ascending
    assert overlays[0]["category"] == "temporary"
    assert preview.species in overlays[0]["label"]

    colors = {entry["id"]: entry["color"] for entry in overlays}
    assert colors[pending.line_id] != colors[preview.line_id]


def test_merge_region_payloads_sorts_combined_lists() -> None:
    later = [{"lambda_start": 1300.0, "lambda_end": 1310.0}]
    earlier = [{"lambda_start": 900.0, "lambda_end": 905.0}]

    merged = merge_region_payloads(later, earlier)

    assert merged[0]["lambda_start"] == 900.0
    assert merged[-1]["lambda_start"] == 1300.0
