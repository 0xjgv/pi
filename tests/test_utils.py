"""Tests for π.utils module."""

import logging

from claude_agent_sdk.types import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    UserMessage,
)

from π.utils import extract_message_content, setup_logging


class TestSetupLogging:
    """Tests for logging configuration."""

    def test_verbose_sets_debug_level(self):
        """Verbose mode should set DEBUG level."""
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        logging.root.setLevel(logging.WARNING)

        setup_logging(verbose=True)
        assert logging.getLogger("π").level == logging.DEBUG

    def test_default_sets_info_level(self):
        """Default mode should set INFO level."""
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        logging.root.setLevel(logging.WARNING)

        setup_logging(verbose=False)
        assert logging.getLogger("π").level == logging.INFO


class TestExtractMessageContent:
    """Tests for message content extraction."""

    def test_extracts_from_result_message(self):
        """Should extract result from ResultMessage."""
        msg = ResultMessage(
            result="test result",
            session_id="123",
            is_error=False,
            subtype="test",
            duration_ms=100,
            duration_api_ms=50,
            num_turns=1,
        )
        assert extract_message_content(msg) == "test result"

    def test_extracts_from_user_message_string(self):
        """Should extract string content from UserMessage."""
        msg = UserMessage(content="hello")
        assert extract_message_content(msg) == "hello"

    def test_extracts_from_assistant_message_blocks(self):
        """Should extract text from AssistantMessage content blocks."""
        msg = AssistantMessage(
            content=[
                TextBlock(text="block 1"),
                TextBlock(text="block 2"),
            ],
            model="claude-sonnet-4-20250514",
        )
        assert extract_message_content(msg) == "block 1\nblock 2"

    def test_returns_none_for_empty_blocks(self):
        """Should return None when no text blocks found."""
        msg = AssistantMessage(content=[], model="claude-sonnet-4-20250514")
        assert extract_message_content(msg) is None
