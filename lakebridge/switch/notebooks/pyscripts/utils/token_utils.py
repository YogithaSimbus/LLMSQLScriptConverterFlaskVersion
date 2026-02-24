"""Token counting utilities for OpenAI and Claude models."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import tiktoken


class TokenizerType(str, Enum):
    """Enum representing different tokenizer types"""

    OPENAI = "openai"
    CLAUDE = "claude"


@dataclass(frozen=True)
class OpenAIConfig:
    """Configuration for OpenAI tokenizer"""

    encoding: str = "o200k_base"


@dataclass(frozen=True)
class ClaudeConfig:
    """Configuration for Claude tokenizer"""

    char_to_token_ratio: float = 3.4


class TokenCounter(Protocol):
    """Protocol for token counters"""

    def count_tokens(self, text: str) -> int:
        """Returns the number of tokens in a text string."""

    def get_type_info(self) -> tuple[str, str]:
        """Returns (tokenizer_type, model) for metadata."""


class OpenAITokenCounter:
    """Token counter for OpenAI models using tiktoken"""

    def __init__(self, config: OpenAIConfig):
        """Initialize with OpenAI configuration."""
        self.config = config
        self.encoding = tiktoken.get_encoding(config.encoding)

    def count_tokens(self, text: str) -> int:
        """Returns the number of tokens in a text string."""
        return len(self.encoding.encode(text))

    def get_type_info(self) -> tuple[str, str]:
        """Returns (tokenizer_type, model) for metadata."""
        return (TokenizerType.OPENAI.value, self.config.encoding)


class ClaudeTokenCounter:
    """Token counter for Claude models based on character to token ratio"""

    def __init__(self, config: ClaudeConfig):
        """Initialize with Claude configuration."""
        self.config = config

    def count_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in the given text for Claude models.

        This estimation is based on Anthropic's documentation, which states that
        approximately 200K tokens correspond to 680K Unicode characters. This implies
        an average of about 3.4 characters per token for Claude models.

        Reference:
        - https://docs.anthropic.com/en/docs/about-claude/models/all-models

        Args:
            text (str): The input text for which to estimate the token count.

        Returns:
            int: The estimated number of tokens in the input text.
        """
        char_count = len(text)
        estimated_tokens = char_count / self.config.char_to_token_ratio
        return int(estimated_tokens)

    def get_type_info(self) -> tuple[str, str]:
        """Returns (tokenizer_type, model) for metadata."""
        return (TokenizerType.CLAUDE.value, TokenizerType.CLAUDE.value)


def create_tokenizer_from_endpoint(endpoint_name: str) -> TokenCounter:
    """
    Create a tokenizer based on the endpoint name.

    Args:
        endpoint_name (str): The endpoint name to determine which tokenizer to use.
                           If 'claude' is in the name, Claude tokenizer is used,
                           otherwise OpenAI tokenizer is used.

    Returns:
        TokenCounter: An instance of the appropriate token counter
    """
    if 'claude' in endpoint_name.lower():
        return ClaudeTokenCounter(ClaudeConfig())
    return OpenAITokenCounter(OpenAIConfig())


def create_tokenizer_explicit(tokenizer_type: str, encoding_or_model: str) -> TokenCounter:
    """
    Create a tokenizer with explicit parameters.

    Args:
        tokenizer_type (str): Type of tokenizer to use ('openai' or 'claude')
        encoding_or_model (str): For OpenAI this is the encoding name,
                                for Claude this is currently not used

    Returns:
        TokenCounter: An instance of the appropriate token counter
    """
    try:
        tokenizer_enum = TokenizerType(tokenizer_type.lower())
        if tokenizer_enum == TokenizerType.OPENAI:
            return OpenAITokenCounter(OpenAIConfig(encoding=encoding_or_model))
        # CLAUDE
        return ClaudeTokenCounter(ClaudeConfig())
    except ValueError as e:
        supported = [t.value for t in TokenizerType]
        raise ValueError(f"Unsupported tokenizer type: {tokenizer_type}. Supported types: {supported}") from e
