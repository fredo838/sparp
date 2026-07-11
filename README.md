# SPARP: Simple Parallel Async Requests for Python

Turn sequential HTTP requests into concurrent ones without writing any `async/await` code:

```python
# Before
responses = [requests.post(url, json=payload) for url, payload in items]

# After
result = SPARP(inspect_response=inspect_response).run(items)
```

## Installation

```bash
pip install sparp
```

## Basic Usage

```python
import aiohttp
import json
from sparp import SPARP, ResponseState


def inspect_response(response: aiohttp.ClientResponse) -> ResponseState:
    if response.status == 200:
        return ResponseState.SUCCESS
    if response.status in (429, 502):
        return ResponseState.SOFT_FAIL
    return ResponseState.HARD_FAIL


requests = [{"method": "GET", "url": f"https://httpbin.org/get?item={i}"} for i in range(100)]

sparp = SPARP(inspect_response=inspect_response, concurrency=20, show_progress_bar=True)
result = sparp.run(requests)

for item in result.success:
    print(f"sent: {item['input']['url']} | received: {json.loads(item['text'])['args']['item']}")

print(f"Completed: {result.stats.success} successful, {result.stats.soft_retries} retries")
```

## Running Examples

```bash
make run-example EXAMPLE=basic_example
make run-example EXAMPLE=callbacks
make run-example EXAMPLE=custom_parser
make run-example EXAMPLE=input_generator
make run-example EXAMPLE=retry_exhaustion
make run-example EXAMPLE=stop_conditions
make run-example EXAMPLE=timeouts
```

## Features

- **Generator support** — pass a generator as input; requests are buffered into memory in small batches
- **Smart retries** — separate retry budgets for server-side failures (e.g. 429) and timeouts
- **Custom parsing** — control exactly what is kept from each response before results are returned
- **Stop conditions** — halt the entire run early on any failure category
- **Progress bar** — real-time terminal UI showing successes, failures, retries, and throughput
- **Auto size detection** — if the input is a list or other sized iterable, progress percentage is computed automatically

## API Reference

### `SPARP(inspect_response, ...)` — configuration

All options are passed at construction time. The input collection is passed separately to `run()`.

```python
sparp = SPARP(
    inspect_response,                          # required — classifies each response as SUCCESS / SOFT_FAIL / HARD_FAIL
    callbacks=None,                            # Callbacks — hooks for every outcome event
    concurrency=100,                           # max simultaneous in-flight requests
    max_retries_when_soft_fail=20,             # retry budget for SOFT_FAIL responses
    max_retries_on_timeout=20,                 # retry budget for timeouts
    parse_response_fn=default_parse_response,  # async fn to extract data from a response
    stop_conditions=None,                      # StopConditions — halt the run on specific events
    input_buffer_size=100,                     # items pre-fetched from a generator into memory
    show_progress_bar=False,                   # print a live progress bar to the terminal
    timeout_s=30.0,                            # per-request timeout in seconds
    progress_bar_requests_threshold=1,         # min requests completed between bar redraws
    progress_bar_time_threshold=timedelta(seconds=0.5),  # min time between bar redraws
)
```

### `sparp.run(input_collection, estimated_input_collection_size=None)` — execution

```python
result: SparpResult = sparp.run(
    input_collection,                  # Iterable[dict] — kwargs forwarded to aiohttp session.request()
    estimated_input_collection_size=None,  # hint for progress % when input is a generator;
                                           # inferred automatically for lists and other sized iterables
)
```

### `ResponseState`

```python
class ResponseState(Enum):
    SUCCESS   = "SUCCESS"    # request completed successfully
    SOFT_FAIL = "SOFT_FAIL"  # transient failure — will be retried
    HARD_FAIL = "HARD_FAIL"  # permanent failure — recorded and skipped
```

### `Callbacks`

Optional hooks called on each outcome. All are `None` by default.

```python
Callbacks(
    on_success=lambda req, response: ...,
    on_hard_fail=lambda req, response: ...,
    on_soft_fail=lambda req, retry_count: ...,
    on_timeout=lambda req, retry_count: ...,
    on_max_retries_by_soft_fail_reached=lambda req: ...,
    on_max_retries_by_timeout_reached=lambda req: ...,
)
```

### `StopConditions`

Halt the entire run when a specific event occurs. All are `False` by default.

```python
StopConditions(
    stop_on_soft_fail=False,
    stop_on_hard_fail=False,
    stop_on_timeout=False,
    stop_on_max_retries_by_soft_fail_reached=False,
    stop_on_max_retries_by_timeout_reached=False,
)
```

### `SparpResult`

```python
@dataclass(frozen=True)
class SparpResult:
    stats: SparpStats
    success: list[Any]                            # parsed results from successful requests
    failed: list[Any]                             # parsed results from hard-failed requests
    max_retries_soft_fail_reached: list[dict]     # request dicts that exhausted their soft-fail budget
    max_retries_timeout_reached: list[dict]       # request dicts that exhausted their timeout budget

@dataclass(frozen=True)
class SparpStats:
    success: int          # total successful requests
    failed: int           # total hard-failed requests
    soft_retries: int     # cumulative soft-fail retry attempts
    timeout_retries: int  # cumulative timeout retry attempts
```

### `default_parse_response`

The built-in parser used when `parse_response_fn` is not overridden. Returns:

```python
{
    "input": request_dict,       # the original request kwargs
    "status": response.status,
    "text": await response.text(),
    "headers": dict(response.headers),
}
```

To customise, pass an `async` function with the same signature:

```python
async def my_parser(request_dict: dict, response: aiohttp.ClientResponse) -> Any:
    return {"status": response.status, "body": await response.json()}

sparp = SPARP(inspect_response=inspect_response, parse_response_fn=my_parser)
```

