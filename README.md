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
## dict_keys(['text', 'status_code', 'json'])
```

### Reference
```python3
results = sparp.sparp(
  configs, # list of request configs. See below
  max_outstanding_requests = 1000, # max number of concurrent requests alive at the same time. Set to len(configs) for max speed, setting it higher will only introduce unnecessary overhead.
  time_between_requests = 0, # minimum amount of time between two requests
  ok_status_codes=[200],  # status codes that are deemed "success"
  stop_on_first_fail=False,  # wether to stop and return (not error) when a "failed" response is encountered
  disable_bar=False,  # do not print anything
  attempts=1,  # number of times to try the request (must be at least 1)
  retry_status_codes=[429]  # status codes to attempt a retry on
)
```

The `configs` should be 
