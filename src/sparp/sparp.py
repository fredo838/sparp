import asyncio
import aiohttp
import aiohttp.client_exceptions
import time
from typing import Dict, List, Iterator
from aiohttp_retry import RetryClient, ExponentialRetry
import time
from aiohttp import TraceConfig


async def on_request_end(session, trace_config_ctx, params):
    elapsed = asyncio.get_event_loop().time() - trace_config_ctx.start
    params.response.elapsed = elapsed
    # print("Request took {}".format(elapsed))


async def on_request_start(session, trace_config_ctx, params) -> None:
    current_attempt = trace_config_ctx.trace_request_ctx['current_attempt']
    if current_attempt > 1:
        print(f"Retrying request, attempt number {current_attempt}")
    trace_config_ctx.start = asyncio.get_event_loop().time()


class SharedMemory:
    def __init__(self, total, cols=40, disable_bar=False):
        self.lock = asyncio.Lock()
        self.done = 0
        self.success = 0
        self.fail = 0
        self.total = total
        self.cols = cols
        self.start_time = time.time()
        self.should_stop = False
        self.disable_bar = disable_bar
        if not self.disable_bar:
            self.print_counter()

    async def set_should_stop(self):
        async with self.lock:
            self.should_stop = True

    async def get_should_stop(self):
        async with self.lock:
            should_stop = self.should_stop
        return should_stop

    async def increment_success(self):
        async with self.lock:
            self.done += 1
            self.success += 1
            self.print_counter()

    async def increment_fail(self):
        async with self.lock:
            self.done += 1
            self.fail += 1
            if not self.disable_bar:
                self.print_counter()

    async def update(self):
        async with self.lock:
            if not self.disable_bar:
                self.print_counter()

    async def check_done(self):
        async with self.lock:
            is_done = self.total == self.done
        return is_done

    async def set_total(self, total):
        async with self.lock:
            if self.total == -1:
                self.total = total

    def print_counter(self, done=False):
        elapsed = time.time() - self.start_time
        if self.total == -1:
            percent = 2
        else:
            percent = int(self.done / self.total * self.cols)
        remainder = self.cols - percent
        full = ''.join(['=' for _ in range(percent)])
        empty = ''.join([' 'for _ in range(remainder)])
        full = full[:-1] + ">"
        end = {'end': "\r"} if not done else {}
        total = "?" if self.total == -1 else self.total
        print(f"[{full}{empty}] {self.done}/{total}, success={self.success}, fail={self.fail},  took {round(elapsed, 2)}                            ", **end, flush=True)


async def canceler(shared, source_semaphore, n_consumers):
    while True:
        await asyncio.sleep(.1)
        is_done = await shared.check_done()
        should_stop = await shared.get_should_stop()
        if is_done or should_stop:
            for _ in range(n_consumers):
                source_semaphore.release()
            break


async def producer(items, source_queue, source_semaphore, time_between_requests, shared):
    total = 0
    for item in items:
        total += 1
        await source_queue.put(item)
        source_semaphore.release()
        await asyncio.sleep(time_between_requests)
    await shared.set_total(total)


async def consumer(source_queue, source_semaphore, sink_queue, session, shared, ok_status_codes, stop_on_first_fail):
    while True:
        await source_semaphore.acquire()
        try:
            config = source_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        response = await session.request(**config)
        response_text = await response.text()
        status_code = response.status
        try:
            json_ = await response.json()
        except Exception as e:
            json_ = f"Failed to decode json due to {str(e)}"
        response = {
            "text": response_text,
            "status_code": status_code,
            "json": json_,
            "elapsed": response.elapsed
        }
        await sink_queue.put(response)
        if response["status_code"] in ok_status_codes:
            await shared.increment_success()
        else:
            await shared.increment_fail()
            if stop_on_first_fail:
                await shared.set_should_stop()


async def updater(shared):
    while True:
        await asyncio.sleep(.3)
        await shared.update()
        done = await shared.check_done()
        should_stop = await shared.get_should_stop()
        if done or should_stop:
            if not shared.disable_bar:
                shared.print_counter(done=True)
            break


async def async_main(configs, source_queue, source_semaphore, sink_queue, shared, max_outstanding_requests, time_between_requests, ok_status_codes, stop_on_first_fail, retry_attempts, retry_status_codes):
    trace_config = TraceConfig()
    trace_config.on_request_start.append(on_request_start)
    trace_config.on_request_end.append(on_request_end)
    retry_options = ExponentialRetry(
        attempts=retry_attempts,
        statuses=set(retry_status_codes),
        retry_all_server_errors=False
    )
    async with RetryClient(
            client_session=aiohttp.ClientSession(
                skip_auto_headers=["Content-Type"],
                trace_configs=[trace_config]
            ),
            retry_options=retry_options,
            raise_for_status=False) as session:
        consumers = [consumer(source_queue, source_semaphore, sink_queue, session, shared,
                              ok_status_codes, stop_on_first_fail) for _ in range(max_outstanding_requests)]
        management_list = [
            updater(shared),
            producer(configs, source_queue, source_semaphore, time_between_requests, shared),
            canceler(shared, source_semaphore, max_outstanding_requests)
        ]
        coros = management_list + consumers
        await asyncio.gather(*coros)


async def empty_full_queue(queue):
    results = []
    while True:
        try:
            results.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            break
    return results


def sparp(configs: Iterator[Dict], max_outstanding_requests: int, time_between_requests: float = 0., ok_status_codes=[200], stop_on_first_fail=False, disable_bar: bool = False, attempts: int = 1, retry_status_codes=[]) -> List:
    """Simple Parallel Asynchronous Requests in Python

    Arguments:
      configs (List[Dict]): the request configurations. Each item in this list is fed roughly as such: [requests.request(**config) for config in configs]
      max_outstanding_requests (int): max number of parallel requests alive at the same time
      time_between_requests (float): minimum amount of time to wait before sending the next request
      ok_status_codes (List[int]): list of status codes deemed "success"
      stop_on_first_fail (bool): whether or not to stop sending requests if we get a status not in stop_on_first_fail
      disable_bar (bool): do not print anything
      attempts (int): number of times to try (at least 1)
      retry_status_codes (List[int]): status codes to retry

    Returns:
      List: list of Responses
    """
    if attempts < 1:
        raise ValueError("attempts should be at least 1")
    if hasattr(configs, '__len__'):
        total = len(configs)
    else:
        total = -1
    source_queue = asyncio.Queue()
    source_semaphore = asyncio.Semaphore(0)
    sink_queue = asyncio.Queue()
    shared = SharedMemory(total=total, disable_bar=disable_bar)
    asyncio.run(async_main(configs, source_queue, source_semaphore, sink_queue, shared,
                           max_outstanding_requests, time_between_requests, ok_status_codes, stop_on_first_fail, attempts, retry_status_codes))
    results = asyncio.run(empty_full_queue(sink_queue))
    print(len(results))
    return results
