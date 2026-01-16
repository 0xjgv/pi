"""Speech notifications for workflow stage transitions."""

from typing import TYPE_CHECKING

from π.state import ArtifactEvent, subscribe_to_artifacts
from π.utils import speak

if TYPE_CHECKING:
    from collections.abc import Callable


class SpeechNotifier:
    """Announces workflow stage transitions via text-to-speech."""

    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = enabled
        self._unsubscribe: Callable[[], None] | None = None

    def start(self) -> None:
        """Subscribe to artifact events."""
        if self._enabled:
            self._unsubscribe = subscribe_to_artifacts(self._on_event)

    def stop(self) -> None:
        """Unsubscribe from events."""
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    def _on_event(self, event: ArtifactEvent) -> None:
        """Announce stage completions."""
        if event.event_type == "stage_end" and event.stage:
            speak(f"{event.stage.lower()} complete")
