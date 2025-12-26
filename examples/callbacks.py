# run this example using `make run-example EXAMPLE=callbacks` from the root directory

import aiohttp
from typing import Any, Dict
from sparp.sparp import SPARP, ResponseState, Callbacks


def inspect_response(response: aiohttp.ClientResponse) -> ResponseState:
    if response.status == 200:
        return ResponseState.SUCCESS
    if response.status == 429 or response.status == 502:
        return ResponseState.SOFT_FAIL
    return ResponseState.HARD_FAIL


def on_success(request: Dict[str, Any], response: aiohttp.ClientResponse) -> None:
    print(f"Callback Log -> SUCCESS: {request['url']}")


def on_fail(request: Dict[str, Any], response: aiohttp.ClientResponse) -> None:
    print(f"Callback Log -> FAILED: {request['url']} (Status: {response.status})")


def main():
    requests = [
        {"method": "GET", "url": "https://httpbin.org/status/200"},
        {"method": "GET", "url": "https://httpbin.org/status/404"},
    ]
    cb = Callbacks(on_success=on_success, on_hard_fail=on_fail)
    sparp = SPARP(requests, inspect_response=inspect_response, callbacks=cb, concurrency=2)
    result = sparp.main()
    print(f"Final Stats: {result.stats.success} Success, {result.stats.failed} Failed")


if __name__ == "__main__":
    main()
