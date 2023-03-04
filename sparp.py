import asyncio
import aiohttp
import time


class AsyncCounter:
    def __init__(self, total, ncols=80):
        self.value = 0
        self.lock = asyncio.Lock()
        self.total = total
        self.time = time.time()
        self.cols = ncols
        self.print_counter()

    def print_counter(self, done=False):
        elapsed = time.time() - self.time
        percent = int(self.value / self.total * self.cols)
        remainder = self.cols - percent
        full = ''.join(['=' for _ in range(percent)])
        empty = ''.join([' 'for _ in range(remainder)])
        full = full[:-1] + ">"
        end = {'end': "\r"} if not done else {}
        print(f"[{full}{empty}] {self.value}/{self.total}, took {round(elapsed, 2)}                            ", **end, flush=True)

    async def increment(self):
        async with self.lock:
            self.value = self.value + 1
            self.print_counter()

    async def update(self):
        async with self.lock:
            self.print_counter()

    async def check_done(self):
        async with self.lock:
            return self.value == self.total


async def updater(counter):
    while True:
        await asyncio.sleep(.3)
        await counter.update()
        done = await counter.check_done()
        if done:
            counter.print_counter(done=True)
            break


async def fetch(client, url, total, semaphore):
    async with semaphore:
        awaited_coro = await client.get(url)
        await total.increment()
        return awaited_coro


async def fetch_all(client, urls, total, semaphore):
    tasks = []
    for url in urls:
        task = asyncio.create_task(fetch(client, url, total, semaphore))
        tasks.append(task)
    res = asyncio.as_completed(tasks)
    return res


async def sparp():
    urls = ["https://www.google.com" for x in range(1000)]
    total = AsyncCounter(len(urls), ncols=40)
    semaphore = asyncio.Semaphore(50)
    async with aiohttp.ClientSession() as session:
        tasks = []
        updater_task = asyncio.create_task(updater(total))
        for url in urls:
            task = asyncio.create_task(fetch(session, url, total, semaphore))
            tasks.append(task)
        for task in [updater_task] + tasks:
            await task

if __name__ == "__main__":
    asyncio.run(main())
