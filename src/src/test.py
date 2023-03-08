from src.sparp import sparpp


def construct_configs():
    configs = []
    for _ in range(10000):
        configs.append({
            'method': 'get',
            'url': 'https://www.google.com',
            'headers': {},
        })
    return configs


def test():
    configs = construct_configs()
    results = sparp_.sparp(
        configs,
        max_outstanding_requests=200,
        ok_status_codes=[200],
        stop_on_first_fail=True
    )
    status_codes = [result.status for result in results if result is not None]
    print(status_codes)


if __name__ == "__main__":
    test()
