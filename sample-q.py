# conversation_queue_async.py
import asyncio
import random


async def fake_api_call(name: str, message: str) -> str:
    """Simulate an async reply with some latency."""
    await asyncio.sleep(random.uniform(0.2, 0.6))
    return f"{name} replying to '{message}'"


async def user(name: str, inbox: asyncio.Queue, outbox: asyncio.Queue):
    """Each user waits for messages, replies asynchronously, and sends them out."""
    while True:
        message = await inbox.get()  # wait for next message
        if message is None:  # termination signal
            outbox.put_nowait(None)
            break

        print(f"{name} received: {message}")
        reply = await fake_api_call(name, message)
        print(f"{name} → {reply}")
        await outbox.put(reply)


async def main():
    # Two mailboxes (queues)
    alice_inbox = asyncio.Queue()
    bob_inbox = asyncio.Queue()

    # Launch both agents concurrently
    alice_task = asyncio.create_task(user("Alice", alice_inbox, bob_inbox))
    bob_task = asyncio.create_task(user("Bob", bob_inbox, alice_inbox))

    # Start conversation
    await bob_inbox.put("Hi Bob!")  # initial message from Alice

    # Run conversation for a few turns
    for _ in range(5):
        await asyncio.sleep(0.7)  # let replies flow

    # Stop both users gracefully
    await alice_inbox.put(None)
    await bob_inbox.put(None)

    await asyncio.gather(alice_task, bob_task)


if __name__ == "__main__":
    asyncio.run(main())
