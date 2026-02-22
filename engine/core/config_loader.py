#!/usr/bin/env python3
"""
FILE: engine/core/config_loader.py
VERSION: 0.1
PURPOSE:
Loads Survivor configuration from config.json.

CONTRACT:
- Single source of runtime configuration
- No defaults invented in code
- Fail closed if config missing or malformed
"""

import json
import os
from typing import Dict, Any


CONFIG_PATH = os.path.join(
    os.path.dirname(__file__),
    "config.json"
)


def load_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        raise RuntimeError(f"Missing config file: {CONFIG_PATH}")

    with open(CONFIG_PATH, "r") as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON in config.json: {e}")

    return config