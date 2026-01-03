#!/usr/bin/env python3
"""Example: Building a Scam Phone Number App with State Machine.

This example demonstrates how to use the TaskStateMachine to build
a complex application: a scam phone number tracker that syncs across users.

Usage:
    # Start fresh
    python -m π.workflow.examples.scam_phone_app

    # Resume from checkpoint
    python -m π.workflow.examples.scam_phone_app --resume
"""

from __future__ import annotations

import argparse
import logging

from rich.console import Console
from rich.table import Table

from π.workflow.executor import ExecutorConfig, TaskExecutor
from π.workflow.state_machine import Task, TaskStateMachine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
console = Console()

# Project identifier
PROJECT_ID = "scam-phone-tracker"

# The ultimate objective
OBJECTIVE = """
Build a mobile/web application for storing and sharing scamming phone numbers.

Key features:
1. Users can report phone numbers as scams with details (type of scam, date, notes)
2. Data syncs across all users who have the app installed
3. When a user receives a call, the app checks against the shared database
4. Users can upvote/downvote reports to validate accuracy
5. Privacy-preserving design (no personal data collected)

Technical requirements:
- Backend API for data synchronization
- Mobile apps (iOS/Android) or cross-platform solution
- Real-time sync capability
- Scalable database for phone number lookups
- Rate limiting to prevent abuse
"""


def get_predefined_tasks() -> list[dict]:
    """Get predefined task breakdown for the scam phone app.

    This shows how to manually define tasks when you want precise control
    over the execution plan. Alternatively, use executor.plan_tasks() to
    let AI decompose the objective automatically.
    """
    return [
        # Phase 1: Research & Architecture
        {
            "id": "task-1-research",
            "name": "Research existing solutions",
            "description": (
                "Research existing scam phone number databases and apps. "
                "Analyze: Truecaller, Hiya, RoboKiller, FTC complaint database. "
                "Document findings on features, APIs, data models, and sync mechanisms."
            ),
            "priority": "critical",
            "dependencies": [],
            "tags": ["research", "phase-1"],
        },
        {
            "id": "task-2-architecture",
            "name": "Design system architecture",
            "description": (
                "Design the overall system architecture including: "
                "- Backend service architecture (API, database, sync) "
                "- Data model for phone numbers, reports, users "
                "- Sync protocol design (real-time vs eventual consistency) "
                "- Security and privacy considerations "
                "Output: Architecture document with diagrams"
            ),
            "priority": "critical",
            "dependencies": ["task-1-research"],
            "tags": ["architecture", "phase-1"],
        },
        # Phase 2: Backend Development
        {
            "id": "task-3-database",
            "name": "Design database schema",
            "description": (
                "Design and implement the database schema: "
                "- Phone numbers table with normalization "
                "- Reports table with user references "
                "- Votes/validation table "
                "- Sync metadata for conflict resolution "
                "Consider using PostgreSQL with proper indexing for phone lookups."
            ),
            "priority": "high",
            "dependencies": ["task-2-architecture"],
            "tags": ["backend", "database", "phase-2"],
        },
        {
            "id": "task-4-api",
            "name": "Build REST API",
            "description": (
                "Implement the REST API endpoints: "
                "- POST /reports - Submit a scam report "
                "- GET /check/{phone} - Check if number is reported "
                "- POST /votes - Upvote/downvote a report "
                "- GET /sync - Get changes since timestamp "
                "- POST /sync - Push local changes "
                "Include rate limiting, authentication, and input validation."
            ),
            "priority": "high",
            "dependencies": ["task-3-database"],
            "tags": ["backend", "api", "phase-2"],
        },
        {
            "id": "task-5-sync",
            "name": "Implement sync protocol",
            "description": (
                "Implement the data synchronization system: "
                "- Conflict resolution strategy (last-write-wins or merge) "
                "- Delta sync to minimize data transfer "
                "- Offline queue for pending changes "
                "- WebSocket support for real-time updates "
                "Test with multiple clients syncing simultaneously."
            ),
            "priority": "high",
            "dependencies": ["task-4-api"],
            "tags": ["backend", "sync", "phase-2"],
        },
        # Phase 3: Mobile/Frontend Development
        {
            "id": "task-6-mobile-setup",
            "name": "Set up mobile project",
            "description": (
                "Initialize the mobile app project: "
                "- Choose framework (React Native or Flutter recommended) "
                "- Set up project structure and dependencies "
                "- Configure build pipeline for iOS and Android "
                "- Set up development environment and simulators"
            ),
            "priority": "normal",
            "dependencies": ["task-4-api"],
            "tags": ["mobile", "setup", "phase-3"],
        },
        {
            "id": "task-7-mobile-ui",
            "name": "Build mobile UI",
            "description": (
                "Implement the mobile app user interface: "
                "- Home screen with recent reports "
                "- Report submission form "
                "- Phone number search/check "
                "- Report detail view with voting "
                "- Settings screen "
                "Follow platform design guidelines (Material/iOS HIG)."
            ),
            "priority": "normal",
            "dependencies": ["task-6-mobile-setup"],
            "tags": ["mobile", "ui", "phase-3"],
        },
        {
            "id": "task-8-caller-id",
            "name": "Implement caller ID integration",
            "description": (
                "Integrate with phone system for caller identification: "
                "- iOS: CallKit CallDirectoryExtension "
                "- Android: Phone app integration / overlay "
                "- Background sync to update local blocklist "
                "- Notification when scam call detected"
            ),
            "priority": "normal",
            "dependencies": ["task-7-mobile-ui", "task-5-sync"],
            "tags": ["mobile", "integration", "phase-3"],
        },
        # Phase 4: Testing & Polish
        {
            "id": "task-9-testing",
            "name": "Comprehensive testing",
            "description": (
                "Implement and run comprehensive tests: "
                "- Unit tests for API and business logic "
                "- Integration tests for sync protocol "
                "- End-to-end tests for mobile flows "
                "- Load testing for database lookups "
                "- Security testing (injection, auth bypass)"
            ),
            "priority": "high",
            "dependencies": ["task-8-caller-id"],
            "tags": ["testing", "phase-4"],
        },
        {
            "id": "task-10-deploy",
            "name": "Deploy and launch",
            "description": (
                "Deploy the application: "
                "- Set up production infrastructure "
                "- Configure monitoring and alerting "
                "- Submit to App Store and Play Store "
                "- Create landing page and documentation "
                "- Plan for user onboarding"
            ),
            "priority": "normal",
            "dependencies": ["task-9-testing"],
            "tags": ["deployment", "phase-4"],
        },
    ]


