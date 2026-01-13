---
name: workflow (π)
description: Orchestrate autonomous research -> design -> execute workflows. Use when given a development task that requires understanding the codebase, planning, and implementing changes.
---

# Autonomous Development Workflow

Run stages in isolated SDK sessions with logging.

**Prerequisite**: Project must have `/1_research_codebase`, `/2_create_plan`, and `/5_implement_plan` commands.

## Usage

```bash
python ~/.claude/skills/workflow/scripts/workflow.py "OBJECTIVE" [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `--stage` | `research`, `design`, `execute`, or `all` (default: all) |
| `--research-doc PATH` | Skip research, use existing document |
| `--plan-doc PATH` | Skip design, use existing plan |
| `-v` | Verbose logging to console |

## Examples

```bash
# Full workflow
python ~/.claude/skills/workflow/scripts/workflow.py "Add dark mode"

# Research only
python ~/.claude/skills/workflow/scripts/workflow.py "Investigate bug" --stage research

# Skip to execute with existing plan
python ~/.claude/skills/workflow/scripts/workflow.py "Add feature" --stage execute --plan-doc thoughts/shared/plans/2024-01-13-feature.md
```

## Exit Codes

- `0` - SUCCESS: Stage(s) completed
- `1` - ERROR: Stage failed with exception
- `2` - EARLY_EXIT: Research determined no implementation needed

## Logs

Logs written to `.π/logs/workflow-*.log` (7-day retention).

## Progress Reporting

After running, report:

```markdown
=== Workflow Progress ===
Objective: {objective}

[✓] Research - {output_path or "skipped"}
[✓] Design - {output_path or "skipped"}
[→] Execute - {status}
=========================
```

## Error Handling

If the script returns `status: "error"`, report the error message and ask the user how to proceed.
