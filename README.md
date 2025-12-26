# SPARP: Simple Parallel Async Requests for Python

This library enables you to turn: ```responses = [requests.post(url) for url in urls]``` into concurrent requests without you needing to write any `async/await` code.



## Installation


```bash
python3 -m pip install sparp
```

## Basic Usage

This example shows how to process 100 concurrent requests with a progress bar:

```python
# examples/basic_example.py
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
    requests = [{
        "method": "GET",
        "url": f"https://httpbin.org/get?item={i}"}
    for i in range(100)]

    result = SPARP(
        requests, inspect_response=inspect_response, concurrency=20, show_progress_bar=True
    ).main()

    for item in result.success:
        print(
            f"data sent: {item['input']['url']},
            data received: {json.loads(item['text'])['args']['item']}"
        )
    print(f"Completed {result.stats.success} requests")
    print(f"Retried {result.stats.soft_retries} times")


if __name__ == "__main__":
    main()
```

## Running Examples

```bash
make run-basic-usage
make run-example EXAMPLE=input_collection
make run-example EXAMPLE=callbacks
make run-example EXAMPLE=custom_parser
make run-example EXAMPLE=retry_exhaustion
make run-example EXAMPLE=stop_condition
make run-example EXAMPLE=timeouts
```


## Features

* **Generator Support**: Takes a generator as input to generate request data on the fly.
* **Smart Retries**: Separate logic for retrying based on request timeouts versus server information (like a 429 - Too Many Requests).
* **Custom Parsing**: Decide exactly what data to keep from the response (headers, body, or status) before the final list is returned.
* **Progress Tracking**: A nice progress bar that tracks successes, failures, and retries in real-time.



## API Reference

### Initialization
All configurations are passed during the initialization of the `SPARP` class:

```python
class SPARP:
    def __init__(
        self: Self,
        input_collection: Iterable[Dict[str, Any]],             # Iterable of request configurations
        inspect_response: Callable[[aiohttp.ClientResponse], ResponseState], # Logic to categorize response status
        callbacks: Callbacks = Callbacks(),                      # Hooks for success, fail, and retry events
        concurrency: int = 100,                                 # Maximum number of simultaneous requests
        max_retries_by_soft_fail: int = 20,                     # Retry limit for server-side errors (e.g. 429)
        max_retries_by_timeout: int = 20,                       # Retry limit for connection or read timeouts
        parse_response: Callable[                               # Logic to extract data from the response
            [dict[str, Any], aiohttp.ClientResponse], Awaitable[Any]
        ] = default_parse_response,
        stop_conditions: StopConditions = StopConditions(),      # Thresholds to halt the entire process
        input_buffer_size: int = 100,                           # Items to pre-fetch from generator into memory
        show_progress_bar: bool = False,                        # Toggle the terminal progress UI
        estimated_input_collection_size: int | None = None,     # Total count for accurate progress percentage
        timeout_s: float = 30.0,                                # Seconds before a request attempt times out
        progress_bar_requests_threshold: int = 1,               # Min requests finished before UI updates
        progress_bar_time_threshold: datetime.timedelta =       # Min time elapsed before UI updates
            datetime.timedelta(seconds=0.5),
    ) -> None:
    ...

    def main() -> 

# Input classes

class ResponseState(Enum):
    HARD_FAIL = "HARD_FAIL"
    SOFT_FAIL = "SOFT_FAIL"
    SUCCESS = "SUCCESS"


class Callbacks:
    def __init__(
        self: Self,
        on_success: Callable[[dict[str, Any], aiohttp.ClientResponse], None] | None = None,
        on_hard_fail: Callable[[dict[str, Any], aiohttp.ClientResponse], None] | None = None,
        on_soft_fail: Callable[[dict[str, Any], int], None] | None = None,
        on_timeout: Callable[[dict[str, Any], int], None] | None = None,
        on_max_retries_by_soft_fail_reached: Callable[[dict[str, Any]], None] | None = None,
        on_max_retries_by_timeout_reached: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
    ...


# Output classes
@dataclass(frozen=True)
class SparpStats:
    success: int
    failed: int
    soft_retries: int
    timeout_retries: int


@dataclass(frozen=True)
class SparpResult:
    stats: SparpStats
    success: list[Any]
    failed: list[Any]
    max_retries_soft_fail_reached: list[dict[str, Any]]
    max_retries_timeout_reached: list[dict[str, Any]]
```
