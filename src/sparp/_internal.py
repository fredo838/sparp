import asyncio
from typing import Any


class DoneSentinel:
    """Sentinel used to signal to worker tasks that the input queue is exhausted."""

    pass


class ResultQueues:
    """Async queues for collecting results during processing."""

    def __init__(self) -> None:
        self.success: asyncio.Queue[Any] = asyncio.Queue()
        self.failed: asyncio.Queue[Any] = asyncio.Queue()
        self.max_retries_soft_fail_reached: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.max_retries_timeout_reached: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    @staticmethod
    def _drain(q: asyncio.Queue[Any]) -> list[Any]:
        """Collects all items currently in a queue without blocking."""
        items: list[Any] = []
        while not q.empty():
            items.append(q.get_nowait())
        return items

    def drain_all(self) -> dict[str, list[Any]]:
        """Drains all result queues into a dictionary of lists."""
        return {
            "success": self._drain(self.success),
            "failed": self._drain(self.failed),
            "max_retries_soft_fail_reached": self._drain(self.max_retries_soft_fail_reached),
            "max_retries_timeout_reached": self._drain(self.max_retries_timeout_reached),
        }
