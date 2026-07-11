from typing import Callable, Any
import aiohttp


class StopConditions:
    """Configuration for early termination based on specific failure events."""

    def __init__(
        self,
        stop_on_soft_fail: bool = False,
        stop_on_hard_fail: bool = False,
        stop_on_max_retries_by_soft_fail_reached: bool = False,
        stop_on_max_retries_by_timeout_reached: bool = False,
        stop_on_timeout: bool = False,
    ) -> None:
        self.stop_on_soft_fail = stop_on_soft_fail
        self.stop_on_hard_fail = stop_on_hard_fail
        self.stop_on_max_retries_by_soft_fail_reached = stop_on_max_retries_by_soft_fail_reached
        self.stop_on_max_retries_by_timeout_reached = stop_on_max_retries_by_timeout_reached
        self.stop_on_timeout = stop_on_timeout


class Callbacks:
    """User-defined hooks for various lifecycle events in the request process."""

    def __init__(
        self,
        on_success: Callable[[dict[str, Any], aiohttp.ClientResponse], None] | None = None,
        on_hard_fail: Callable[[dict[str, Any], aiohttp.ClientResponse], None] | None = None,
        on_soft_fail: Callable[[dict[str, Any], int], None] | None = None,
        on_timeout: Callable[[dict[str, Any], int], None] | None = None,
        on_max_retries_by_soft_fail_reached: Callable[[dict[str, Any]], None] | None = None,
        on_max_retries_by_timeout_reached: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.on_success = on_success
        self.on_hard_fail = on_hard_fail
        self.on_soft_fail = on_soft_fail
        self.on_timeout = on_timeout
        self.on_max_retries_by_soft_fail_reached = on_max_retries_by_soft_fail_reached
        self.on_max_retries_by_timeout_reached = on_max_retries_by_timeout_reached
