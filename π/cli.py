import asyncio
from pathlib import Path
from sys import argv

from π.utils import prevent_sleep
from π.workflow import run_workflow

cwd = Path(__file__).parent.parent


async def run():
    if len(argv) < 2:
        print('Usage: π "<prompt>"')
        return
    result = await run_workflow(
        prompt=argv[1].strip('"'),
        cwd=cwd,
    )
    print(f"Result: {result}")


@prevent_sleep
def main():
    asyncio.run(run())
