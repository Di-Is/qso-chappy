"""Tests for selective registration behavior in identify mode.

Users can select specific temporary lines for registration instead of
processing all lines at once.
"""

from __future__ import annotations

import pytest

from chappy.core.identify_state import IdentifySessionState, TemporaryLineContext


class TestSelectiveGrouping:
    """Tests for selected-id filtering ahead of registration."""

    @pytest.fixture
    def session_with_lines(self) -> IdentifySessionState:
        """Create session with 3 temporary lines for testing."""
        session = IdentifySessionState()
        # Add 3 lines with different wavelengths
        session.add_temporary_line(
            "C IV",
            1548.0,
            1549.0,
            creation_method="manual",
            context=TemporaryLineContext(
                line_id="test_civ_1548",
                rest_wavelength=1548.195,
                multiplet_id="",
                multiplet_label="",
                transition_name="C IV 1548.2",
                oscillator_strength=0.1,
                gamma_value=1e8,
                tie_group_key="",
            ),
        )
        session.add_temporary_line(
            "Si II",
            1526.0,
            1527.0,
            creation_method="manual",
            context=TemporaryLineContext(
                line_id="test_sii_1526",
                rest_wavelength=1526.707,
                multiplet_id="",
                multiplet_label="",
                transition_name="Si II 1526.7",
                oscillator_strength=0.1,
                gamma_value=1e8,
                tie_group_key="",
            ),
        )
        session.add_temporary_line(
            "O I",
            1302.0,
            1303.0,
            creation_method="manual",
            context=TemporaryLineContext(
                line_id="test_oi_1302",
                rest_wavelength=1302.168,
                multiplet_id="",
                multiplet_label="",
                transition_name="O I 1302.2",
                oscillator_strength=0.1,
                gamma_value=1e8,
                tie_group_key="",
            ),
        )
        return session

    def test_session_has_three_temporary_lines(
        self, session_with_lines: IdentifySessionState
    ) -> None:
        """Verify test fixture creates expected lines."""
        assert len(session_with_lines.temporary_lines) == 3

    def test_filtering_by_selected_ids(self, session_with_lines: IdentifySessionState) -> None:
        """Test that selected_ids filter correctly reduces target lines."""
        lines = session_with_lines.temporary_lines
        all_ids = [s.temporary_line_id for s in lines]

        # Select only first two lines
        selected_ids = all_ids[:2]
        selected_set = set(selected_ids)
        target_lines = [s for s in lines if s.temporary_line_id in selected_set]

        assert len(target_lines) == 2
        assert target_lines[0].species == "C IV"
        assert target_lines[1].species == "Si II"

    def test_empty_selected_ids_uses_all_lines(
        self, session_with_lines: IdentifySessionState
    ) -> None:
        """Test that empty selected_ids results in using all lines."""
        lines = session_with_lines.temporary_lines
        selected_ids: list[str] = []  # Empty list

        if selected_ids:
            target_lines = [s for s in lines if s.temporary_line_id in set(selected_ids)]
        else:
            target_lines = list(lines)

        assert len(target_lines) == 3


class TestSelectiveRemoval:
    """Tests for selective candidate removal after partial registration."""

    @pytest.fixture
    def session_with_four_lines(self) -> IdentifySessionState:
        """Create session with 4 temporary lines."""
        session = IdentifySessionState()
        for name, rest in (
            ("C IV", 1548.195),
            ("Si II", 1526.707),
            ("O I", 1302.168),
            ("Mg II", 2796.0),
        ):
            session.add_temporary_line(
                name,
                rest - 0.5,
                rest + 0.5,
                creation_method="manual",
                context=TemporaryLineContext(
                    line_id=f"test_{name.replace(' ', '').lower()}",
                    rest_wavelength=rest,
                    multiplet_id="",
                    multiplet_label="",
                    transition_name=f"{name} {rest:.1f}",
                    oscillator_strength=0.1,
                    gamma_value=1e8,
                    tie_group_key="",
                ),
            )
        return session

    def test_selective_removal_preserves_non_selected(
        self, session_with_four_lines: IdentifySessionState
    ) -> None:
        """Removing registered lines preserves the unselected ones."""
        session = session_with_four_lines
        all_ids = [line.temporary_line_id for line in session.temporary_lines]
        registered_ids = set(all_ids[:2])

        session.remove_temporary_lines(registered_ids)

        remaining_ids = {line.temporary_line_id for line in session.temporary_lines}
        assert len(remaining_ids) == 2
        assert remaining_ids.isdisjoint(registered_ids)
