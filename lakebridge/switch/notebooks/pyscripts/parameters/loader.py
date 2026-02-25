from pathlib import Path
import yaml

from databricks.sdk import WorkspaceClient
from .models import SwitchConfig, LakebridgeConfig
from ..utils.common_utils import setup_logger

logger = setup_logger(__name__)


class ConfigLoader:
    """Load Switch and Lakebridge workspace configuration."""

    _SWITCH_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "resources" / "switch_config.yml"
    _LAKEBRIDGE_CONFIG_PATH_TPL = "/Workspace/Users/{user}/.lakebridge/config.yml"

    def __init__(self, ws: WorkspaceClient):
        self._ws = ws

    def _load_config_from_file(
        self, path: Path, config_name: str, config_class: type, extract_key: str | None = None
    ) -> SwitchConfig | LakebridgeConfig:
        """Load configuration from YAML file with error handling.

        Args:
            path: Path to the config file
            config_name: Name for logging (e.g., "Switch", "Lakebridge")
            config_class: Configuration class constructor
            extract_key: Optional key to extract from config dict before passing to class

        Returns:
            Configuration instance or empty instance on error
        """
        if not path.exists():
            logger.warning(f"{config_name} config file not found: {path}")
            return config_class()

        try:
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as e:
            logger.warning(f"Failed to load {config_name} config: {e}")
            return config_class()

        config = config if config is not None else {}

        if extract_key:
            config = config.get(extract_key, {})

        config_instance = config_class.from_dict(config)
        logger.info(f"Loaded {config_name} config from {path}:\n{config_instance}")
        return config_instance

    def load_switch_config(self, config_path: str | None = None) -> SwitchConfig:
        """Load Switch config from switch_config.yml or specified path."""
        path = Path(config_path) if config_path else self._SWITCH_DEFAULT_CONFIG_PATH
        return self._load_config_from_file(path, "Switch", SwitchConfig)

    def load_lakebridge_config(self, config_path: str | None = None) -> LakebridgeConfig:
        """Load transpiler options from Lakebridge config.yml or specified path."""
        path = Path(config_path) if config_path else self._get_default_lakebridge_path()
        return self._load_config_from_file(path, "Lakebridge", LakebridgeConfig, "transpiler_options")

    def _get_default_lakebridge_path(self) -> Path:
        """Get default Lakebridge config file path for current user."""
        if not self._ws:
            raise ValueError("WorkspaceClient required for default Lakebridge config path")
        current_user = self._ws.current_user.me().user_name
        return Path(self._LAKEBRIDGE_CONFIG_PATH_TPL.format(user=current_user))
