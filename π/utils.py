"""Utility functions for the π CLI."""

import logging

from claude_agent_sdk.types import (
    AssistantMessage,
    Message,
    ResultMessage,
    TextBlock,
    UserMessage,
)


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging for the π CLI.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO level

    Returns:
        Configured logger instance
    """
    level = logging.DEBUG if verbose else logging.INFO

    # Configure root logger with basic format (keeps third-party libs at WARNING)
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        level=logging.WARNING,
        force=True,
    )

    # Configure our logger specifically
    logger = logging.getLogger("π")
    logger.setLevel(level)

    # Silence noisy third-party loggers
    for name in ("httpcore", "httpx", "claude_agent_sdk"):
        logging.getLogger(name).setLevel(logging.WARNING)

    return logger


def extract_message_content(msg: Message | ResultMessage) -> str | None:
    """Extract text content from a Claude SDK message.

    Args:
        msg: A Message or ResultMessage from the Claude SDK

    Returns:
        Extracted text content, or None if no text found
    """
    if isinstance(msg, ResultMessage):
        return msg.result
    if isinstance(msg, (UserMessage, AssistantMessage)):
        content = msg.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, TextBlock):
                    texts.append(block.text)
            return "\n".join(texts) if len(texts) > 0 else None
        return None
    return None
