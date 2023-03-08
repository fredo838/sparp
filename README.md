# Documentation
`sparp` stands for *Simple Parallel Asynchronous Requests in Python*

### Installation
```python3
python3 -m pip install python3 -m pip install git+https://github.com/fredo838/sparp.git
```

### Reference
```python3
import sparp
configs = []
for _ in range(10000):
  configs.append({
    'method': 'get',
    'url': 'https://www.google.com',
    'headers': {},
  })
results = sparp.sparp(configs,
  max_outstanding_requests = 1000, # max number of concurrent requests alive at the same time
  ok_status_codes=[200],  # status codes that are deemed "success"
  stop_on_first_fail=False  # wether to stop and return (not error) when a "failed" response is encountered
)

```
