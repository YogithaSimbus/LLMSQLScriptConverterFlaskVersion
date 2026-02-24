"""Conversion prompt management and YAML configuration handling."""

from pathlib import Path
from typing import TypedDict

import yaml
from omegaconf import OmegaConf
from omegaconf.errors import OmegaConfBaseException

from ..types.builtin_prompt import BuiltinPrompt


class FewShot(TypedDict):
    """Type definition for few-shot examples in the conversion process.

    Attributes:
        role: The role of the example (e.g., 'user', 'assistant').
        content: The content of the example.
    """

    role: str
    content: str


class ConversionPromptHelper:
    """Helper class for managing conversion prompts with pure YAML processing responsibility.

    This class handles YAML loading, processing, and prompt management.
    Path resolution is handled by BuiltinPrompt.
    """

    def __init__(self, yaml_path: str | Path, comment_lang: str = None):
        """Initialize with any YAML path.

        Args:
            yaml_path: Path to the YAML file containing prompts.
            comment_lang: Language to be used for comments in the converted code.
        """
        self.prompt_config = PromptConfig(conversion_prompt_yaml=str(yaml_path), comment_lang=comment_lang)

    def get_system_message(self) -> str:
        """Retrieve the system message for the conversion process.

        Returns:
            The formatted system message with the specified comment language.
        """
        return self.prompt_config.get_system_message()

    def get_few_shots(self) -> list[FewShot]:
        """Retrieve the few-shot examples for the conversion process.

        Returns:
            A list of few-shot examples to be used in the conversion.
        """
        return self.prompt_config.get_few_shots()


class PromptConfig:
    """Configuration class for managing conversion prompts.

    This class handles loading and managing prompt configurations from YAML files.
    """

    def __init__(self, conversion_prompt_yaml: str, comment_lang: str = None):
        """Initialize the PromptConfig.

        Args:
            conversion_prompt_yaml: Path to the YAML file containing prompts.
            comment_lang: Language to be used for comments.
        """
        self.conversion_prompt_yaml = conversion_prompt_yaml
        self.comment_lang = comment_lang
        self._prompts = self._load_prompts()

    def get_system_message(self) -> str:
        """Get system message with comment language interpolated.

        Returns:
            The system message with the comment language placeholders replaced.
        """
        system_message = self._prompts["system_message"]
        if self.comment_lang:
            system_message = system_message.replace("{comment_lang}", self.comment_lang)
        return system_message

    def get_few_shots(self) -> list[FewShot]:
        """Get few-shot examples from the loaded prompts.

        Returns:
            A list of few-shot examples, or an empty list if none are defined.
        """
        return self._prompts.get("few_shots", [])

    def _load_prompts(self) -> dict:
        """Load prompts from the YAML file.

        Returns:
            A dictionary containing the loaded prompts.

        Raises:
            FileNotFoundError: If the specified YAML file is not found.
            ValueError: If the YAML content is invalid or missing required keys.
            RuntimeError: If prompt loading fails for any other reason.
        """
        try:
            common_yaml = self._load_yaml_file(BuiltinPrompt.get_common_instruction_path())
            custom_yaml = self._load_yaml_file(self.conversion_prompt_yaml)
            prompts = self._merge_yaml_files(common_yaml, custom_yaml)
            if "system_message" not in prompts:
                raise ValueError("YAML must contain 'system_message' key")
            return prompts
        except (FileNotFoundError, ValueError):
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to load custom prompts from {self.conversion_prompt_yaml}") from e

    @staticmethod
    def _load_yaml_file(file_path: str | Path) -> dict:
        """Common helper method to load a YAML file.

        Args:
            file_path: Path to the YAML file to be loaded (string or Path object).

        Returns:
            The loaded YAML content as a dictionary.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the YAML content is not a dictionary.
        """
        path = Path(file_path) if not isinstance(file_path, Path) else file_path
        if not path.exists():
            raise FileNotFoundError(f"YAML file not found: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            yaml_content = yaml.safe_load(f)
        if not isinstance(yaml_content, dict):
            raise ValueError(f"YAML content must be a dictionary: {path}")
        return yaml_content

    @staticmethod
    def _merge_yaml_files(common_yaml: dict, custom_yaml: dict) -> dict:
        """
        Merges two YAML configuration dictionaries into a single dictionary.

        This method combines the keys and values from `common_yaml` and `custom_yaml`.
        If there are overlapping keys, the values from `custom_yaml` will take precedence.
        The resulting dictionary is resolved using OmegaConf to ensure all references
        and interpolations are processed.

        Args:
            common_yaml (dict): The base YAML configuration dictionary.
            custom_yaml (dict): The custom YAML configuration dictionary that overrides
                                or extends the base configuration.

        Returns:
            dict: A merged and resolved dictionary containing the combined configuration.
        """
        combined_yaml = {**common_yaml, **custom_yaml}
        try:
            conf = OmegaConf.create(combined_yaml)
            return OmegaConf.to_container(conf, resolve=True)
        except OmegaConfBaseException:
            # If OmegaConf fails due to unresolved interpolations, return the combined dict as-is
            return combined_yaml
