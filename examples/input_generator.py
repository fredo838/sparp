import aiohttp
from typing import Generator, Dict, Any
from sparp.sparp import SPARP, ResponseState


def inspect_response(response: aiohttp.ClientResponse) -> ResponseState:
    if response.status == 200:
        return ResponseState.SUCCESS
    if response.status == 429 or response.status == 502:
        return ResponseState.SOFT_FAIL
    return ResponseState.HARD_FAIL


def my_generator(count: int) -> Generator[Dict[str, Any], None, None]:
    for i in range(count):
        yield {"method": "GET", "url": f"https://httpbin.org/get?id={i}"}


def main():
    # Use a generator instead of a list
    gen = my_generator(100)

    sparp = SPARP(
        input_collection=gen,
        inspect_response=inspect_response,
        concurrency=10,
        show_progress_bar=True,
        input_buffer_size=2,
    )

    result = sparp.main()
    print(f"Processed {len(result.success)} items from generator.")


if __name__ == "__main__":
    main()
