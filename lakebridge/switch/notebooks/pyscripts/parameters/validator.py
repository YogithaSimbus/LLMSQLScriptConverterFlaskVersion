"""Parameter validation for Switch."""

import json

from ..types.comment_language import CommentLanguage
from ..types.log_level import LogLevel
from ..types.source_format import SourceFormat
from ..types.target_type import TargetType
from .models import SwitchParameters


class SwitchParameterValidator:
    """Validates Switch parameters with error accumulation."""

    def __init__(self):
        self.errors: list[str] = []

    def validate(self, params: SwitchParameters) -> list[str]:
        """Validate parameters.

        Args:
            params: SwitchParameters instance to validate

        Returns:
            List of validation error messages. Empty list if all validations pass.
        """
        self.errors = []

        # Enum validations
        self._validate_enum(params.target_type, TargetType.get_supported_values(), "target_type")
        self._validate_enum(params.source_format, SourceFormat.get_supported_values(), "source_format")
        self._validate_enum(params.comment_lang, CommentLanguage.get_supported_values(), "comment_lang")
        self._validate_enum(params.log_level, LogLevel.get_supported_values(), "log_level")

        # Integer validations
        self._validate_positive_int(params.token_count_threshold, "token_count_threshold")
        self._validate_positive_int(params.concurrency, "concurrency")
        self._validate_non_negative_int(params.max_fix_attempts, "max_fix_attempts")

        # JSON format validation
        self._validate_json_format(params.request_params, "request_params")

        # Workspace path validations
        self._validate_workspace_path(params.output_dir, "output_dir", required=True)
        self._validate_workspace_path(params.sql_output_dir, "sql_output_dir", required=False)

        # Dependency validations
        self._validate_target_dependencies(params.target_type, params.output_extension)

        return self.errors

    def _validate_enum(self, value: str | None, valid_values: list[str], param_name: str) -> None:
        """Validate enum parameter against valid values."""
        if value is None:
            self.errors.append(f"{param_name} is required but got None")
            return
        if value not in valid_values:
            self.errors.append(f"Invalid {param_name}: '{value}'. Supported: {', '.join(valid_values)}")

    def _validate_positive_int(self, value: int | None, param_name: str) -> None:
        """Validate that integer parameter is positive."""
        if value is None:
            self.errors.append(f"{param_name} is required but got None")
            return
        if not isinstance(value, int):
            self.errors.append(f"{param_name} must be int, got {type(value).__name__}")
            return
        if value <= 0:
            self.errors.append(f"{param_name} must be positive, got: {value}")

    def _validate_non_negative_int(self, value: int | None, param_name: str) -> None:
        """Validate that integer parameter is non-negative (>= 0)."""
        if value is None:
            self.errors.append(f"{param_name} is required but got None")
            return
        if not isinstance(value, int):
            self.errors.append(f"{param_name} must be int, got {type(value).__name__}")
            return
        if value < 0:
            self.errors.append(f"{param_name} must be non-negative, got: {value}")

    def _validate_json_format(self, value: str, param_name: str) -> None:
        """Validate JSON string format."""
        if value:
            try:
                json.loads(value)
            except json.JSONDecodeError as e:
                self.errors.append(f"{param_name} is not valid JSON: {e}")

    def _validate_workspace_path(self, path: str, param_name: str, required: bool = True) -> None:
        """Validate Databricks workspace path format."""
        if not path and not required:
            return
        if not path:
            self.errors.append(f"{param_name} is required")
            return
        if not (path.startswith("/Workspace/") or path.startswith("/Users/") or path.startswith("/Shared/")):
            self.errors.append(
                f"{param_name} must be a Databricks workspace path (start with /Workspace/, /Users/, or /Shared/), got: {path}"
            )

    def _validate_target_dependencies(self, target_type: str, output_extension: str) -> None:
        """Validate target-specific parameter dependencies."""
        if target_type == "file" and not output_extension:
            self.errors.append("output_extension is required when target_type='file'")
