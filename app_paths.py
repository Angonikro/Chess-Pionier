"""Per-user paths and one-time migration for Chess Pionier."""
from pathlib import Path
import os
import shutil

APP_DIR = "chess-pionier"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_DIR
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_DIR
SETTINGS_FILE = CONFIG_DIR / "settings.ini"
ENGINES_FILE = CONFIG_DIR / "engines.json"


def _migrate_once():
    """Preserve settings from older releases that used the working directory."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parent
    legacy_settings = root / "data" / "settings.ini"
    legacy_engines = root / "engines.json"
    for old, new in ((legacy_settings, SETTINGS_FILE), (legacy_engines, ENGINES_FILE)):
        try:
            if old.is_file() and not new.exists():
                shutil.copy2(old, new)
        except OSError:
            pass


_migrate_once()
