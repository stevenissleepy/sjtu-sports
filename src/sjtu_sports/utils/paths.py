"""Runtime paths configurable through ``SJTU_SPORTS_HOME``."""

import os
from pathlib import Path


HOME = Path(os.environ.get("SJTU_SPORTS_HOME", ".")).resolve()
OUTPUT_DIR = HOME / "output"
AUTH_DIR = HOME / "auth"


def ensure_output_dir():
    """Create and return the runtime output directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def ensure_auth_dir():
    """Create and return the directory containing login state."""
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    return AUTH_DIR
