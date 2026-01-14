"""Tests for shared state module."""

from __future__ import annotations

from π.state import (
    ArtifactEvent,
    ArtifactStatus,
    emit_artifact_event,
    get_current_status,
    is_live_display_active,
    set_current_status,
    set_live_display_active,
    subscribe_to_artifacts,
)


class TestSpinnerState:
    """Tests for spinner state management."""

    def test_get_current_status_default_none(self) -> None:
        """get_current_status returns None by default."""
        # Reset by setting to None
        set_current_status(None)
        assert get_current_status() is None

    def test_set_and_get_current_status(self) -> None:
        """set_current_status updates the status."""

        class FakeStatus:
            """Fake Status object for testing."""

        fake = FakeStatus()
        set_current_status(fake)  # type: ignore[arg-type]
        assert get_current_status() is fake
        # Cleanup
        set_current_status(None)

    def test_live_display_active_default_false(self) -> None:
        """is_live_display_active defaults to False."""
        set_live_display_active(False)
        assert is_live_display_active() is False

    def test_set_live_display_active(self) -> None:
        """set_live_display_active updates the flag."""
        set_live_display_active(True)
        assert is_live_display_active() is True
        # Cleanup
        set_live_display_active(False)


class TestArtifactStatus:
    """Tests for ArtifactStatus enum."""

    def test_all_statuses_defined(self) -> None:
        """All expected statuses exist."""
        assert ArtifactStatus.PENDING.value == "pending"
        assert ArtifactStatus.IN_PROGRESS.value == "in_progress"
        assert ArtifactStatus.DONE.value == "done"
        assert ArtifactStatus.FAILED.value == "failed"

    def test_status_count(self) -> None:
        """Exactly 4 statuses are defined."""
        assert len(ArtifactStatus) == 4


class TestArtifactEvent:
    """Tests for ArtifactEvent dataclass."""

    def test_minimal_event(self) -> None:
        """Event requires only event_type."""
        event = ArtifactEvent(event_type="phase_start")
        assert event.event_type == "phase_start"
        assert event.path is None
        assert event.phase is None
        assert event.doc_type is None
        assert event.elapsed is None

    def test_full_event(self) -> None:
        """Event accepts all optional fields."""
        event = ArtifactEvent(
            event_type="file_done",
            path="/test/file.md",
            phase="Researching codebase",
            doc_type="research",
            elapsed=1.5,
        )
        assert event.event_type == "file_done"
        assert event.path == "/test/file.md"
        assert event.phase == "Researching codebase"
        assert event.doc_type == "research"
        assert event.elapsed == 1.5

    def test_event_types(self) -> None:
        """All 5 event types can be created."""
        types = ["phase_start", "phase_end", "file_start", "file_done", "file_failed"]
        for event_type in types:
            event = ArtifactEvent(event_type=event_type)
            assert event.event_type == event_type


class TestPubSub:
    """Tests for artifact pub/sub system."""

    def test_subscribe_returns_unsubscribe(self) -> None:
        """subscribe_to_artifacts returns an unsubscribe function."""
        events: list[ArtifactEvent] = []
        unsubscribe = subscribe_to_artifacts(events.append)
        assert callable(unsubscribe)
        # Cleanup
        unsubscribe()

    def test_unsubscribe_removes_listener(self) -> None:
        """unsubscribe function removes the listener."""
        events: list[ArtifactEvent] = []
        unsubscribe = subscribe_to_artifacts(events.append)

        # Emit before unsubscribe
        emit_artifact_event(ArtifactEvent(event_type="test1"))
        assert len(events) == 1

        unsubscribe()

        # Emit after unsubscribe - should not be received
        emit_artifact_event(ArtifactEvent(event_type="test2"))
        assert len(events) == 1

    def test_emit_calls_all_listeners(self) -> None:
        """emit_artifact_event calls all subscribed listeners."""
        events1: list[ArtifactEvent] = []
        events2: list[ArtifactEvent] = []
        unsub1 = subscribe_to_artifacts(events1.append)
        unsub2 = subscribe_to_artifacts(events2.append)

        event = ArtifactEvent(event_type="test")
        emit_artifact_event(event)

        assert events1 == [event]
        assert events2 == [event]

        # Cleanup
        unsub1()
        unsub2()

    def test_multiple_subscribers(self) -> None:
        """Multiple subscribers each receive events independently."""
        # Create separate lists to avoid lambda closures
        events0: list[ArtifactEvent] = []
        events1: list[ArtifactEvent] = []
        events2: list[ArtifactEvent] = []
        all_events = [events0, events1, events2]

        unsub0 = subscribe_to_artifacts(events0.append)
        unsub1 = subscribe_to_artifacts(events1.append)
        unsub2 = subscribe_to_artifacts(events2.append)

        emit_artifact_event(ArtifactEvent(event_type="test"))

        # Each subscriber received the event
        assert len(events0) == 1
        assert len(events1) == 1
        assert len(events2) == 1
        assert all(len(e) == 1 for e in all_events)

        # Cleanup
        unsub0()
        unsub1()
        unsub2()
