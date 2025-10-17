import asyncio
from sys import argv

from lt.agent import run_agent


async def run():
    if len(argv) < 2:
        print("Usage: lt <prompt>")
        return
    await run_agent(prompt=argv[1])


def main():
    asyncio.run(run())
