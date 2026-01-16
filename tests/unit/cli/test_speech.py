"""Tests for speech notifications module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from π.cli.speech import SpeechNotifier
from π.state import ArtifactEvent


class TestSpeechNotifier:
    """Tests for SpeechNotifier class."""

    @pytest.fixture
    def notifier(self) -> SpeechNotifier:
        """Create a fresh SpeechNotifier."""
        return SpeechNotifier()

    def test_initial_state_enabled(self) -> None:
        """SpeechNotifier defaults to enabled."""
        notifier = SpeechNotifier()
        assert notifier._enabled is True
        assert notifier._unsubscribe is None

    def test_initial_state_disabled(self) -> None:
        """SpeechNotifier can be created disabled."""
        notifier = SpeechNotifier(enabled=False)
        assert notifier._enabled is False
        assert notifier._unsubscribe is None

    @patch("π.cli.speech.subscribe_to_artifacts")
    def test_start_subscribes_when_enabled(
        self,
        mock_subscribe: MagicMock,
        notifier: SpeechNotifier,
    ) -> None:
        """start() subscribes to artifact events when enabled."""
        mock_unsubscribe = MagicMock()
        mock_subscribe.return_value = mock_unsubscribe

        notifier.start()

        mock_subscribe.assert_called_once_with(notifier._on_event)
        assert notifier._unsubscribe is mock_unsubscribe

    @patch("π.cli.speech.subscribe_to_artifacts")
    def test_start_skips_subscription_when_disabled(
        self,
        mock_subscribe: MagicMock,
    ) -> None:
        """start() does nothing when disabled."""
        notifier = SpeechNotifier(enabled=False)

        notifier.start()

        mock_subscribe.assert_not_called()
        assert notifier._unsubscribe is None

    @patch("π.cli.speech.subscribe_to_artifacts")
    def test_stop_unsubscribes(
        self,
        mock_subscribe: MagicMock,
        notifier: SpeechNotifier,
    ) -> None:
        """stop() calls unsubscribe and clears reference."""
        mock_unsubscribe = MagicMock()
        mock_subscribe.return_value = mock_unsubscribe

        notifier.start()
        notifier.stop()

        mock_unsubscribe.assert_called_once()
        assert notifier._unsubscribe is None

    def test_stop_handles_none_unsubscribe(self, notifier: SpeechNotifier) -> None:
        """stop() handles case when not started."""
        # Should not raise
        notifier.stop()
        assert notifier._unsubscribe is None

    @patch("π.cli.speech.speak")
    def test_on_event_speaks_on_stage_end(
        self,
        mock_speak: MagicMock,
        notifier: SpeechNotifier,
    ) -> None:
        """_on_event calls speak for stage_end events."""
        event = ArtifactEvent(event_type="stage_end", stage="Research")

        notifier._on_event(event)

        mock_speak.assert_called_once_with("research complete")

    @patch("π.cli.speech.speak")
    def test_on_event_ignores_non_stage_end(
        self,
        mock_speak: MagicMock,
        notifier: SpeechNotifier,
    ) -> None:
        """_on_event ignores non-stage_end events."""
        events = [
            ArtifactEvent(event_type="stage_start", stage="Research"),
            ArtifactEvent(event_type="phase_start", phase="Researching"),
            ArtifactEvent(event_type="phase_end", phase="Researching"),
            ArtifactEvent(event_type="file_start", path="/test.md"),
            ArtifactEvent(event_type="file_done", path="/test.md"),
        ]

        for event in events:
            notifier._on_event(event)

        mock_speak.assert_not_called()

    @patch("π.cli.speech.speak")
    def test_on_event_ignores_stage_end_without_stage(
        self,
        mock_speak: MagicMock,
        notifier: SpeechNotifier,
    ) -> None:
        """_on_event ignores stage_end events without stage field."""
        event = ArtifactEvent(event_type="stage_end", stage=None)

        notifier._on_event(event)

        mock_speak.assert_not_called()

    @patch("π.cli.speech.speak")
    def test_on_event_lowercases_stage_name(
        self,
        mock_speak: MagicMock,
        notifier: SpeechNotifier,
    ) -> None:
        """_on_event lowercases stage name in speech."""
        event = ArtifactEvent(event_type="stage_end", stage="EXECUTE")

        notifier._on_event(event)

        mock_speak.assert_called_once_with("execute complete")
