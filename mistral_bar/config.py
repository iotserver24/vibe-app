import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "mistral-bar"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "api_key": "",
    "model": "mistral-small-latest",
    "hotkey": "ctrl+alt+space",
    "working_dir": str(Path.home()),
    "max_tool_iterations": 8,
    "max_file_bytes": 60000,
    "history_limit": 20,
}


def load_config():
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    if os.environ.get("MISTRAL_API_KEY"):
        cfg["api_key"] = os.environ["MISTRAL_API_KEY"]
    return cfg


def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
