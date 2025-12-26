import asyncio
import time
import datetime
from enum import Enum
from typing import Callable, Iterable, Any, Awaitable, Self, Dict, List

import aiohttp
from dataclasses import dataclass


class ResponseState(Enum):
    HARD_FAIL = "HARD_FAIL"
    SOFT_FAIL = "SOFT_FAIL"
    SUCCESS = "SUCCESS"


class Sentinel:
    pass


class DoneSentinel:
    pass


class SPARPStopSignal(Exception):
    pass


class HardFailStop(SPARPStopSignal):
    pass


class SoftFailStop(SPARPStopSignal):
    pass


class TimeoutFailStop(SPARPStopSignal):
    pass


class MaxRetriesStop(SPARPStopSignal):
    pass


@dataclass(frozen=True)
class SparpStats:
    success: int
    failed: int
    soft_retries: int
    timeout_retries: int


@dataclass(frozen=True)
class SparpResult:
    stats: SparpStats
    success: List[Any]
    failed: List[Any]
    max_retries_soft_fail_reached: List[Dict[str, Any]]
    max_retries_timeout_reached: List[Dict[str, Any]]


class ResultQueues:
    def __init__(self: Self) -> None:
        self.success: asyncio.Queue[Any] = asyncio.Queue()
        self.failed: asyncio.Queue[Any] = asyncio.Queue()
        self.max_retries_soft_fail_reached: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self.max_retries_timeout_reached: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

    @staticmethod
    async def _drain(q: asyncio.Queue[Any]) -> List[Any]:
        items: List[Any] = []
        while not q.empty():
            items.append(await q.get())
            q.task_done()
        return items

    async def drain_all(self: Self) -> Dict[str, List[Any]]:
        return {
            "success": await self._drain(self.success),
            "failed": await self._drain(self.failed),
            "max_retries_soft_fail_reached": await self._drain(self.max_retries_soft_fail_reached),
            "max_retries_timeout_reached": await self._drain(self.max_retries_timeout_reached),
        }


class StopConditions:
    def __init__(
        self: Self,
        stop_on_soft_fail: bool = False,
        stop_on_hard_fail: bool = False,
        stop_on_max_retries_by_soft_fail_reached: bool = False,
        stop_on_max_retries_by_timeout_reached: bool = False,
        stop_on_timeout: bool = False,
    ) -> None:
        self.stop_on_soft_fail = stop_on_soft_fail
        self.stop_on_hard_fail = stop_on_hard_fail
        self.stop_on_max_retries_by_soft_fail_reached = stop_on_max_retries_by_soft_fail_reached
        self.stop_on_max_retries_by_timeout_reached = stop_on_max_retries_by_timeout_reached
        self.stop_on_timeout = stop_on_timeout


class Callbacks:
    def __init__(
        self: Self,
        on_success: Callable[[Dict[str, Any], aiohttp.ClientResponse], None] | None = None,
        on_hard_fail: Callable[[Dict[str, Any], aiohttp.ClientResponse], None] | None = None,
        on_soft_fail: Callable[[Dict[str, Any], int], None] | None = None,
        on_timeout: Callable[[Dict[str, Any], int], None] | None = None,
        on_max_retries_by_soft_fail_reached: Callable[[Dict[str, Any]], None] | None = None,
        on_max_retries_by_timeout_reached: Callable[[Dict[str, Any]], None] | None = None,
    ) -> None:
        self.on_success = on_success
        self.on_hard_fail = on_hard_fail
        self.on_soft_fail = on_soft_fail
        self.on_timeout = on_timeout
        self.on_max_retries_by_soft_fail_reached = on_max_retries_by_soft_fail_reached
        self.on_max_retries_by_timeout_reached = on_max_retries_by_timeout_reached


async def default_parse_response(request_dict: Dict[str, Any], response: aiohttp.ClientResponse) -> Any:
    return {
        "input": request_dict,
        "status": response.status,
        "text": await response.text(),
        "headers": dict(response.headers),
    }


