import time
import asyncio
import pytest
from aiohttp import web
from typing import Any, Dict, List
from collections.abc import AsyncGenerator


@pytest.fixture
async def tuned_fast_server() -> AsyncGenerator[None, None]:
    """Server that takes ~0.01s per request."""

    async def handle(request: web.Request) -> web.StreamResponse:
        await asyncio.sleep(0.01)
        return web.json_response({"status": "ok"})

    app = web.Application()
    app.router.add_post("/test", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8889)
    time.sleep(0.1)
    await site.start()
    yield
    await runner.cleanup()


@pytest.fixture
async def success_server() -> AsyncGenerator[Dict[str, List[Any]], None]:
    processed: List[Any] = []

    async def handle(request: web.Request) -> web.StreamResponse:
        data = await request.json()
        processed.append(data.get("value"))
        return web.json_response({"status": "ok", "echo": data.get("value")})

    app = web.Application()
    app.router.add_post("/test", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8765)
    await site.start()
    time.sleep(0.1)
    yield {"processed": processed}
    await runner.cleanup()


@pytest.fixture
async def rate_limited_server() -> AsyncGenerator[None, None]:
    attempts: Dict[Any, int] = {}

    async def handle(request: web.Request) -> web.StreamResponse:
        data = await request.json()
        val = data.get("value")
        attempts[val] = attempts.get(val, 0) + 1
        if attempts[val] <= 2:
            return web.json_response({"error": "limit"}, status=429)
        return web.json_response({"status": "ok"})

    app = web.Application()
    app.router.add_post("/test", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8766)
    time.sleep(0.1)
    await site.start()
    yield
    await runner.cleanup()


@pytest.fixture
async def failing_server() -> AsyncGenerator[None, None]:
    async def handle(request: web.Request) -> web.StreamResponse:
        return web.json_response({"error": "internal error"}, status=500)

    app = web.Application()
    app.router.add_post("/test", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8767)
    await site.start()
    time.sleep(0.1)
    yield
    await runner.cleanup()


@pytest.fixture
async def unresponsive_server() -> AsyncGenerator[None, None]:
    async def handle(request: web.Request) -> web.StreamResponse:
        await asyncio.sleep(10000)
        return web.json_response({"status": "never"})

    app = web.Application()
    app.router.add_post("/test", handle)
    runner = web.AppRunner(app, shutdown_timeout=0.1)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8769)
    await site.start()
    time.sleep(0.1)
    yield
    await runner.cleanup()


@pytest.fixture
async def timeout_server() -> AsyncGenerator[None, None]:
    """Server that always sleeps longer than the client timeout."""

    async def handle(request: web.Request) -> web.StreamResponse:
        # Sleep for a long time to trigger aiohttp.ClientTimeout
        await asyncio.sleep(10)
        return web.json_response({"status": "never"})

    app = web.Application()
    app.router.add_post("/test", handle)
    # We use a short shutdown_timeout so the test suite doesn't hang on cleanup
    runner = web.AppRunner(app, shutdown_timeout=0.1)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8770)
    await site.start()
    yield
    await runner.cleanup()


@pytest.fixture
async def flaky_timeout_server() -> AsyncGenerator[Dict[str, int], None]:
    """Server that times out N times for a specific value before succeeding."""
    attempts: Dict[Any, int] = {}

    async def handle(request: web.Request) -> web.StreamResponse:
        data = await request.json()
        val = data.get("value")
        attempts[val] = attempts.get(val, 0) + 1

        # Timeout the first 2 attempts
        if attempts[val] <= 2:
            await asyncio.sleep(10)
            return web.json_response({"error": "timeout"})

        return web.json_response({"status": "ok"})

    app = web.Application()
    app.router.add_post("/test", handle)
    runner = web.AppRunner(app, shutdown_timeout=0.1)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8771)
    await site.start()
    yield attempts
    await runner.cleanup()
