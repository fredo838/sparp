import aiohttp
from sparp.sparp import SPARP, ResponseState, StopConditions


def inspect_response(response: aiohttp.ClientResponse) -> ResponseState:
    # 500 triggers a HARD_FAIL to demonstrate the stop condition
    if response.status == 500:
        return ResponseState.HARD_FAIL
    return ResponseState.SUCCESS if response.status == 200 else ResponseState.SOFT_FAIL


def main():
    requests = [
        {"method": "GET", "url": "https://httpbin.org/status/200"},
        {"method": "GET", "url": "https://httpbin.org/status/500"},  # Trigger stop
        {"method": "GET", "url": "https://httpbin.org/status/200"},  # Never reached
    ]
    cond = StopConditions(stop_on_hard_fail=True)
    sparp = SPARP(requests, inspect_response=inspect_response, stop_conditions=cond, concurrency=1)
    result = sparp.main()
    print(f"Halted after {result.stats.success + result.stats.failed} total requests.")
    print(f"Success: {result.stats.success} | Failed: {result.stats.failed}")


if __name__ == "__main__":
    main()
