"""Live artifact tree display for workflow progress."""

from collections.abc import Callable
from dataclasses import dataclass, field

from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree

from π.hooks.utils import compact_path
from π.state import (
    ArtifactEvent,
    ArtifactStatus,
    set_live_display_active,
    subscribe_to_artifacts,
)


@dataclass
class TrackedArtifact:
    """A file artifact being tracked during workflow execution."""

    path: str
    status: ArtifactStatus = ArtifactStatus.PENDING
    elapsed: float | None = None


@dataclass
class LiveArtifactDisplay:
    """Manages Rich Live display with artifact tree.

    Subscribes to artifact events and renders a live-updating panel
    showing workflow progress and file artifacts.
    """

    current_phase: str | None = None
    phase_elapsed: float = 0.0
    artifacts: dict[str, TrackedArtifact] = field(default_factory=dict)
    _live: Live | None = None
    _unsubscribe: Callable[[], None] | None = None

    def start(self) -> None:
        """Start the live display and subscribe to events."""
        set_live_display_active(True)
        self._unsubscribe = subscribe_to_artifacts(self._on_event)
        self._live = Live(self._render(), refresh_per_second=4, console=None)
        self._live.start()

    def stop(self) -> None:
        """Stop display and unsubscribe."""
        if self._live:
            self._live.stop()
        if self._unsubscribe:
            self._unsubscribe()
        set_live_display_active(False)

    def _on_event(self, event: ArtifactEvent) -> None:
        """Handle artifact events."""
        if event.event_type == "phase_start":
            self.current_phase = event.phase
        elif event.event_type == "phase_end":
            self.phase_elapsed += event.elapsed or 0
        elif event.event_type == "file_start" and event.path:
            self.artifacts[event.path] = TrackedArtifact(
                path=event.path, status=ArtifactStatus.IN_PROGRESS
            )
        elif event.event_type == "file_done" and event.path in self.artifacts:
            self.artifacts[event.path].status = ArtifactStatus.DONE
        elif event.event_type == "file_failed" and event.path in self.artifacts:
            self.artifacts[event.path].status = ArtifactStatus.FAILED

        if self._live:
            self._live.update(self._render())

    def _render(self) -> Panel:
        """Render current state as Rich Panel with Tree."""
        # Phase indicator line
        phases = ["Research", "Design", "Execute"]
        phase_parts = []
        for p in phases:
            if p == self.current_phase:
                phase_parts.append(f"[bold cyan]{p}[/]")
            else:
                phase_parts.append(f"[dim]{p}[/]")
        phase_line = Text.from_markup(" → ".join(phase_parts))

        # Build artifact tree
        tree = Tree("[bold]Artifacts[/]")
        if self.artifacts:
            for path, artifact in self.artifacts.items():
                icon = _STATUS_ICONS[artifact.status]
                tree.add(f"{icon} {compact_path(path)}")
        else:
            tree.add("[dim]waiting...[/]")

        # Combine into panel using Group for proper rendering
        content = Group(phase_line, Text(""), tree)

        return Panel(
            content,
            title="[heading]π Workflow[/heading]",
            border_style="cyan",
        )


_STATUS_ICONS: dict[ArtifactStatus, str] = {
    ArtifactStatus.PENDING: "[dim]○[/]",
    ArtifactStatus.IN_PROGRESS: "[cyan]⠋[/]",
    ArtifactStatus.DONE: "[green]✓[/]",
    ArtifactStatus.FAILED: "[red]✗[/]",
}
