"""Logging level definitions for Switch operations."""

from enum import Enum

from ._base import CaseInsensitiveEnumMixin


class LogLevel(CaseInsensitiveEnumMixin, str, Enum):
    """Logging levels for Switch operations

    This enum defines the supported logging levels for debugging and monitoring.
    These levels control the verbosity of output during execution.
    """

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
