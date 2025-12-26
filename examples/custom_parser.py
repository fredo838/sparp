# run this example using `make run-example EXAMPLE=custom_parser` from the root directory

import aiohttp
from typing import Any, Dict
from sparp.sparp import SPARP, ResponseState


def inspect_response(response: aiohttp.ClientResponse) -> ResponseState:
    if response.status == 200:
        return ResponseState.SUCCESS
    if response.status == 429 or response.status == 502:
        return ResponseState.SOFT_FAIL
    return ResponseState.HARD_FAIL


async def custom_parser(request_dict: Dict[str, Any], response: aiohttp.ClientResponse) -> Dict[str, Any]:
    """
    High-performance parser:
    We do NOT use 'await response.json()' here. We only grab headers.
    """
    return {
        "url": request_dict.get("url"),
        "server": response.headers.get("Server"),
        "date": response.headers.get("Date"),
        "status": response.status,
    }


def main():
    requests = [{"method": "GET", "url": "https://httpbin.org/get"} for _ in range(5)]

    # SPARP will run the custom_parser, but since the parser doesn't
    # await the body, it finishes as soon as headers are received.
    sparp = SPARP(
        requests, inspect_response=inspect_response, parse_response=custom_parser, concurrency=2, show_progress_bar=True
    )

    result = sparp.main()

    for item in result.success:
        print(f"URL: {item['url']} | Server: {item['server']} | Date: {item['date']}")


if __name__ == "__main__":
    main()