class SPARP:
    def __init__(
        self: Self,
        input_collection: Iterable[Dict[str, Any]],
        inspect_response: Callable[[aiohttp.ClientResponse], ResponseState],
        callbacks: Callbacks = Callbacks(),
        concurrency: int = 100,
        max_retries_by_soft_fail: int = 20,
        max_retries_by_timeout: int = 20,
        parse_response: Callable[[Dict[str, Any], aiohttp.ClientResponse], Awaitable[Any]] = default_parse_response,
        stop_conditions: StopConditions = StopConditions(),
        input_buffer_size: int = 100,
        show_progress_bar: bool = False,
        estimated_input_collection_size: int | None = None,
        timeout_s: float = 30.0,
        progress_bar_requests_threshold: int = 1,
        progress_bar_time_threshold: datetime.timedelta = datetime.timedelta(seconds=0.5),
    ) -> None:
        self.seen: int = 0
        self.concurrency: int = concurrency
        self.input_queue: asyncio.Queue[Dict[str, Any] | DoneSentinel] = asyncio.Queue(maxsize=input_buffer_size)
        self.queues: ResultQueues = ResultQueues()

        self.success_count: int = 0
        self.failed_count: int = 0
        self.max_retries_soft_reached_count: int = 0
        self.max_retries_timeout_reached_count: int = 0

        self.iterator_exhausted: asyncio.Event = asyncio.Event()

        self.callbacks: Callbacks = callbacks
        self.inspect_response: Callable[[aiohttp.ClientResponse], ResponseState] = inspect_response
        self.parse_response: Callable[[Dict[str, Any], aiohttp.ClientResponse], Awaitable[Any]] = parse_response
        self.input_collection: Iterable[Dict[str, Any]] = input_collection
        self.max_retries_by_soft_fail: int = max_retries_by_soft_fail
        self.max_retries_by_timeout: int = max_retries_by_timeout
        self.stop_conditions: StopConditions = stop_conditions
        self.show_progress_bar: bool = show_progress_bar
        self.retries_by_soft_fail: int = 0
        self.retries_by_timeout: int = 0
        self.estimated_input_collection_size: int | None = estimated_input_collection_size
        self.start_time: float = time.time()
        self.timeout_s: float = timeout_s
        self.progress_bar_time_threshold: datetime.timedelta = progress_bar_time_threshold
        self.progress_bar_requests_threshold: int = progress_bar_requests_threshold

        if self.progress_bar_time_threshold.total_seconds() == 0:
            raise ValueError("progress_bar_time_threshold should not be zero seconds")

    async def _requester(self: Self, session: aiohttp.ClientSession) -> None:
        while True:
            next_request: Dict[str, Any] | DoneSentinel = await self.input_queue.get()
            if isinstance(next_request, DoneSentinel):
                self.input_queue.task_done()
                break

            req: Dict[str, Any] = next_request

            try:
                soft_retries: int = 0
                timeout_retries: int = 0
                while True:
                    if soft_retries >= self.max_retries_by_soft_fail:
                        self.max_retries_soft_reached_count += 1
                        await self.queues.max_retries_soft_fail_reached.put(req)
                        if self.callbacks.on_max_retries_by_soft_fail_reached:
                            self.callbacks.on_max_retries_by_soft_fail_reached(req)
                        if self.stop_conditions.stop_on_max_retries_by_soft_fail_reached:
                            raise MaxRetriesStop("Max soft-fail retries reached.")
                        break

                    if timeout_retries >= self.max_retries_by_timeout:
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
                            parsed_response: Any = await self.parse_response(req, response)

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
                                continue
                            elif state == ResponseState.HARD_FAIL:
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
                        continue
                    except Exception as e:
                        if not isinstance(e, SPARPStopSignal):
                            e.add_note(f"SPARP_REQUEST_DATA: {req}")
                        raise
            finally:
                if self.dones() % self.progress_bar_requests_threshold == 0 and self.show_progress_bar:
                    self.display_bar()
                self.input_queue.task_done()

    async def _producer(self: Self) -> None:
        for item in self.input_collection:
            self.seen += 1
            await self.input_queue.put(item)
        self.iterator_exhausted.set()
        for _ in range(self.concurrency):
            await self.input_queue.put(DoneSentinel())

    def dones(self: Self) -> int:
        return (
            self.success_count
            + self.failed_count
            + self.max_retries_soft_reached_count
            + self.max_retries_timeout_reached_count
        )

    def display_bar(self: Self) -> None:
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
        )

    async def _bar_updater(self: Self) -> None:
        if not self.show_progress_bar:
            return
        try:
            while True:
                self.display_bar()
                await asyncio.sleep(self.progress_bar_time_threshold.total_seconds())
        except asyncio.CancelledError:
            return

    async def _main(self: Self) -> SparpResult:
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout_s)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with asyncio.TaskGroup() as tg:
                    updater_task = tg.create_task(self._bar_updater())
                    tg.create_task(self._producer())
                    for _ in range(self.concurrency):
                        tg.create_task(self._requester(session))

                    await self.iterator_exhausted.wait()
                    # Join inside the TaskGroup context ensures all accounting
                    # completes before the group closes.
                    await self.input_queue.join()
                    updater_task.cancel()
        except* SPARPStopSignal:
            pass

        if self.show_progress_bar:
            print("\r")
        return await self.get_results()

    def main(self: Self) -> SparpResult:
        return asyncio.run(self._main())

    def get_stats(self: Self) -> SparpStats:
        return SparpStats(
            success=self.success_count,
            failed=self.failed_count,
            soft_retries=self.retries_by_soft_fail,
            timeout_retries=self.retries_by_timeout,
        )

    async def get_results(self: Self) -> SparpResult:
        drained = await self.queues.drain_all()
        return SparpResult(
            success=drained["success"],
            failed=drained["failed"],
            max_retries_soft_fail_reached=drained["max_retries_soft_fail_reached"],
            max_retries_timeout_reached=drained["max_retries_timeout_reached"],
            stats=self.get_stats(),
        )
