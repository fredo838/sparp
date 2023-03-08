import asyncio
import aiohttp
import aiohttp.client_exceptions
import aiohttp_retry
import time
from typing import Dict, List
from aiohttp_retry import RetryClient, ExponentialRetry
import logging
from aiohttp import TraceConfig


async def on_request_start(session, trace_config_ctx, params) -> None:
    current_attempt = trace_config_ctx.trace_request_ctx['current_attempt']
    if current_attempt > 1:
        print(f"Retrying request, attempt number {current_attempt}")


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

    def print_counter(self, done=False):
        elapsed = time.time() - self.start_time
        percent = int(self.done / self.total * self.cols)
        remainder = self.cols - percent
        full = ''.join(['=' for _ in range(percent)])
        empty = ''.join([' 'for _ in range(remainder)])
        full = full[:-1] + ">"
        end = {'end': "\r"} if not done else {}
        print(f"[{full}{empty}] {self.done}/{self.total}, success={self.success}, fail={self.fail},  took {round(elapsed, 2)}                            ", **end, flush=True)


async def consumer(source_queue, session, shared, ok_status_codes, stop_on_first_fail):
    responses = []
    while True:
        is_done = await shared.check_done()
        should_stop = await shared.get_should_stop()
        if is_done or should_stop:
            break
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
            "json": json_
        }
        if response["status_code"] in ok_status_codes:
            await shared.increment_success()
        else:
            await shared.increment_fail()
            if stop_on_first_fail:
                await shared.set_should_stop()
        responses.append(response)
    return responses


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


async def async_main(source_queue, shared, max_outstanding_requests, ok_status_codes, stop_on_first_fail, retry_attempts, retry_status_codes):
    trace_config = TraceConfig()
    trace_config.on_request_start.append(on_request_start)
    async with RetryClient(
            client_session=aiohttp.ClientSession(
                skip_auto_headers=["Content-Type"], trace_configs=[trace_config]),
            retry_options=ExponentialRetry(
                attempts=retry_attempts,
                statuses=set(retry_status_codes),
                retry_all_server_errors=False
            ),
            raise_for_status=False) as session:
        coros = [updater(shared)] + [consumer(source_queue, session, shared, ok_status_codes, stop_on_first_fail)
                                     for _ in range(max_outstanding_requests)]
        results = await asyncio.gather(*coros)

    results = [item for sublist in results[1:] for item in sublist]
    return results


async def fill_queue(queue, items):
    for item in items:
        await queue.put(item)
    return queue


def sparp(configs: List[Dict], max_outstanding_requests: int, ok_status_codes=[200], stop_on_first_fail=False, disable_bar: bool = False, retry_attempts: int = 1, retry_status_codes=[]) -> List:
    """Simple Parallel Asynchronous Requests in Python

    Arguments:
      configs (List[Dict]): the request configurations. Each item in this list is fed roughly as such: [requests.request(**config) for config in configs]
      max_outstanding_requests (int): max number of parallel requests alive at the same time
      ok_status_codes (List[int]): list of status codes deemed "success"
      stop_on_first_fail (bool): whether or not to stop sending requests if we get a status not in stop_on_first_fail
      disable_bar (bool): do not print anything
      retry_attempts (int): number of times to retry with exponential backoff

    Returns:
      List: list of Responses
    """
    source_queue = asyncio.Queue()
    source_queue = asyncio.run(fill_queue(source_queue, configs))
    shared = SharedMemory(total=len(configs), disable_bar=disable_bar)
    result = asyncio.run(async_main(source_queue, shared,
                         max_outstanding_requests, ok_status_codes, stop_on_first_fail, retry_attempts, retry_status_codes))
    return result
