"""Base classes for type definitions in Switch."""


class CaseInsensitiveEnumMixin:
    """Case-insensitive normalization mixin for Enum classes.

    Provides:
    - normalize(): Case-insensitive value normalization
    - get_supported_values(): List all valid enum values

    Examples:
        >>> class Color(CaseInsensitiveEnumMixin, str, Enum):
        ...     RED = "red"
        ...     BLUE = "blue"
        >>> Color.normalize("RED")
        "red"
        >>> Color.get_supported_values()
        ["red", "blue"]
    """

    @classmethod
    def get_supported_values(cls) -> list[str]:
        """Get list of all supported enum values.

        Returns:
            List of valid enum values

        Examples:
            >>> TargetType.get_supported_values()
            ["notebook", "file"]
            >>> LogLevel.get_supported_values()
            ["DEBUG", "INFO", "WARNING", "ERROR"]
        """
        return [member.value for member in cls]

    @classmethod
    def normalize(cls, value: str) -> str:
        """Normalize case-insensitive input to correct enum value.

        Args:
            value: Input value (case-insensitive)

        Returns:
            Correct enum value (e.g., "notebook", "INFO", "English")

        Raises:
            ValueError: If value is empty or doesn't match any enum value

        Examples:
            >>> TargetType.normalize("NOTEBOOK")
            "notebook"
            >>> TargetType.normalize("notebook")
            "notebook"
            >>> LogLevel.normalize("info")
            "INFO"
            >>> CommentLanguage.normalize("english")
            "English"
        """
        if not value:
            raise ValueError(f"{cls.__name__} value cannot be empty")

        supported_values = cls.get_supported_values()

        # Fast path: exact match
        if value in supported_values:
            return value

        # Case-insensitive match
        value_lower = value.lower()
        for valid_value in supported_values:
            if valid_value.lower() == value_lower:
                return valid_value  # Return original enum value

        raise ValueError(f"Invalid {cls.__name__}: '{value}'. " f"Supported: {', '.join(supported_values)}")
