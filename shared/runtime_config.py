"""Optional path configuration. Credentials are accepted only from environment variables."""
from pathlib import Path
import os


def path_setting(environment: str, key: str, default: str | Path) -> Path:
    if os.environ.get(environment):
        return Path(os.environ[environment]).expanduser()
    filename = os.environ.get("DAVID_OS_CONFIG")
    if not filename:
        return Path(default).expanduser()
    import yaml
    source = Path(filename).expanduser().resolve()
    config = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    if not isinstance(config, dict):
        raise ValueError("configuration must be a mapping")
    def reject_credentials(value):
        if isinstance(value, dict):
            for name, item in value.items():
                if any(word in str(name).lower() for word in ("api_key", "password", "secret", "token")):
                    raise ValueError("credentials belong in environment variables only")
                reject_credentials(item)
        elif isinstance(value, list):
            for item in value:
                reject_credentials(item)
    reject_credentials(config)
    value = config.get("paths", {}).get(key)
    if value is None:
        return Path(default).expanduser()
    result = Path(value).expanduser()
    return result if result.is_absolute() else source.parent / result
