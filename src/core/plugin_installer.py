#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Plugin installer for NetWORKS.
Downloads plugin ZIPs, verifies SHA-256, extracts to external_plugins_dir.
"""

import hashlib
import os
import shutil
import zipfile
from typing import Optional

from loguru import logger
from PySide6.QtCore import QObject, Signal

from .plugin_catalog import CatalogPluginInfo
from .plugin_types import PluginInfo


class PluginInstaller(QObject):
    """
    Downloads and installs plugins from catalog URLs.
    Extracts to external_plugins_dir/{plugin_id}/.
    """

    download_progress = Signal(int, int)  # bytes_done, bytes_total (0 = unknown)
    install_complete = Signal(object)  # PluginInfo
    install_error = Signal(str)

    def __init__(self, external_plugins_dir: str):
        super().__init__()
        self.external_plugins_dir = external_plugins_dir
        os.makedirs(external_plugins_dir, exist_ok=True)

    def _verify_sha256(self, path: str, expected: Optional[str]) -> bool:
        """Verify file SHA-256. If expected is None, return True."""
        if not expected:
            return True
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest().lower() == expected.lower()

    def _validate_installed(self, plugin_dir: str, plugin_id: str, entry_point: str) -> bool:
        """Check manifest and entry point exist."""
        manifest_path = os.path.join(plugin_dir, "manifest.json")
        plugin_json = os.path.join(plugin_dir, "plugin.json")
        plugin_yaml = os.path.join(plugin_dir, "plugin.yaml")
        if not any(os.path.exists(p) for p in (manifest_path, plugin_json, plugin_yaml)):
            return False
        entry_path = os.path.join(plugin_dir, entry_point)
        if not os.path.exists(entry_path):
            return False
        return True

    def install_from_url(
        self,
        url: str,
        plugin_id: str,
        sha256: Optional[str] = None,
    ) -> Optional[PluginInfo]:
        """
        Download ZIP from URL, verify optional SHA-256, extract to external_plugins_dir/{plugin_id}/.
        Returns PluginInfo if successful, None otherwise.
        """
        import urllib.request

        target_dir = os.path.join(self.external_plugins_dir, plugin_id)
        tmp_zip = os.path.join(self.external_plugins_dir, f".{plugin_id}.tmp.zip")

        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "NetWORKS-Plugin-Manager/1.0")
            with urllib.request.urlopen(req, timeout=120) as resp:
                content = resp.read()
            with open(tmp_zip, "wb") as f:
                f.write(content)

            if not self._verify_sha256(tmp_zip, sha256):
                self.install_error.emit(f"SHA-256 verification failed for {plugin_id}")
                return None

            if os.path.isdir(target_dir):
                shutil.rmtree(target_dir)
            os.makedirs(target_dir, exist_ok=True)

            with zipfile.ZipFile(tmp_zip, "r") as zf:
                zf.extractall(target_dir)

            # Read manifest to get entry_point and validate
            manifest_path = os.path.join(target_dir, "manifest.json")
            plugin_json = os.path.join(target_dir, "plugin.json")
            plugin_yaml = os.path.join(target_dir, "plugin.yaml")
            import json
            import yaml
            data = None
            if os.path.exists(manifest_path):
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            elif os.path.exists(plugin_json):
                with open(plugin_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
            elif os.path.exists(plugin_yaml):
                with open(plugin_yaml, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

            if not data:
                self.install_error.emit(f"Manifest not found in {plugin_id}")
                return None

            entry_point = data.get("entry_point")
            if not entry_point:
                self.install_error.emit(f"Manifest missing entry_point for {plugin_id}")
                return None

            if not self._validate_installed(target_dir, plugin_id, entry_point):
                self.install_error.emit(f"Validation failed: entry point {entry_point} not found")
                return None

            plugin_info = PluginInfo(
                data["id"],
                data["name"],
                data["version"],
                data.get("description", ""),
                data.get("author", ""),
                entry_point,
                target_dir,
            )
            plugin_info.min_app_version = data.get("min_app_version")
            plugin_info.changelog = data.get("changelog", [])
            if "requirements" in data:
                if "python" in data["requirements"]:
                    plugin_info.requirements["python"] = data["requirements"]["python"]
                if "system" in data["requirements"]:
                    plugin_info.requirements["system"] = data["requirements"]["system"]
            from .plugin.plugin_discovery import _resolve_plugin_icon_path
            plugin_info.icon_path = _resolve_plugin_icon_path(
                data.get("icon"), target_dir, plugin_id
            )

            self.install_complete.emit(plugin_info)
            return plugin_info

        except Exception as e:
            logger.error(f"Install failed for {plugin_id}: {e}")
            self.install_error.emit(str(e))
            if os.path.isdir(target_dir):
                try:
                    shutil.rmtree(target_dir)
                except OSError:
                    pass
            return None
        finally:
            if os.path.exists(tmp_zip):
                try:
                    os.remove(tmp_zip)
                except OSError:
                    pass

    def uninstall_plugin(self, plugin_id: str) -> bool:
        """Remove plugin directory from external_plugins_dir. Returns True if removed."""
        target_dir = os.path.join(self.external_plugins_dir, plugin_id)
        if not os.path.isdir(target_dir):
            return False
        try:
            shutil.rmtree(target_dir)
            return True
        except OSError as e:
            logger.error(f"Failed to uninstall {plugin_id}: {e}")
            return False

    def update_plugin(
        self,
        plugin_id: str,
        catalog_entry: CatalogPluginInfo,
    ) -> Optional[PluginInfo]:
        """Install/overwrite plugin from catalog entry (same as install_from_url)."""
        return self.install_from_url(
            catalog_entry.download_url,
            plugin_id,
            catalog_entry.sha256,
        )
