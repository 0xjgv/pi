"""Tests for live artifact display module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from π.cli.live_display import (
    _PHASE_TO_STAGE,
    _STAGE_PHASES,
    _STATUS_ICONS,
    LiveArtifactDisplay,
    TrackedArtifact,
)
from π.state import ArtifactEvent, ArtifactStatus


class TestTrackedArtifact:
    """Tests for TrackedArtifact dataclass."""

    def test_default_status_is_pending(self) -> None:
        """TrackedArtifact defaults to PENDING status."""
        artifact = TrackedArtifact(path="/some/path.md")
        assert artifact.status == ArtifactStatus.PENDING

    def test_custom_status(self) -> None:
        """TrackedArtifact accepts custom status."""
        artifact = TrackedArtifact(path="/path.md", status=ArtifactStatus.DONE)
        assert artifact.status == ArtifactStatus.DONE


class TestConstantMappings:
    """Tests for phase/stage mapping constants."""

    def test_phase_to_stage_maps_research(self) -> None:
        """Research phase maps to Research stage."""
        assert _PHASE_TO_STAGE["Researching codebase"] == "Research"

    def test_phase_to_stage_maps_design(self) -> None:
        """Design phases map to Design stage."""
        assert _PHASE_TO_STAGE["Creating plan"] == "Design"
        assert _PHASE_TO_STAGE["Reviewing plan"] == "Design"

    def test_phase_to_stage_maps_execute(self) -> None:
        """Execute phases map to Execute stage."""
        assert _PHASE_TO_STAGE["Implementing plan"] == "Execute"
        assert _PHASE_TO_STAGE["Committing changes"] == "Execute"

    def test_stage_phases_contains_all_stages(self) -> None:
        """All three stages have defined phases."""
        assert "Research" in _STAGE_PHASES
        assert "Design" in _STAGE_PHASES
        assert "Execute" in _STAGE_PHASES

    def test_status_icons_all_defined(self) -> None:
        """All artifact statuses have icons."""
        for status in ArtifactStatus:
            assert status in _STATUS_ICONS


class TestLiveArtifactDisplay:
    """Tests for LiveArtifactDisplay class."""

    @pytest.fixture
    def display(self) -> LiveArtifactDisplay:
        """Create a fresh LiveArtifactDisplay."""
        return LiveArtifactDisplay()

    def test_initial_state(self, display: LiveArtifactDisplay) -> None:
        """Display initializes with empty state."""
        assert display.current_phase is None
        assert display.phase_elapsed == 0.0
        assert display.artifacts == {}
        assert display.completed_stages == set()
        assert display.completed_phases == {}

    @patch("π.cli.live_display.Live")
    @patch("π.cli.live_display.subscribe_to_artifacts")
    @patch("π.cli.live_display.set_live_display_active")
    def test_start_subscribes_to_events(
        self,
        mock_set_active: MagicMock,
        mock_subscribe: MagicMock,
        mock_live: MagicMock,
        display: LiveArtifactDisplay,
    ) -> None:
        """start() subscribes to artifact events and activates display."""
        mock_subscribe.return_value = lambda: None

        display.start()

        mock_set_active.assert_called_once_with(True)
        mock_subscribe.assert_called_once()
        mock_live.assert_called_once()
        mock_live.return_value.start.assert_called_once()

    @patch("π.cli.live_display.Live")
    @patch("π.cli.live_display.subscribe_to_artifacts")
    @patch("π.cli.live_display.set_live_display_active")
    def test_stop_unsubscribes_and_clears_flag(
        self,
        mock_set_active: MagicMock,
        mock_subscribe: MagicMock,
        mock_live: MagicMock,
        display: LiveArtifactDisplay,
    ) -> None:
        """stop() unsubscribes from events and deactivates display."""
        mock_unsubscribe = MagicMock()
        mock_subscribe.return_value = mock_unsubscribe

        display.start()
        mock_set_active.reset_mock()

        display.stop()

        mock_unsubscribe.assert_called_once()
        mock_set_active.assert_called_once_with(False)
        mock_live.return_value.stop.assert_called_once()

    def test_on_event_phase_start(self, display: LiveArtifactDisplay) -> None:
        """phase_start event sets current_phase."""
        event = ArtifactEvent(event_type="phase_start", phase="Researching codebase")
        display._on_event(event)
        assert display.current_phase == "Researching codebase"

    def test_on_event_phase_end(self, display: LiveArtifactDisplay) -> None:
        """phase_end event accumulates elapsed and tracks completed stages."""
        event = ArtifactEvent(
            event_type="phase_end",
            phase="Researching codebase",
            elapsed=5.5,
        )
        display._on_event(event)

        assert display.phase_elapsed == 5.5
        assert "Research" in display.completed_stages
        assert "Researching codebase" in display.completed_phases.get("Research", set())

    def test_on_event_file_start(self, display: LiveArtifactDisplay) -> None:
        """file_start event creates IN_PROGRESS artifact."""
        event = ArtifactEvent(event_type="file_start", path="/test/file.md")
        display._on_event(event)

        assert "/test/file.md" in display.artifacts
        assert display.artifacts["/test/file.md"].status == ArtifactStatus.IN_PROGRESS

    def test_on_event_file_done(self, display: LiveArtifactDisplay) -> None:
        """file_done event transitions artifact to DONE."""
        # First start the file
        display._on_event(ArtifactEvent(event_type="file_start", path="/test/file.md"))
        # Then mark as done
        display._on_event(ArtifactEvent(event_type="file_done", path="/test/file.md"))

        assert display.artifacts["/test/file.md"].status == ArtifactStatus.DONE

    def test_on_event_file_failed(self, display: LiveArtifactDisplay) -> None:
        """file_failed event transitions artifact to FAILED."""
        # First start the file
        display._on_event(ArtifactEvent(event_type="file_start", path="/test/file.md"))
        # Then mark as failed
        display._on_event(ArtifactEvent(event_type="file_failed", path="/test/file.md"))

        assert display.artifacts["/test/file.md"].status == ArtifactStatus.FAILED

    def test_render_stage_pending(self, display: LiveArtifactDisplay) -> None:
        """Pending stage renders with dim circle icon."""
        result = display._render_stage("Execute")
        assert "○" in result
        assert "Execute" in result

    def test_render_stage_active(self, display: LiveArtifactDisplay) -> None:
        """Active stage renders with spinning icon and phase name."""
        display.current_phase = "Researching codebase"
        result = display._render_stage("Research")
        assert "⟳" in result
        assert "Research" in result
        assert "Researching codebase" in result

    def test_render_stage_completed(self, display: LiveArtifactDisplay) -> None:
        """Completed stage renders with checkmark."""
        display.completed_stages.add("Research")
        result = display._render_stage("Research")
        assert "✓" in result
        assert "Research" in result

    def test_render_returns_panel(self, display: LiveArtifactDisplay) -> None:
        """_render() returns a Rich Panel."""
        from rich.panel import Panel

        result = display._render()
        assert isinstance(result, Panel)

    def test_render_with_artifacts(self, display: LiveArtifactDisplay) -> None:
        """_render() includes artifacts in tree."""
        display.artifacts["/test/research.md"] = TrackedArtifact(
            path="/test/research.md", status=ArtifactStatus.DONE
        )

        # Should not raise
        result = display._render()
        assert result is not None
