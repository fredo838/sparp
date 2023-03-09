# Documentation
`sparp` stands for *Simple Parallel Asynchronous Requests in Python*
### Purpose
Find `async` or `await` confusing, and just want to process a list of requests? Then this 
is the package for you. 
### Installation
```bash
python3 -m pip install python3 -m pip install git+https://github.com/fredo838/sparp.git
```

### Simple example
```python3
import sparp
configs = [{'method': 'get', 'url': 'https://www.google.com'} for _ in range(10000)]
results = sparp.sparp(configs, max_outstanding_requests=len(configs), =sparp.DontCare)
print(results[0].keys())
## dict_keys(['text', 'status_code', 'json', 'elapsed'])
```

### Reference
```python3
results = sparp.sparp(
  configs, # list of request configs. See below
  max_outstanding_requests = 1000, # max number of concurrent requests alive at the same time. Should be in [0, len(configs)]. Using len(configs) guarantees you won't bottleneck the processing.
  time_between_requests = 0, # minimum amount of time between two requests
  ok_status_codes=[200],  # status codes that are deemed "success"
  stop_on_first_fail=False,  # wether to stop and return (not error) when a "failed" response is encountered
  disable_bar=False,  # do not print anything
  attempts=1,  # number of times to try the request (must be at least 1)
  retry_status_codes=[429]  # status codes to attempt a retry on
)
```
### Small print
- each `config` in `configs` should be able to be passed to `aiohttp.ClientSession.request(**config)`
- `configs` should preferably be a `list` of `dict`s, but you can also use a `generator`, so if you want to make your request
as soon as you have created your `config`, you can.
- `max_outstanding_requests` is a mandatory paramater, but what should you use? We create a `consumer coroutine` (read: `while loop that makes requests`) for every item in `range(max_outstanding_requests)`, so the ideal value is just above the "actual" max amount of requests that will be active at the same time, but we don't know that beforehand. So rule of thumb:
  - try `100`, if not fast enough, make it `1000`, still not fast enough use `len(configs)`. 
  - using `len(configs)` ensures you wont bottleneck your application, but know that this creates `len(configs)` `coroutines` (so those `while loops`), so it should not be tooo much, let's say `<100000`.
  - if the `url` you call cannot scale beyond `1000` requests, than using values higher that `1000` will only hurt performance
