import asyncio
import time
import datetime
from collections.abc import Sized
from typing import Callable, Iterable, Any, Awaitable, cast

import aiohttp

from ._exceptions import SPARPStopSignal, HardFailStop, SoftFailStop, TimeoutFailStop, MaxRetriesStop
from ._types import ResponseState, SparpStats, SparpResult
from ._config import Callbacks, StopConditions
from ._internal import DoneSentinel, ResultQueues


async def default_parse_response(request_dict: dict[str, Any], response: aiohttp.ClientResponse) -> Any:
    """The default parser that returns basic response metadata and text body."""
    return {
        "input": request_dict,
        "status": response.status,
        "text": await response.text(),
        "headers": dict(response.headers),
    }


class SPARP:
    """Simple Parallel Asynchronous Requests for Python (SPARP).

    Coordinates concurrent HTTP requests with configurable retries,
    stop conditions, and result parsing.
    """

    def __init__(
        self,
        inspect_response: Callable[[aiohttp.ClientResponse], ResponseState],
        callbacks: Callbacks | None = None,
        concurrency: int = 100,
        max_retries_when_soft_fail: int = 20,
        max_retries_on_timeout: int = 20,
        parse_response_fn: Callable[[dict[str, Any], aiohttp.ClientResponse], Awaitable[Any]] = default_parse_response,
        stop_conditions: StopConditions | None = None,
        input_buffer_size: int = 100,
        show_progress_bar: bool = False,
        timeout_s: float = 30.0,
        progress_bar_requests_threshold: int = 1,
        progress_bar_time_threshold: datetime.timedelta = datetime.timedelta(seconds=0.5),
        ssl_verify: bool = True,
    ) -> None:
        """Initialises the SPARP engine with configuration."""
        if progress_bar_time_threshold.total_seconds() == 0:
            raise ValueError("progress_bar_time_threshold should not be zero seconds")

        self.concurrency = concurrency
        self.max_retries_when_soft_fail = max_retries_when_soft_fail
        self.max_retries_on_timeout = max_retries_on_timeout
        self.inspect_response = inspect_response
        self.parse_response_fn = parse_response_fn
        self.callbacks = callbacks if callbacks is not None else Callbacks()
        self.stop_conditions = stop_conditions if stop_conditions is not None else StopConditions()
        self.input_buffer_size = input_buffer_size
        self.show_progress_bar = show_progress_bar
        self.timeout_s = timeout_s
        self.progress_bar_requests_threshold = progress_bar_requests_threshold
        self.progress_bar_time_threshold = progress_bar_time_threshold
        self.ssl_verify = ssl_verify

        # Runtime state — populated by _main()
        self.input_collection: Iterable[dict[str, Any]] = []
        self.estimated_input_collection_size: int | None = None
        self.seen: int = 0
        self.success_count: int = 0
        self.failed_count: int = 0
        self.max_retries_soft_reached_count: int = 0
        self.max_retries_timeout_reached_count: int = 0
        self.retries_by_soft_fail: int = 0
        self.retries_by_timeout: int = 0
        self.start_time: float = 0.0
        self.input_queue: asyncio.Queue[dict[str, Any] | DoneSentinel] = asyncio.Queue()
        self.queues: ResultQueues = ResultQueues()
        self.iterator_exhausted: asyncio.Event = asyncio.Event()

    def _init_runtime_state(
        self,
        input_collection: Iterable[dict[str, Any]],
        estimated_input_collection_size: int | None,
    ) -> None:
        """Resets all mutable runtime state for a fresh run."""
        # Auto-detect size from sized iterables (e.g. lists)
        if estimated_input_collection_size is None and isinstance(input_collection, Sized):
            estimated_input_collection_size = len(cast(Sized, input_collection))

        self.input_collection = input_collection
        self.estimated_input_collection_size = estimated_input_collection_size
        self.seen = 0
        self.success_count = 0
        self.failed_count = 0
        self.max_retries_soft_reached_count = 0
        self.max_retries_timeout_reached_count = 0
        self.retries_by_soft_fail = 0
        self.retries_by_timeout = 0
        self.start_time = time.time()
        self.input_queue = asyncio.Queue(maxsize=self.input_buffer_size)
        self.queues = ResultQueues()
        self.iterator_exhausted = asyncio.Event()

    async def _requester(self, session: aiohttp.ClientSession) -> None:
        """Worker loop that pulls requests from the queue and executes them."""
        while True:
            next_request: dict[str, Any] | DoneSentinel = await self.input_queue.get()
            if isinstance(next_request, DoneSentinel):
                self.input_queue.task_done()
                break

            req: dict[str, Any] = next_request

            try:
                soft_retries: int = 0
                timeout_retries: int = 0
                while True:
                    if soft_retries >= self.max_retries_when_soft_fail:
                        self.max_retries_soft_reached_count += 1
                        await self.queues.max_retries_soft_fail_reached.put(req)
                        if self.callbacks.on_max_retries_by_soft_fail_reached:
                            self.callbacks.on_max_retries_by_soft_fail_reached(req)
                        if self.stop_conditions.stop_on_max_retries_by_soft_fail_reached:
                            raise MaxRetriesStop("Max soft-fail retries reached.")
                        break

                    if timeout_retries >= self.max_retries_on_timeout:
                        self.max_retries_timeout_reached_count += 1
                        await self.queues.max_retries_timeout_reached.put(req)
                        if self.callbacks.on_max_retries_by_timeout_reached:
                            self.callbacks.on_max_retries_by_timeout_reached(req)
                        if self.stop_conditions.stop_on_max_retries_by_timeout_reached:
                            raise MaxRetriesStop("Max timeout retries reached.")
                        break

                    try:
                        async with session.request(**req) as response:
                            state: ResponseState = self.inspect_response(response)
                            parsed_response: Any = await self.parse_response_fn(req, response)

                            if state == ResponseState.SUCCESS:
                                self.success_count += 1
                                await self.queues.success.put(parsed_response)
                                if self.callbacks.on_success:
                                    self.callbacks.on_success(req, response)
                                break
                            elif state == ResponseState.SOFT_FAIL:
                                self.retries_by_soft_fail += 1
                                if self.callbacks.on_soft_fail:
                                    self.callbacks.on_soft_fail(req, soft_retries)
                                if self.stop_conditions.stop_on_soft_fail:
                                    raise SoftFailStop("Stop on soft fail.")
                                soft_retries += 1
                            else:
                                self.failed_count += 1
                                await self.queues.failed.put(parsed_response)
                                if self.callbacks.on_hard_fail:
                                    self.callbacks.on_hard_fail(req, response)
                                if self.stop_conditions.stop_on_hard_fail:
                                    raise HardFailStop("Stop on hard fail.")
                                break
                    except asyncio.TimeoutError:
                        self.retries_by_timeout += 1
                        if self.callbacks.on_timeout:
                            self.callbacks.on_timeout(req, timeout_retries)
                        if self.stop_conditions.stop_on_timeout:
                            raise TimeoutFailStop("Stop on timeout.")
                        timeout_retries += 1
                    except Exception as e:
                        if not isinstance(e, SPARPStopSignal):
                            e.add_note(f"SPARP_REQUEST_DATA: {req}")
                        raise
            finally:
                if self.dones() % self.progress_bar_requests_threshold == 0 and self.show_progress_bar:
                    self.display_bar()
                self.input_queue.task_done()

    async def _producer(self) -> None:
        """Iterates over input_collection and populates the input queue."""
        for item in self.input_collection:
            self.seen += 1
            await self.input_queue.put(item)
        self.iterator_exhausted.set()
        for _ in range(self.concurrency):
            await self.input_queue.put(DoneSentinel())

    def dones(self) -> int:
        """Returns the total number of processed requests (final states)."""
        return (
            self.success_count
            + self.failed_count
            + self.max_retries_soft_reached_count
            + self.max_retries_timeout_reached_count
        )

    def display_bar(self) -> None:
        """Prints a real-time progress bar to the terminal."""
        done: int = self.dones()
        if self.iterator_exhausted.is_set():
            progress: float = 100.0 * done / self.seen if self.seen > 0 else 100.0
            est = f"{done}/{self.seen} - {progress:.1f}%"
        elif self.estimated_input_collection_size:
            progress = 100.0 * done / self.estimated_input_collection_size
            est = f"{done}/~{self.estimated_input_collection_size} - ~{progress:.1f}%"
        else:
            est = f"{done}/?"

        print(
            f"SUCCESS: {self.success_count} | HARD_FAIL: {self.failed_count} | "
            f"TIMEOUT_RETRIES: {self.retries_by_timeout} | SOFT_RETRIES: {self.retries_by_soft_fail} | "
            f"TOOK: {time.time() - self.start_time:.2f}s | PROGRESS: {est}",
            end="\r",
            flush=True,
        )

    async def _bar_updater(self) -> None:
        """Background task that periodically refreshes the progress bar."""
        if not self.show_progress_bar:
            return
        try:
            while True:
                self.display_bar()
                await asyncio.sleep(self.progress_bar_time_threshold.total_seconds())
        except asyncio.CancelledError:
            return

    async def _main(
        self,
        input_collection: Iterable[dict[str, Any]],
        estimated_input_collection_size: int | None = None,
    ) -> SparpResult:
        """Core async orchestrator. Initialises runtime state then runs all workers."""
        self._init_runtime_state(input_collection, estimated_input_collection_size)

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout_s)
            connector = aiohttp.TCPConnector(ssl=self.ssl_verify)
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with asyncio.TaskGroup() as tg:
                    updater_task = tg.create_task(self._bar_updater())
                    tg.create_task(self._producer())
                    for _ in range(self.concurrency):
                        tg.create_task(self._requester(session))

                    await self.iterator_exhausted.wait()
                    await self.input_queue.join()
                    updater_task.cancel()
        except* SPARPStopSignal:
            pass

        if self.show_progress_bar:
            print()
        return self.get_results()

    def run(
        self,
        input_collection: Iterable[dict[str, Any]],
        estimated_input_collection_size: int | None = None,
    ) -> SparpResult:
        """Synchronous entry point. Runs the engine and returns the final result."""
        return asyncio.run(self._main(input_collection, estimated_input_collection_size))

    def get_stats(self) -> SparpStats:
        """Returns a snapshot of the current execution statistics."""
        return SparpStats(
            success=self.success_count,
            failed=self.failed_count,
            soft_retries=self.retries_by_soft_fail,
            timeout_retries=self.retries_by_timeout,
        )

    def get_results(self) -> SparpResult:
        """Drains all internal queues and returns the final SparpResult object."""
        drained = self.queues.drain_all()
        return SparpResult(
            success=drained["success"],
            failed=drained["failed"],
            max_retries_soft_fail_reached=drained["max_retries_soft_fail_reached"],
            max_retries_timeout_reached=drained["max_retries_timeout_reached"],
            stats=self.get_stats(),
        )
