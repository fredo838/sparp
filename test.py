from src.sparp import request_parallel


def construct_configs():
    configs = []
    for _ in range(300):
        configs.append({
            'method': 'get',
            'url': 'https://www.google.com',
            'headers': {},
        })
    return configs


def test():
    configs = construct_configs()
    results = request_parallel(
        configs,
        max_outstanding_requests=20,
        ok_status_codes=[200],
        stop_on_not_ok=True
    )
    status_codes = [result.status for result in results if result is not None]
    print(status_codes)


if __name__ == "__main__":
    test()
