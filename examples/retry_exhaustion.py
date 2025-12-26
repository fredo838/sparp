import aiohttp
from sparp.sparp import SPARP, ResponseState


def inspect_response(response: aiohttp.ClientResponse) -> ResponseState:
    # Force everything into SOFT_FAIL to demonstrate retries
    return ResponseState.SOFT_FAIL


def main():
    requests = [{"method": "GET", "url": "https://httpbin.org/get"}]

    # Try twice (initial + 1 retry) then give up
    sparp = SPARP(requests, inspect_response=inspect_response, max_retries_by_soft_fail=1, concurrency=1)
    result = sparp.main()

    # Access the items that reached the max retry limit
    for item in result.max_retries_soft_fail_reached:
        print(f"Exhausted: {item['url']}")
    print(f"Total Soft Retries Attempted: {result.stats.soft_retries}")


if __name__ == "__main__":
    main()
