from enum import Enum
from typing import Any
from dataclasses import dataclass


class ResponseState(Enum):
    """Represents the classification of an HTTP response for retry logic."""

    HARD_FAIL = "HARD_FAIL"
    SOFT_FAIL = "SOFT_FAIL"
    SUCCESS = "SUCCESS"


@dataclass(frozen=True)
class SparpStats:
    """Data container for execution statistics.

    Attributes:
        success: Total number of successful requests.
        failed: Total number of hard-failed requests.
        soft_retries: Cumulative count of all soft-fail retry attempts.
        timeout_retries: Cumulative count of all timeout retry attempts.
    """

    success: int
    failed: int
    soft_retries: int
    timeout_retries: int


@dataclass(frozen=True)
class SparpResult:
    """Final result container for a SPARP run.

    Attributes:
        stats: Aggregated statistics.
        success: List of parsed successful responses.
        failed: List of parsed hard-fail responses.
        max_retries_soft_fail_reached: Requests abandoned after max soft retries.
        max_retries_timeout_reached: Requests abandoned after max timeout retries.
    """

    stats: SparpStats
    success: list[Any]
    failed: list[Any]
    max_retries_soft_fail_reached: list[dict[str, Any]]
    max_retries_timeout_reached: list[dict[str, Any]]
