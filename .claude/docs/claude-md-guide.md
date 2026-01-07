# CLAUDE.md Guide

LLMs are stateless. CLAUDE.md is injected into every conversation—the highest-leverage file in any project.

## Constraints

1. **Target <60 lines** — Never exceed 300.
2. **Universal** — Every line must be relevant to every session.
3. **No code style** — Linters do that.
4. **Pointers, not copies** — Reference files by path.
5. **Deliberate** — Craft every line.

## Template

Copy this and fill in the placeholders. Delete sections that don't apply.

```markdown
# {project-name}

{One sentence: what it is and what it does.}

## Stack

- {language} {version}
- {framework}
- {database (if any)}
- {1-3 key dependencies that affect how you work}

## Structure

{2-5 lines showing where things live}

## Commands

- Build: `{command}`
- Test: `{command}`
- Lint: `{command}`
- {Other essential commands (1-2 max)}

## Docs

- `{path/to/doc.md}` — {what it covers}

## Patterns

- {One critical pattern that affects everything (if any)}
```

### Example (45 lines)

```markdown
# Acme API

REST API for the Acme marketplace, handling orders, inventory, and payments.

## Stack

- Python 3.12
- FastAPI + SQLAlchemy
- PostgreSQL 15
- Stripe SDK, Celery

## Structure

- `src/api/` — Route handlers
- `src/models/` — SQLAlchemy models
- `src/services/` — Business logic
- `src/tasks/` — Celery background jobs

## Commands

- Test: `pytest`
- Lint: `ruff check . && mypy .`
- Dev: `uvicorn src.main:app --reload`

## Docs

- `docs/api.md` — Endpoint reference
- `docs/architecture.md` — System design decisions

## Patterns

- All writes go through service layer, never direct ORM in routes
```

## Progressive Disclosure

For complex projects, use auxiliary docs:

```shell
.claude/docs/
├── architecture.md
├── testing.md
└── conventions.md
```

Reference with one-line descriptions in CLAUDE.md.

## Edge Cases

| Scenario | Approach |
|----------|----------|
| **Bloated CLAUDE.md** | Move content to `.claude/docs/`. Keep essentials, reference the rest. |
| **User wants everything** | Explain trade-off: >300 lines → Claude may miss instructions. Progressive disclosure gives same info with better retention. |
| **Monorepo** | Root-only (universal context) or Root + per-app (app-specific in subdirectories). |

## Anti-Patterns

- ❌ Exhaustive command lists
- ❌ Code snippets showing "how to write a component"
- ❌ Style guides and formatting rules
- ❌ Database schema details
- ❌ Instructions for rare/one-off tasks
- ❌ Duplicating config file information
