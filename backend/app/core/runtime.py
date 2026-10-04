import asyncio
import sys


def loop_factory() -> asyncio.AbstractEventLoop:
    """Psycopg async connections require SelectorEventLoop on Windows."""
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()
