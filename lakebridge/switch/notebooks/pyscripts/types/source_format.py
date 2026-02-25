"""Source file format type definitions for preprocessing in Switch conversion."""

from enum import Enum

from ._base import CaseInsensitiveEnumMixin


class SourceFormat(CaseInsensitiveEnumMixin, str, Enum):
    """Source file format types for preprocessing

    This enum defines the supported source file formats and their preprocessing behavior:
    - SQL: SQL files that require comment removal and whitespace normalization
    - GENERIC: Generic text files that require no preprocessing
    """

    SQL = "sql"
    GENERIC = "generic"
