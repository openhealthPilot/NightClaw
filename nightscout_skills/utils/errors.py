class NightscoutError(Exception):
    """Base error for Nightscout skill failures."""


class NightscoutConfigError(NightscoutError):
    """Raised when required Nightscout configuration is missing or invalid."""


class NightscoutRequestError(NightscoutError):
    """Raised when an HTTP request to Nightscout fails."""


class NightscoutResponseError(NightscoutError):
    """Raised when Nightscout returns malformed or unexpected data."""


class InvalidDateRangeError(NightscoutError, ValueError):
    """Raised when a requested date range is invalid."""
