import asyncio
from pathlib import Path
from sys import argv

from lt.agent import run_agent

cwd = Path(__file__).parent.parent


async def run():
    if len(argv) < 2:
        print("Usage: lt <prompt>")
        return
    await run_agent(prompt=argv[1], cwd=cwd)


def main():
    asyncio.run(run())
