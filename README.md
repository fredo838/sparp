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
import time
configs = [{'method': 'get', 'url': 'https://www.google.com'} for _ in range(10000)]
start_time = time.time()
results = sparp.sparp(configs, max_outstanding_requests=1000)
print(results[0].keys())
## dict_keys(['text', 'status_code', 'json'])
print(time.time() - start_time)
## 17.99310803413391
```

### Reference
```python3
results = sparp.sparp(configs, 
  max_outstanding_requests = 1000, # max number of concurrent requests alive at the same time
  ok_status_codes=[200],  # status codes that are deemed "success"
  stop_on_first_fail=False  # wether to stop and return (not error) when a "failed" response is encountered
)
```
