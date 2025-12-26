# run this example using `make run-example EXAMPLE=basic_example` from the root directory

import aiohttp
from sparp.sparp import SPARP, ResponseState
import json


def inspect_response(response: aiohttp.ClientResponse) -> ResponseState:
    if response.status == 200:
        return ResponseState.SUCCESS
    if response.status == 429 or response.status == 502:
        return ResponseState.SOFT_FAIL
    return ResponseState.HARD_FAIL


def main():
    requests = [{"method": "GET", "url": f"https://httpbin.org/get?item={i}"} for i in range(100)]

    sparp = SPARP(requests, inspect_response=inspect_response, concurrency=20, show_progress_bar=True)
    result = sparp.main()

    for item in result.success:
        # ['args']['item'] are specific to httpbin.org/get
        print(f"data sent: {item['input']['url']}, data received: {json.loads(item['text'])['args']['item']}")
    print(f"Completed: {result.stats.success} requests successfully, retried {result.stats.soft_retries} times")


if __name__ == "__main__":
    main()
