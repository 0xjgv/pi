"""Integration tests for session state management."""


class TestSessionStateIntegration:
    """Integration tests for session state management."""

    def test_session_persists_across_workflow_calls(self):
        """Session state should persist across multiple workflow calls."""
        from π.workflow import Command, ExecutionContext
        from π.workflow.context import _ctx, get_ctx

        # Clear any existing context
        try:
            _ctx.set(ExecutionContext())
        except LookupError:
            pass

        ctx = get_ctx()
        ctx.session_ids[Command.RESEARCH_CODEBASE] = "test-session"

        # Retrieve again - should be same context
        retrieved = get_ctx()
        assert retrieved.session_ids.get(Command.RESEARCH_CODEBASE) == "test-session"

    def test_command_map_built_correctly(self):
        """Command map should be built from actual command files."""
        from π.workflow import COMMAND_MAP, Command

        # Should have entries for commands that have files
        # (depends on actual .claude/commands/ content)
        assert isinstance(COMMAND_MAP, dict)

        # All values should be slash commands
        for cmd, value in COMMAND_MAP.items():
            assert isinstance(cmd, Command)
            assert value.startswith("/")
