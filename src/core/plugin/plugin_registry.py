#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Plugin registry load/save/sync. Pure file I/O; PluginManager holds cache and dirty flag.
"""

import json
import os
import shutil
from datetime import datetime

from loguru import logger


def load_registry_from_file(registry_file):
    """Load plugin registry from disk. Caller is responsible for caching."""
    logger.debug(f"Loading plugin registry from: {registry_file}")

    if not os.path.exists(registry_file):
        logger.warning(f"Plugin registry file not found: {registry_file}")
        return {}

    try:
        with open(registry_file, "r") as f:
            registry_data = json.load(f)
        logger.debug(f"Successfully loaded registry with {len(registry_data)} plugins")
        for plugin_id, plugin_data in registry_data.items():
            state = plugin_data.get("state", None)
            if state:
                logger.debug(f"Registry: {plugin_id} -> state={state}")
            else:
                logger.debug(
                    f"Registry: {plugin_id} -> enabled={plugin_data.get('enabled', True)}, loaded={plugin_data.get('loaded', False)}"
                )
        return registry_data
    except Exception as e:
        logger.error(f"Error loading plugin registry from {registry_file}: {e}", exc_info=True)
        return {}


def build_registry_data(plugins_dict):
    """Build registry dict from plugins id->PluginInfo. Used by save/sync."""
    registry_data = {}
    now_str = str(datetime.now())
    for plugin_id, plugin_info in plugins_dict.items():
        registry_data[plugin_id] = {
            "state": plugin_info.state.name,
            "last_loaded": now_str if plugin_info.state.is_loaded else "",
            "path": plugin_info.path,
            "version": plugin_info.version,
        }
    return registry_data


def save_registry_to_file(registry_file, registry_data):
    """Write registry to disk. Uses atomic write (temp + replace)."""
    logger.debug(f"Saving plugin registry to: {registry_file}")

    try:
        os.makedirs(os.path.dirname(registry_file), exist_ok=True)
    except Exception as e:
        logger.error(f"Error creating registry directory: {e}", exc_info=True)
        return

    try:
        temp_file = registry_file + ".tmp"
        logger.debug(f"Writing registry to temporary file: {temp_file}")
        with open(temp_file, "w") as f:
            json.dump(registry_data, f, indent=2)
        if os.path.exists(registry_file):
            os.replace(temp_file, registry_file)
        else:
            shutil.move(temp_file, registry_file)
        logger.debug(f"Registry saved with {len(registry_data)} plugins")
    except PermissionError as e:
        logger.warning(
            f"Permission denied saving plugin registry (file may be locked): {e}"
        )
    except Exception as e:
        logger.error(f"Error saving plugin registry to {registry_file}: {e}", exc_info=True)
