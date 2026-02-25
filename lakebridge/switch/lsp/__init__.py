from pathlib import Path
import yaml

def get_switch_dialects() -> list[str]:

    config_path = Path(__file__).parent / "config.yml"
    path = Path(config_path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    dialects = data.get("remorph", {}).get("dialects", [])
    return sorted(dialects) if dialects else []