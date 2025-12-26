import aiohttp
from sparp.sparp import SPARP, ResponseState


def inspect_response(response: aiohttp.ClientResponse) -> ResponseState:
    if response.status == 200:
        return ResponseState.SUCCESS
    if response.status == 429 or response.status == 502:
        return ResponseState.SOFT_FAIL
    return ResponseState.HARD_FAIL


def main():
    # httpbin.org/delay/5 will take 5 seconds to respond
    requests = [{"method": "GET", "url": "https://httpbin.org/delay/5"} for _ in range(3)]

    # We set a 1-second timeout. This will force timeout retries.
    sparp = SPARP(requests, inspect_response=inspect_response, timeout_s=1.0, max_retries_by_timeout=2, concurrency=3)
    result = sparp.main()

    print(f"Success: {result.stats.success}")
    print(f"Total Timeout Retries attempted: {result.stats.timeout_retries}")
    print(f"Requests that eventually gave up: {len(result.max_retries_timeout_reached)}")


if __name__ == "__main__":
    main()
