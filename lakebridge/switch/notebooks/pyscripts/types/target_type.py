"""Target output type definitions for Switch conversion."""

from enum import Enum

from ._base import CaseInsensitiveEnumMixin


class TargetType(CaseInsensitiveEnumMixin, str, Enum):
    """Target output types for Switch conversion

    This enum defines the supported output formats for the conversion process.
    Each type determines the processing flow and output format.
    """

    NOTEBOOK = "notebook"
    FILE = "file"
