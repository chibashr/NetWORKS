#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Plugin discovery and manifest parsing. Manager passes itself for callbacks.
"""

import json
import os
import stat
import time
import traceback
from pathlib import Path

import yaml
from loguru import logger

from ..plugin_types import PluginInfo, PluginState


def _resolve_plugin_icon_path(icon_value, plugin_dir, plugin_id):
    """Resolve the plugin icon path from manifest or default location."""
    candidates = []
    if icon_value:
        candidates.append(icon_value)
    candidates.append(os.path.join("resources", "icons", f"{plugin_id}.svg"))
    for candidate in candidates:
        if not candidate:
            continue
        icon_path = candidate
        if not os.path.isabs(icon_path):
            icon_path = os.path.join(plugin_dir, icon_path)
        if os.path.exists(icon_path):
            return icon_path
    return None


def _extract_pkg_name(req_str):
    """Extract package name from requirement string."""
    return (
        req_str.split(">=")[0]
        .split("==")[0]
        .split(">")[0]
        .split("<")[0]
        .split("~")[0]
        .split("!")[0]
        .strip()
        .lower()
    )


def load_plugin_info_from_json(json_file, plugin_dir):
    """Load plugin info from JSON manifest. Pure function; no manager needed."""
    try:
        with open(json_file, "r") as f:
            data = json.load(f)
        required_fields = ["id", "name", "version", "entry_point"]
        for field in required_fields:
            if field not in data:
                logger.warning(f"Plugin JSON missing required field: {field}")
                return None
        plugin_info = PluginInfo(
            data["id"],
            data["name"],
            data["version"],
            data.get("description", ""),
            data.get("author", ""),
            data["entry_point"],
            plugin_dir,
        )
        plugin_info.min_app_version = data.get("min_app_version")
        plugin_info.max_app_version = data.get("max_app_version")
        plugin_info.dependencies = data.get("dependencies", [])
        plugin_info.changelog = data.get("changelog", [])
        plugin_info.icon_path = _resolve_plugin_icon_path(
            data.get("icon"), plugin_dir, plugin_info.id
        )
        if "requirements" in data:
            if "python" in data["requirements"]:
                plugin_info.requirements["python"] = data["requirements"]["python"]
            if "system" in data["requirements"]:
                plugin_info.requirements["system"] = data["requirements"]["system"]
        requirements_txt_path = os.path.join(plugin_dir, "requirements.txt")
        if os.path.exists(requirements_txt_path):
            try:
                with open(requirements_txt_path, "r") as f:
                    requirements_txt = [
                        line.strip()
                        for line in f
                        if line.strip() and not line.strip().startswith("#")
                    ]
                if requirements_txt:
                    existing = {_extract_pkg_name(r) for r in plugin_info.requirements["python"]}
                    for req in requirements_txt:
                        pkg = _extract_pkg_name(req)
                        if pkg not in existing:
                            plugin_info.requirements["python"].append(req)
                            existing.add(pkg)
            except Exception as e:
                logger.warning(f"Error reading requirements.txt for plugin {data['id']}: {e}")
        api_doc_path = os.path.join(plugin_dir, "API.md")
        if not os.path.exists(api_doc_path):
            logger.warning(
                f"Plugin {data['id']} is missing API.md documentation file. Documentation is required."
            )
            plugin_info.missing_docs = True
        return plugin_info
    except Exception as e:
        logger.error(f"Error loading plugin info from JSON: {e}")
        return None


def load_plugin_info_from_yaml(yaml_file, plugin_dir):
    """Load plugin info from YAML manifest. Pure function."""
    try:
        with open(yaml_file, "r") as f:
            data = yaml.safe_load(f)
        required_fields = ["id", "name", "version", "entry_point"]
        for field in required_fields:
            if field not in data:
                logger.warning(f"Plugin YAML missing required field: {field}")
                return None
        plugin_info = PluginInfo(
            data["id"],
            data["name"],
            data["version"],
            data.get("description", ""),
            data.get("author", ""),
            data["entry_point"],
            plugin_dir,
        )
        plugin_info.min_app_version = data.get("min_app_version")
        plugin_info.max_app_version = data.get("max_app_version")
        plugin_info.dependencies = data.get("dependencies", [])
        plugin_info.changelog = data.get("changelog", [])
        plugin_info.icon_path = _resolve_plugin_icon_path(
            data.get("icon"), plugin_dir, plugin_info.id
        )
        if "requirements" in data:
            if "python" in data["requirements"]:
                plugin_info.requirements["python"] = data["requirements"]["python"]
            if "system" in data["requirements"]:
                plugin_info.requirements["system"] = data["requirements"]["system"]
        requirements_txt_path = os.path.join(plugin_dir, "requirements.txt")
        if os.path.exists(requirements_txt_path):
            try:
                with open(requirements_txt_path, "r") as f:
                    requirements_txt = [
                        line.strip()
                        for line in f
                        if line.strip() and not line.strip().startswith("#")
                    ]
                if requirements_txt:
                    existing = {_extract_pkg_name(r) for r in plugin_info.requirements["python"]}
                    for req in requirements_txt:
                        pkg = _extract_pkg_name(req)
                        if pkg not in existing:
                            plugin_info.requirements["python"].append(req)
                            existing.add(pkg)
            except Exception as e:
                logger.warning(f"Error reading requirements.txt for plugin {data['id']}: {e}")
        return plugin_info
    except Exception as e:
        logger.error(f"Error loading plugin info from YAML: {e}")
        return None


def discover_plugins_in_directory(manager, directory):
    """Discover plugins in a directory. Calls manager.validate_plugin and manager._is_plugin_compatible."""
    plugins = {}
    logger.debug(f"_discover_plugins_in_directory: Checking {directory}")
    is_network = directory.startswith("\\\\") or (
        len(directory) > 2
        and directory[1:3] == ":\\"
        and any(
            x in directory
            for x in ("Synology", "OneDrive", "Dropbox", "Google")
        )
    )
    if is_network:
        logger.warning(
            f"External plugins directory appears to be on a network/synced drive: {directory}"
        )
    try:
        if not os.path.exists(directory):
            logger.warning(f"Plugin directory not found: {directory}")
            return plugins
    except Exception as e:
        logger.error(f"Error checking directory existence: {e}")
        return plugins
    try:
        start = time.time()
        items = os.listdir(directory)
        if time.time() - start > 2.0:
            logger.warning(f"Directory listing took {time.time() - start:.2f}s")
    except (OSError, PermissionError) as e:
        logger.error(f"Error listing directory {directory}: {e}")
        return plugins
    except Exception as e:
        logger.error(f"Unexpected error listing directory {directory}: {e}", exc_info=True)
        return plugins
    for item in items:
        try:
            plugin_dir = os.path.join(directory, item)
            if not os.path.isdir(plugin_dir):
                continue
            manifest_json = os.path.join(plugin_dir, "manifest.json")
            plugin_json = os.path.join(plugin_dir, "plugin.json")
            plugin_yaml = os.path.join(plugin_dir, "plugin.yaml")
            plugin_info = None
            if os.path.exists(manifest_json):
                plugin_info = load_plugin_info_from_json(manifest_json, plugin_dir)
            elif os.path.exists(plugin_json):
                plugin_info = load_plugin_info_from_json(plugin_json, plugin_dir)
            elif os.path.exists(plugin_yaml):
                plugin_info = load_plugin_info_from_yaml(plugin_yaml, plugin_dir)
            if not plugin_info:
                continue
            if not manager._is_plugin_compatible(plugin_info):
                logger.warning(f"Plugin {plugin_info.id} is not compatible with current app version")
                plugin_info.state = PluginState.ERROR
                plugin_info.error = "Incompatible with current app version"
                continue
            validation = manager.validate_plugin(
                plugin_info,
                check_structure=True,
                check_requirements=False,
                check_dependencies=False,
            )
            if not validation["valid"]:
                logger.warning(
                    f"Plugin {plugin_info.id} failed validation: {', '.join(validation['errors'])}"
                )
                plugin_info.state = PluginState.ERROR
                plugin_info.error = "; ".join(validation["errors"])
                continue
            if validation.get("warnings"):
                logger.debug(
                    f"Plugin {plugin_info.id} has validation warnings: {', '.join(validation['warnings'])}"
                )
            plugins[plugin_info.id] = plugin_info
            logger.debug(f"Discovered plugin: {plugin_info.id}")
        except Exception as e:
            logger.error(f"Error processing plugin directory {item}: {e}", exc_info=True)
    return plugins


def run_discovery(manager):
    """Run full discovery: internal, external, workspace dirs; merge registry state; sync. Modifies manager.plugins."""
    if manager._discovering:
        logger.warning("Plugin discovery already in progress, skipping duplicate call")
        return manager.plugins
    manager._discovering = True
    try:
        logger.info("Discovering plugins...")
        manager.plugins = {}
        registry = manager._load_registry()
        logger.debug(f"Registry loaded with {len(registry)} entries")
        logger.debug(f"Discovery call stack:\n{''.join(traceback.format_stack()[-3:-1])}")
        discovered_plugins = {}
        if manager.internal_plugins_dir:
            try:
                internal = discover_plugins_in_directory(manager, manager.internal_plugins_dir)
                discovered_plugins.update(internal)
            except Exception as e:
                logger.error(f"Error discovering internal plugins: {e}", exc_info=True)
        if manager.external_plugins_dir:
            try:
                external = discover_plugins_in_directory(manager, manager.external_plugins_dir)
                discovered_plugins.update(external)
            except Exception as e:
                logger.error(f"Error discovering external plugins: {e}", exc_info=True)
        try:
            if (
                hasattr(manager.app, "device_manager")
                and getattr(manager.app.device_manager, "current_workspace", None)
            ):
                dm = manager.app.device_manager
                ws_dir = os.path.join(dm.workspaces_dir, dm.current_workspace)
                workspace_plugins_dir = os.path.join(ws_dir, "plugins")
                try:
                    st = os.stat(workspace_plugins_dir)
                    if stat.S_ISDIR(st.st_mode):
                        wp = discover_plugins_in_directory(manager, workspace_plugins_dir)
                        discovered_plugins.update(wp)
                except (OSError, FileNotFoundError):
                    pass
        except Exception as e:
            logger.warning(f"Error checking workspace plugins: {e}", exc_info=True)
        for plugin_id, plugin_info in discovered_plugins.items():
            if plugin_id in registry:
                pd = registry[plugin_id]
                if "state" in pd:
                    try:
                        plugin_info.state = PluginState[pd["state"]]
                    except (KeyError, ValueError):
                        plugin_info.state = PluginState.DISCOVERED
                else:
                    plugin_info.state = PluginState.from_enabled_loaded(
                        pd.get("enabled", True), pd.get("loaded", False)
                    )
            else:
                plugin_info.state = PluginState.DISCOVERED
            manager.plugins[plugin_id] = plugin_info
        manager._registry_cache = {
            pid: registry[pid] for pid in registry if pid in manager.plugins
        }
        manager._registry_dirty = True
        try:
            manager._sync_registry()
        except Exception as e:
            logger.error(f"Error syncing plugin registry: {e}", exc_info=True)
        logger.info(f"Discovered {len(manager.plugins)} plugins")
        return manager.plugins
    finally:
        manager._discovering = False
