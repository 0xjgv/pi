#!/usr/bin/env python3
"""Validate structured output support in claude-agent-sdk."""

import asyncio

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, query
from claude_agent_sdk.types import ResultMessage

from π.schemas import StageOutput


async def test_with_client(options: ClaudeAgentOptions) -> dict:
    """Test structured output with ClaudeSDKClient."""
    result = {"method": "ClaudeSDKClient", "structured_output": None, "text": None}

    async with ClaudeSDKClient(options=options) as client:
        await client.query(
            prompt='Reply with exactly: {"status": "complete", "summary": "hello"}'
        )

        async for msg in client.receive_response():
            if type(msg).__name__ == "ResultMessage":
                result["structured_output"] = getattr(msg, "structured_output", None)
                result["text"] = getattr(msg, "result", None)

    return result


async def test_with_query(options: ClaudeAgentOptions) -> dict:
    """Test structured output with query() function."""
    result = {"method": "query()", "structured_output": None, "text": None}

    async for msg in query(
        prompt='Reply with exactly: {"status": "complete", "summary": "hello"}',
        options=options,
    ):
        if type(msg).__name__ == "ResultMessage":
            result["structured_output"] = getattr(msg, "structured_output", None)
            result["text"] = getattr(msg, "result", None)

    return result


async def test_structured_output():
    """Test if structured output is working with the SDK."""
    print("=" * 60)
    print("Structured Output Validation")
    print("=" * 60)

    # Check SDK version
    import claude_agent_sdk

    version = getattr(claude_agent_sdk, "__version__", "unknown")
    print(f"\n1. SDK Version: {version}")

    # Check ResultMessage has structured_output
    has_attr = hasattr(
        ResultMessage, "structured_output"
    ) or "structured_output" in dir(ResultMessage)
    print(f"2. ResultMessage.structured_output exists: {has_attr}")

    # Check schema generation
    stage_schema = StageOutput.model_json_schema()
    print(
        f"3. StageOutput schema generated: {len(stage_schema.get('properties', {}))} properties"
    )

    # Create options with output_format
    options = ClaudeAgentOptions(
        permission_mode="acceptEdits",
        system_prompt="You must respond ONLY with valid JSON matching the schema. No other text.",
        output_format={
            "type": "json_schema",
            "json_schema": {
                "name": "StageOutput",
                "schema": stage_schema,
            },
        },
    )
    print("4. ClaudeAgentOptions created with output_format")

    # Test both methods
    print("\n5. Testing ClaudeSDKClient:")
    try:
        client_result = await test_with_client(options)
        print(f"   structured_output: {client_result['structured_output']}")
        print(
            f"   text result: {client_result['text'][:100] if client_result['text'] else None}..."
        )
    except Exception as e:
        print(f"   Error: {e}")

    print("\n6. Testing query() function:")
    try:
        query_result = await test_with_query(options)
        print(f"   structured_output: {query_result['structured_output']}")
        print(
            f"   text result: {query_result['text'][:100] if query_result['text'] else None}..."
        )
    except Exception as e:
        print(f"   Error: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print("Both ClaudeSDKClient and query() use the same underlying")
    print("transport. If structured_output is None for both, the SDK")
    print("isn't enforcing structured output at the CLI level.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_structured_output())
