---
description: Create git commit for implementation changes
model: opus
---
# Create Commit

You are tasked with creating a git commit for implementation changes. You should create a clean, well-formatted commit with an appropriate message.

## Purpose and Scope

**What this command does**:

- Stages relevant files for commit
- Creates a well-formatted commit message
- Executes the git commit
- Reports the commit hash and details

**What this command does NOT do**:

- Push changes to remote (user must do this manually or request it)
- Make additional code changes
- Amend previous commits without explicit request

## Quick Reference

**Typical invocation**:

```bash
/6_create_commit files: src/auth.py, src/login.py | message: Add JWT authentication
```

## Initial Response

When this command is invoked:

1. **Parse the input to identify**:
   - Files to commit (explicit list or "all staged")
   - Proposed commit message
   - Any additional context

2. **Handle different input scenarios**:

   **If NO files or message provided**:

   ```markdown
   I'll help you create a git commit.

   First, let me check the current git status to see what files have been changed...
   ```

   Then run `git status` and `git diff --stat` to understand what's available to commit.

   **If files and message provided**:
   - Proceed immediately to commit process

## Process Steps

### Step 1: Analyze Changes

1. **Check git status**:
   ```bash
   git status
   ```

2. **Review changes**:
   ```bash
   git diff --stat
   git diff  # for detailed changes
   ```

3. **Identify files to commit**:
   - If files specified: verify they exist and have changes
   - If not specified: summarize what's changed and confirm with user

### Step 2: Stage Files

1. **Stage specified files**:
   ```bash
   git add path/to/file1.py path/to/file2.py
   ```

   Or for all changes:
   ```bash
   git add -A
   ```

2. **Verify staging**:
   ```bash
   git status
   ```

### Step 3: Create Commit Message

Follow conventional commit format when appropriate:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code refactoring
- `docs`: Documentation
- `test`: Adding tests
- `chore`: Maintenance

**Guidelines**:
- Subject line: 50 chars max, imperative mood
- Body: Wrap at 72 chars, explain what and why
- Reference issues if applicable

### Step 4: Execute Commit

```bash
git commit -m "$(cat <<'EOF'
<type>(<scope>): <subject>

<body explaining the changes>
EOF
)"
```

### Step 5: Report Results

```markdown
## Commit Created

**Hash**: `abc1234`
**Message**:
```
feat(auth): Add JWT authentication middleware

- Implement token validation in auth middleware
- Add refresh token endpoint
- Update user model with token fields
```

**Files committed**:
- `src/auth/middleware.py`
- `src/auth/tokens.py`
- `src/models/user.py`

**Next steps**:
- Run `git push` to push changes to remote
- Or continue with more changes
```

## Important Guidelines

1. **Don't Push Automatically**:
   - Only commit, don't push unless explicitly requested
   - User controls when to push

2. **Verify Before Committing**:
   - Check that tests pass
   - Ensure only intended files are staged
   - Review the diff if uncertain

3. **Write Good Messages**:
   - Be specific about what changed
   - Explain why, not just what
   - Reference related issues or plans

4. **Handle Sensitive Files**:
   - Never commit `.env`, credentials, or secrets
   - Warn if such files are in the staging area
   - Suggest adding to `.gitignore`

## Error Handling

**If nothing to commit**:
```markdown
No changes detected to commit. The working directory is clean.

If you expected changes, please verify:
- Files were saved after editing
- You're in the correct directory
```

**If commit fails**:
- Check for pre-commit hook failures
- Verify git is configured properly
- Report the specific error

**If sensitive files detected**:
```markdown
Warning: The following files may contain sensitive data:
- `.env`
- `credentials.json`

These should NOT be committed. Would you like me to:
1. Remove them from staging
2. Add them to .gitignore
3. Proceed anyway (not recommended)
```

## Related Commands

- **`5_implement_plan.md`**: Implement changes before committing
- **`2_create_plan.md`**: Plan changes before implementing
