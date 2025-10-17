import json

from claude_agent_sdk.types import (
    AssistantMessage,
    Message,
    ResultMessage,
    SystemMessage,
    TextBlock,
)


def display_message(msg: Message) -> None:
    """Standardized message display function."""
    if isinstance(msg, AssistantMessage):
        for block in msg.content:
            if isinstance(block, TextBlock):
                print(block.text)
    elif isinstance(msg, ResultMessage):
        print("[Done]")
    elif isinstance(msg, SystemMessage):
        # Iterate over the attributes of the SystemMessage
        print(f"[System] {json.dumps(msg.data, indent=2)}")
    else:
        print(
            f"[Error] Unknown message type: {type(msg)}", file=__import__("sys").stderr
        )
        print(msg, file=__import__("sys").stderr)