def print_task_table(tasks: list[Task]) -> None:
    """Print tasks in a formatted table."""
    table = Table(title="Task Breakdown")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Status", style="green")
    table.add_column("Priority", style="yellow")
    table.add_column("Dependencies", style="dim")

    for task in tasks:
        deps = ", ".join(task.dependencies) if task.dependencies else "-"
        table.add_row(
            task.id,
            task.name,
            task.status.value,
            task.priority.value,
            deps,
        )

    console.print(table)


def print_progress(executor: TaskExecutor) -> None:
    """Print execution progress."""
    console.print("\n" + "=" * 60)
    console.print(executor.get_status_report())
    console.print("=" * 60 + "\n")


def on_task_complete(task: Task) -> None:
    """Callback when a task completes."""
    status_emoji = "✅" if task.status.value == "completed" else "❌"
    console.print(f"\n{status_emoji} Task completed: [bold]{task.name}[/bold]")
    if task.result:
        console.print(f"   Output: {task.result.output[:200]}...")
        if task.result.artifacts:
            console.print(f"   Artifacts: {', '.join(task.result.artifacts)}")


def run_fresh() -> None:
    """Start a fresh execution of the scam phone app project."""
    console.print("[bold cyan]Starting Scam Phone App Project[/bold cyan]\n")

    # Create executor with state machine
    executor = TaskExecutor.create(
        PROJECT_ID,
        config=ExecutorConfig(
            checkpoint_interval=2,  # Checkpoint every 2 tasks
            pause_on_failure=True,
        ),
    )

    # Set the objective
    executor.set_objective(OBJECTIVE)
    console.print("[green]✓[/green] Objective set\n")

    # Option 1: Use predefined tasks (shown here for clarity)
    console.print("[bold]Using predefined task breakdown...[/bold]\n")
    tasks = executor.plan_tasks(custom_tasks=get_predefined_tasks())

    # Option 2: Let AI decompose (uncomment to use)
    # console.print("[bold]AI is decomposing the objective into tasks...[/bold]\n")
    # tasks = executor.plan_tasks(context="Target: iOS and Android with shared backend")

    print_task_table(tasks)

    # Run execution
    console.print("\n[bold cyan]Starting Execution[/bold cyan]\n")
    result = executor.run_until_complete(
        max_tasks=3,  # Limit for demo purposes
        on_task_complete=on_task_complete,
    )

    print_progress(executor)
    console.print("\n[bold]Execution Summary:[/bold]")
    console.print(f"  Tasks run: {result['tasks_run']}")
    console.print(f"  State: {result['state']}")
    console.print(f"  Complete: {result['is_complete']}")


