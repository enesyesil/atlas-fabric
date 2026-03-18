import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]


def get_env_path() -> Path:
    custom_path = os.environ.get("ATLAS_FABRIC_ENV_FILE", "").strip()
    if custom_path:
        return Path(custom_path).expanduser()
    return _REPO_ROOT / ".env"


def load_environment(*, override: bool = True) -> bool:
    """
    Load AtlasFabric environment variables from the repo's .env file.

    By default, .env is treated as the main local source of truth and will
    override pre-existing process environment variables.
    """
    return load_dotenv(dotenv_path=get_env_path(), override=override)
