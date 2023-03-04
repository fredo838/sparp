import asyncio
import aiohttp
import time
import requests
from typing import List, Dict


class AsyncCounter:
    def __init__(self, total, ncols=80):
        self.value = 0
        self.lock = asyncio.Lock()
        self.total = total
        self.time = time.time()
        self.cols = ncols
        self.fail = 0
        self.success = 0
        self.should_stop = False
        self.print_counter()

    def print_counter(self, done=False):
        elapsed = time.time() - self.time
        percent = int(self.value / self.total * self.cols)
        remainder = self.cols - percent
        full = ''.join(['=' for _ in range(percent)])
        empty = ''.join([' 'for _ in range(remainder)])
        full = full[:-1] + ">"
        end = {'end': "\r"} if not done else {}
        print(f"[{full}{empty}] {self.value}/{self.total}, ok={self.success}, fail={self.fail}, took {round(elapsed, 2)}                            ", **end, flush=True)

    async def increment_fail(self):
        async with self.lock:
            self.value = self.value + 1
            self.fail = self.fail + 1
            self.print_counter()

    async def increment_success(self):
        async with self.lock:
            self.value = self.value + 1
            self.success = self.success + 1
            self.print_counter()

    async def update(self):
        async with self.lock:
            self.print_counter()

    async def check_done(self):
        async with self.lock:
            return self.value == self.total

    async def get_should_stop(self):
        async with self.lock:
            return self.should_stop

    async def set_should_stop(self):
        async with self.lock:
            self.should_stop = True


async def updater(counter):
    while True:
        await asyncio.sleep(.3)
        await counter.update()
        done = await counter.check_done()
        should_stop = await counter.get_should_stop()
        if done or should_stop:
            await asyncio.sleep(.3)
            counter.print_counter(done=True)
            break


async def fetch(client, request_config, total, semaphore, ok_status_codes, stop_on_not_ok):
    async with semaphore:
        if await total.get_should_stop():
            return None
        awaited_coro = await client.request(**request_config)

        if awaited_coro.status in ok_status_codes:
            await total.increment_success()
        else:
            await total.increment_fail()
            if stop_on_not_ok:
                await total.set_should_stop()
        return awaited_coro


async def request_parallel_async(request_configs: List[Dict], max_outstanding_requests: int, ok_status_codes: List[int], stop_on_not_ok: bool):
    total = AsyncCounter(len(request_configs), ncols=40)
    semaphore = asyncio.Semaphore(max_outstanding_requests)
    task_results = []
    async with aiohttp.ClientSession() as session:
        tasks = []
        updater_task = asyncio.create_task(updater(total))
        for request_config in request_configs:
            task = asyncio.create_task(
                fetch(session, request_config, total, semaphore, ok_status_codes, stop_on_not_ok))
            tasks.append(task)
        for j, task in enumerate([updater_task] + tasks):
            task_result = await task
            if j != 0:
                task_results.append(task_result)
        task_result = task_results[0]
    return task_results


def request_parallel(request_configs: List[Dict], max_outstanding_requests: int, ok_status_codes: List[int], stop_on_not_ok: bool) -> List[requests.Response]:
    return asyncio.run(request_parallel_async(request_configs, max_outstanding_requests, ok_status_codes, stop_on_not_ok))
