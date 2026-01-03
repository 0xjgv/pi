---
description: Create git commits with user approval and no Claude attribution
model: haiku
---
# Commit Changes

You are tasked with creating git commits for the changes made during this session.

## Process

1. **Think about what changed:**
   - Review the conversation history and understand what was accomplished
   - Run `git status` to see current changes
   - Run `git diff` to understand the modifications
   - Consider whether changes should be one commit or multiple logical commits

2. **Plan your commit(s):**
   - Identify which files belong together
   - Draft clear, descriptive commit messages
   - Use imperative mood in commit messages
   - Focus on why the changes were made, not just what

3. **Execute the commit(s):**
   - Use `git add` with specific files (never use `-A` or `.`)
   - Create commits with your planned messages
   - Show the result with `git log --oneline -n [number]`

## Important

- Do not include any "Generated with Claude" messages
- Write commit messages as if the user wrote them
- Commits should be authored solely by the user

## Remember

- You have the full context of what was done in this session
- The user trusts your judgment - they asked you to commit
- Keep commits focused and atomic when possible
- Group related changes together
