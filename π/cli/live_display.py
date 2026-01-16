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

# Default stages (fallback if no stage events received)
_DEFAULT_STAGES = ["Research", "Design", "Execute"]

_STATUS_ICONS: dict[ArtifactStatus, str] = {
    ArtifactStatus.PENDING: "[dim]○[/]",
    ArtifactStatus.IN_PROGRESS: "[cyan]⠋[/]",
    ArtifactStatus.DONE: "[green]✓[/]",
    ArtifactStatus.FAILED: "[red]✗[/]",
}


@dataclass
class TrackedArtifact:
    """A file artifact being tracked during workflow execution."""

    path: str
    status: ArtifactStatus = ArtifactStatus.PENDING


@dataclass
class LiveArtifactDisplay:
    """Manages Rich Live display with artifact tree.

    Subscribes to artifact events and renders a live-updating panel
    showing workflow progress and file artifacts.
    """

    current_phase: str | None = None
    phase_elapsed: float = 0.0
    artifacts: dict[str, TrackedArtifact] = field(default_factory=dict)
    completed_stages: set[str] = field(default_factory=set)
    completed_phases: dict[str, set[str]] = field(default_factory=dict)
    # Dynamic stage tracking from events
    current_stage: str | None = None
    stages_seen: list[str] = field(default_factory=list)
    phase_counts: dict[str, int] = field(default_factory=dict)
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
        if event.event_type == "stage_start":
            # Track stages dynamically as they're entered
            if event.stage and event.stage not in self.stages_seen:
                self.stages_seen.append(event.stage)
            self.current_stage = event.stage
            if event.stage and event.phase_count:
                self.phase_counts[event.stage] = event.phase_count
        elif event.event_type == "stage_end":
            if event.stage:
                self.completed_stages.add(event.stage)
            self.current_stage = None
        elif event.event_type == "phase_start":
            self.current_phase = event.phase
        elif event.event_type == "phase_end":
            self.phase_elapsed += event.elapsed or 0
            # Track completed phases under current stage
            if self.current_stage and event.phase:
                self.completed_phases.setdefault(self.current_stage, set()).add(
                    event.phase
                )
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

    def _render_stage(self, stage: str) -> str:
        """Render a single stage with status icon, sub-phase name, and progress."""
        total = self.phase_counts.get(stage, 1)
        done = len(self.completed_phases.get(stage, set()))
        progress = f" ({done}/{total})" if total > 1 else ""

        # Active stage takes priority over completed status
        if stage == self.current_stage:
            phase_suffix = f": {self.current_phase}" if self.current_phase else ""
            return f"[bold cyan]⟳ {stage}{phase_suffix}{progress}[/]"
        elif stage in self.completed_stages:
            return f"[green]✓ {stage}{progress}[/]"
        else:
            return f"[dim]○ {stage}[/]"

    def _render(self) -> Panel:
        """Render current state as Rich Panel with Tree."""
        # Stage indicator line with status icons (dynamic or fallback)
        stages = self.stages_seen if self.stages_seen else _DEFAULT_STAGES
        stage_parts = [self._render_stage(s) for s in stages]
        phase_line = Text.from_markup(" → ".join(stage_parts))

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