def run_resume() -> None:
    """Resume execution from saved state."""
    console.print("[bold cyan]Resuming Scam Phone App Project[/bold cyan]\n")

    try:
        executor = TaskExecutor.resume(PROJECT_ID)
    except FileNotFoundError:
        console.print("[red]No saved state found. Run without --resume first.[/red]")
        return

    print_progress(executor)

    # Continue execution
    result = executor.run_until_complete(
        max_tasks=3,  # Limit for demo
        on_task_complete=on_task_complete,
    )

    print_progress(executor)
    console.print("\n[bold]Execution Summary:[/bold]")
    console.print(f"  Tasks run: {result['tasks_run']}")
    console.print(f"  State: {result['state']}")
    console.print(f"  Complete: {result['is_complete']}")


def run_interactive() -> None:
    """Run in interactive mode with manual task control."""
    console.print("[bold cyan]Interactive Mode: Scam Phone App[/bold cyan]\n")

    # Load or create
    machine = TaskStateMachine.load_or_create(PROJECT_ID)

    if machine.state.value == "uninitialized":
        machine.set_objective(OBJECTIVE)
        machine.decompose_goal(get_predefined_tasks())
        console.print("[green]✓[/green] Project initialized\n")

    while True:
        print_progress(TaskExecutor(machine))

        console.print("\nCommands:")
        console.print("  [n]ext - Execute next task")
        console.print("  [s]kip <id> - Skip a task")
        console.print("  [p]ause - Pause execution")
        console.print("  [c]heckpoint - Create checkpoint")
        console.print("  [q]uit - Save and exit")

        cmd = input("\n> ").strip().lower()

        if cmd == "n" or cmd == "next":
            executor = TaskExecutor(machine)
            task = executor.execute_next_task()
            if task:
                on_task_complete(task)
            else:
                console.print("[yellow]No tasks available[/yellow]")

        elif cmd.startswith("s ") or cmd.startswith("skip "):
            task_id = cmd.split(" ", 1)[1]
            machine.skip_task(task_id, reason="User skipped")
            console.print(f"[yellow]Skipped: {task_id}[/yellow]")

        elif cmd == "p" or cmd == "pause":
            machine.pause(reason="User paused")
            console.print("[yellow]Execution paused[/yellow]")

        elif cmd == "c" or cmd == "checkpoint":
            cp = machine.checkpoint(notes="Manual checkpoint")
            console.print(f"[green]Checkpoint created: {cp.id}[/green]")

        elif cmd == "q" or cmd == "quit":
            machine.save()
            console.print("[green]State saved. Goodbye![/green]")
            break

        else:
            console.print("[red]Unknown command[/red]")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Scam Phone App - State Machine Example"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from saved state",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run in interactive mode",
    )
    args = parser.parse_args()

    if args.interactive:
        run_interactive()
    elif args.resume:
        run_resume()
    else:
        run_fresh()


if __name__ == "__main__":
    main()
