---
description: Write or improve CLAUDE.md file
model: opus
---
# Write or Improve CLAUDE.md

Help users create or improve their CLAUDE.md file.

**Reference:** Read `.claude/docs/claude-md-guide.md` for principles, constraints, and template.

## Initial Response

1. **Check if CLAUDE.md exists** in the repository root
2. Respond based on what you find:

**If exists:**

```markdown
I see you already have a CLAUDE.md. Let me review it.

[Summarize in 2-3 bullets]

**What would you like to improve?**
- Too long/verbose
- Missing critical information  
- Outdated content
- Restructure entirely
```

**If not:**

```markdown
No CLAUDE.md found. I'll help you create one.

**What's the most important thing Claude should know about this project?**

(The thing that, if misunderstood, causes the most problems.)
```

Then wait for the user's response.

## Process

### Step 1: Discovery

Use the research pattern from `commands/dev/1_research_codebase.md`:

- Spawn `codebase-locator` for project structure, config files, key directories
- Spawn `codebase-analyzer` for build tools, test runners, patterns
- Spawn `codebase-pattern-finder` for conventions

**Key files to find:** `package.json`, `pyproject.toml`, `Cargo.toml`, `README.md`, `docs/`, `agent_docs/`

**Extract:** Tech stack, versions, build/test/lint commands, project structure, critical patterns.

### Step 2: Draft

Read `.claude/docs/claude-md-guide.md` for the template and constraints.

Present for review:

```markdown
Here's my draft CLAUDE.md:

---
[Draft following template from guide]
---

**Before I finalize:**
1. Is the project description accurate?
2. Are the commands correct?
3. Anything critical I missed?
4. Anything that shouldn't be there?
```

### Step 3: Refine & Write

Iterate based on feedback. Once approved, write to `CLAUDE.md` in the repository root.

Report final line count to confirm it meets the <60 target.
