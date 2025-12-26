from src.sparp.sparp import ResponseState
import aiohttp
from typing import Any, Generator, Dict


def req_gen(count: int, port: int, path: str = "/test") -> Generator[Dict[str, Any], None, None]:
    for i in range(count):
        yield {"method": "POST", "url": f"http://localhost:{port}{path}", "json": {"value": i}}


def inspect_response(response: aiohttp.ClientResponse) -> ResponseState:
    if response.status == 200:
        return ResponseState.SUCCESS
    if response.status == 429:
        return ResponseState.SOFT_FAIL
    return ResponseState.HARD_FAIL
