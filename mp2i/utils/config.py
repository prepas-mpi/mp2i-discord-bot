from pathlib import Path
from typing import Any, Optional

import tomllib as toml

_working_dir: Path = Path.cwd()
_config_path: Path = _working_dir / "config.toml"

_config: Optional[dict[str, Any]] = None
with _config_path.open("rb") as f:
    _config = toml.load(f)


class ConfigNotLoadedException(Exception):
    """
    Exception raised when the config has not been loaded
    """

    def __init__(self) -> None:
        """
        Supply exception message to parent class
        """
        super().__init__("Attempt to use configuration but it has not been loaded.")


def has_config() -> bool:
    """
    Check if config has been loaded

    Returns
    -------
    bool
        True if config has been loaded, False otherwise
    """
    return bool(_config)


def get_config() -> dict[str, Any]:
    """
    Return config if it has been loaded

    Returns
    -------
    dict[str, Any]
        Configuration content

    Raises
    ------
    ConfigNotLoadedException
        Config has not been loaded
    """
    if not _config:
        raise ConfigNotLoadedException()
    return _config


def get_config_deep(path: str) -> dict[str, Any]:
    node: dict[str, Any] = get_config()
    for part in path.split("."):
        node = node.get(part, {})
    return node
