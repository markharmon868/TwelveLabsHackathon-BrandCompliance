"""
Persistent Frame.io integration config stored in frameio_config.json at project root.
Decouples webhook guideline selection from environment variables.
"""

import json
from pathlib import Path

CONFIG_FILE = Path(__file__).parent.parent / "frameio_config.json"

_DEFAULTS: dict = {
    "default_guidelines": "",   # filename, e.g. "pureflow_water.json"
    "workspace_id": "",
    "webhook_id": "",
    "webhook_url": "",
    "custom_action_id": "",
    "custom_action_url": "",
}


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return dict(_DEFAULTS)
    try:
        with CONFIG_FILE.open() as f:
            data = json.load(f)
        return {**_DEFAULTS, **data}
    except Exception:
        return dict(_DEFAULTS)


def save_config(updates: dict) -> dict:
    config = load_config()
    for key in _DEFAULTS:
        if key in updates:
            config[key] = updates[key]
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    return config
