class SPARPStopSignal(Exception):
    """Base exception for signals that should terminate the SPARP execution."""

    pass


class HardFailStop(SPARPStopSignal):
    """Raised when a hard failure occurs and stop_on_hard_fail is True."""

    pass


class SoftFailStop(SPARPStopSignal):
    """Raised when a soft failure occurs and stop_on_soft_fail is True."""

    pass


class TimeoutFailStop(SPARPStopSignal):
    """Raised when a timeout occurs and stop_on_timeout is True."""

    pass


class MaxRetriesStop(SPARPStopSignal):
    """Raised when the maximum retry limit is reached for a specific request."""

    pass
