"""Parameter dataclasses for Switch."""

import json
from dataclasses import dataclass, fields

from ..types.builtin_prompt import BuiltinPrompt
from ..types.comment_language import CommentLanguage
from ..types.log_level import LogLevel
from ..types.source_format import SourceFormat
from ..types.target_type import TargetType


@dataclass
class SwitchConfig:
    """Switch configuration from switch_config.yml."""

    target_type: str | None = None
    source_format: str | None = None
    comment_lang: str | None = None
    log_level: str | None = None
    token_count_threshold: int | None = None
    concurrency: int | None = None
    max_fix_attempts: int | None = None
    conversion_prompt_yaml: str | None = None
    output_extension: str | None = None
    sql_output_dir: str | None = None
    request_params: str | None = None

    # Enum fields that need normalization
    _ENUM_NORMALIZERS = {
        'target_type': TargetType.normalize,
        'source_format': SourceFormat.normalize,
        'comment_lang': CommentLanguage.normalize,
        'log_level': LogLevel.normalize,
    }

    @classmethod
    def from_dict(cls, data: dict) -> "SwitchConfig":
        """Create SwitchConfig from dict, ignoring unknown fields.

        Normalizes enum values to handle case-insensitive input (e.g., "NOTEBOOK" -> "notebook",
        "info" -> "INFO"). If normalization fails, the original value is preserved and will be
        validated later by the validator.
        """
        field_names = {f.name for f in fields(cls)}
        filtered_data = {}
        for key, value in data.items():
            if key in field_names:
                if key in cls._ENUM_NORMALIZERS and value is not None:
                    try:
                        value = cls._ENUM_NORMALIZERS[key](value)
                    except ValueError:
                        pass
                filtered_data[key] = value
        return cls(**filtered_data)

    def __str__(self) -> str:
        """Return string representation of all parameters."""
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)


@dataclass
class LakebridgeConfig:
    """Lakebridge configuration from config.yml transpiler_options."""

    catalog: str | None = None
    schema: str | None = None
    foundation_model: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "LakebridgeConfig":
        """Create LakebridgeConfig from dict, ignoring unknown fields."""
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered_data)

    def __str__(self) -> str:
        """Return string representation of all parameters."""
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)

    def __post_init__(self):
        """Normalize foundation_model from Lakebridge config."""
        if self.foundation_model and self.foundation_model.startswith("[DEFAULT] "):
            self.foundation_model = self.foundation_model.replace("[DEFAULT] ", "", 1)


class SwitchParameters:  # pylint: disable=too-many-instance-attributes
    """Unified Switch parameters with flattened access.

    Automatically resolves conversion_prompt_yaml from source_tech if not set.
    """

    # Switch config fields
    target_type: str | None
    source_format: str | None
    comment_lang: str | None
    log_level: str | None
    token_count_threshold: int | None
    concurrency: int | None
    max_fix_attempts: int | None
    conversion_prompt_yaml: str | None
    output_extension: str | None
    sql_output_dir: str | None
    request_params: str | None

    # Lakebridge config fields (YAML field names)
    catalog: str | None
    schema: str | None
    foundation_model: str | None

    # Runtime parameters
    input_dir: str | None
    output_dir: str | None
    source_tech: str | None

    def __init__(
        self,
        switch: SwitchConfig,
        lakebridge: LakebridgeConfig,
        input_dir: str | None = None,
        output_dir: str | None = None,
        source_tech: str | None = None,
    ):
        """Initialize with config and runtime parameters."""
        # Copy all fields from SwitchConfig
        self.target_type = switch.target_type
        self.source_format = switch.source_format
        self.comment_lang = switch.comment_lang
        self.log_level = switch.log_level
        self.token_count_threshold = switch.token_count_threshold
        self.concurrency = switch.concurrency
        self.max_fix_attempts = switch.max_fix_attempts
        self.conversion_prompt_yaml = switch.conversion_prompt_yaml
        self.output_extension = switch.output_extension
        self.sql_output_dir = switch.sql_output_dir
        self.request_params = switch.request_params

        # Copy all fields from LakebridgeConfig
        self.catalog = lakebridge.catalog
        self.schema = lakebridge.schema
        self.foundation_model = lakebridge.foundation_model

        # Set runtime parameters
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.source_tech = source_tech

        # Resolve conversion_prompt_yaml from source_tech if not set
        if self.source_tech and not self.conversion_prompt_yaml:
            self.conversion_prompt_yaml = str(BuiltinPrompt.from_name(self.source_tech).path)

    def __str__(self) -> str:
        """Return string representation of all parameters."""
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2)
