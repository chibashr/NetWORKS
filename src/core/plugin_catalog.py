#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Plugin catalog client for NetWORKS.
Fetches and caches the plugin catalog; filters by min_app_version.
"""

import json
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import List, Optional

from loguru import logger


@dataclass
class CatalogPluginInfo:
    """Catalog entry for a plugin (from plugin_catalog.json)."""

    id: str
    name: str
    version: str
    description: str
    author: str
    download_url: str
    sha256: Optional[str] = None
    min_app_version: Optional[str] = None
    changelog: Optional[List[dict]] = None


def _parse_version(v: str) -> tuple:
    """Parse version string to comparable tuple. Handles '10.5', '0.12.2', etc."""
    try:
        return tuple(int(x) for x in re.split(r"\.", str(v)) if x.isdigit())
    except (ValueError, TypeError):
        return (0,)


def _compare_versions(v1: str, v2: str) -> int:
    """Compare versions. Returns -1 if v1 < v2, 0 if equal, 1 if v1 > v2."""
    p1 = _parse_version(v1)
    p2 = _parse_version(v2)
    for i in range(max(len(p1), len(p2))):
        a = p1[i] if i < len(p1) else 0
        b = p2[i] if i < len(p2) else 0
        if a < b:
            return -1
        if a > b:
            return 1
    return 0


def _derive_catalog_url(repository_url: str, update_channel: str) -> str:
    """Derive catalog URL from repository_url and update_channel."""
    branch_map = {
        "Stable": "stable",
        "Beta": "beta",
        "Alpha": "alpha",
        "Development": "main",
    }
    branch = branch_map.get(update_channel, "stable")
    # Parse owner/repo from URL (e.g. https://github.com/owner/repo or owner/repo)
    url = (repository_url or "").rstrip("/")
    match = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$", url)
    if match:
        owner, repo = match.group(1), match.group(2)
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/plugin_catalog.json"
    return f"https://raw.githubusercontent.com/chibashr/NetWORKS/{branch}/plugin_catalog.json"


class PluginCatalogClient:
    """
    Fetches plugin catalog from configured URL, caches with TTL,
    filters by min_app_version.
    """

    def __init__(self, config, app_version: str):
        self.config = config
        self.app_version = app_version
        self._cache_path = None
        self._catalog_cache_ttl_minutes = 60

    def _get_cache_path(self) -> str:
        """Config dir for plugin_catalog_cache.json."""
        if self._cache_path is None:
            config_dir = getattr(self.config, "config_dir", None)
            if not config_dir:
                app_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                config_dir = os.path.join(app_dir, "config")
            self._cache_path = os.path.join(config_dir, "plugin_catalog_cache.json")
        return self._cache_path

    def _get_catalog_url(self) -> str:
        """Get catalog URL from config or derive from repository_url + update_channel."""
        url = self.config.get("plugins.catalog_url", None)
        if url:
            return url
        repo_url = self.config.get("general.repository_url", "")
        channel = self.config.get("general.update_channel", "Stable")
        return _derive_catalog_url(repo_url, channel)

    def _get_cache_ttl_minutes(self) -> int:
        return self.config.get("plugins.catalog_cache_ttl_minutes", 60)

    def _is_cache_valid(self) -> bool:
        path = self._get_cache_path()
        if not os.path.exists(path):
            return False
        try:
            import time
            mtime = os.path.getmtime(path)
            ttl_sec = self._get_cache_ttl_minutes() * 60
            return (time.time() - mtime) < ttl_sec
        except OSError:
            return False

    def _load_cached(self) -> Optional[List[CatalogPluginInfo]]:
        path = self._get_cache_path()
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            plugins = []
            for p in data.get("plugins", []):
                plugins.append(
                    CatalogPluginInfo(
                        id=p["id"],
                        name=p["name"],
                        version=p["version"],
                        description=p.get("description", ""),
                        author=p.get("author", ""),
                        download_url=p["download_url"],
                        sha256=p.get("sha256"),
                        min_app_version=p.get("min_app_version"),
                        changelog=p.get("changelog"),
                    )
            )
            return plugins
        except Exception as e:
            logger.warning(f"Failed to load catalog cache: {e}")
            return None

    def _get_local_catalog_path(self) -> Optional[str]:
        """Return path to plugin_catalog.json in project root, if it exists."""
        config_dir = getattr(self.config, "config_dir", None)
        if not config_dir:
            return None
        app_root = os.path.dirname(config_dir)
        path = os.path.join(app_root, "plugin_catalog.json")
        return path if os.path.exists(path) else None

    def _load_from_path(self, path: str) -> Optional[List[CatalogPluginInfo]]:
        """Load catalog from a JSON file path."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            plugins = []
            for p in data.get("plugins", []):
                plugins.append(
                    CatalogPluginInfo(
                        id=p["id"],
                        name=p["name"],
                        version=p["version"],
                        description=p.get("description", ""),
                        author=p.get("author", ""),
                        download_url=p["download_url"],
                        sha256=p.get("sha256"),
                        min_app_version=p.get("min_app_version"),
                        changelog=p.get("changelog"),
                    )
                )
            return plugins
        except Exception as e:
            logger.warning(f"Failed to load catalog from {path}: {e}")
            return None

    def _save_cache(self, plugins: List[CatalogPluginInfo]):
        path = self._get_cache_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "plugins": [
                {
                    "id": p.id,
                    "name": p.name,
                    "version": p.version,
                    "description": p.description,
                    "author": p.author,
                    "download_url": p.download_url,
                    "sha256": p.sha256,
                    "min_app_version": p.min_app_version,
                    "changelog": p.changelog,
                }
                for p in plugins
            ]
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _filter_by_app_version(self, plugins: List[CatalogPluginInfo]) -> List[CatalogPluginInfo]:
        """Filter out plugins whose min_app_version exceeds current app version."""
        result = []
        for p in plugins:
            if not p.min_app_version:
                result.append(p)
                continue
            if _compare_versions(self.app_version, p.min_app_version) >= 0:
                result.append(p)
            else:
                logger.debug(f"Filtering {p.id} (min_app_version {p.min_app_version} > {self.app_version})")
        return result

    def fetch_catalog(self) -> List[CatalogPluginInfo]:
        """
        Fetch catalog from URL. On error, returns empty list or cached data.
        Does not use cache for the fetch itself.
        """
        url = self._get_catalog_url()
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "NetWORKS-Plugin-Manager/1.0")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            plugins = []
            for p in data.get("plugins", []):
                plugins.append(
                    CatalogPluginInfo(
                        id=p["id"],
                        name=p["name"],
                        version=p["version"],
                        description=p.get("description", ""),
                        author=p.get("author", ""),
                        download_url=p["download_url"],
                        sha256=p.get("sha256"),
                        min_app_version=p.get("min_app_version"),
                        changelog=p.get("changelog"),
                    )
                )
            filtered = self._filter_by_app_version(plugins)
            self._save_cache(filtered)
            return filtered
        except Exception as e:
            logger.warning(f"Failed to fetch catalog from {url}: {e}")
            cached = self._load_cached()
            if cached is not None:
                return cached
            local_path = self._get_local_catalog_path()
            if local_path:
                plugins = self._load_from_path(local_path)
                if plugins:
                    filtered = self._filter_by_app_version(plugins)
                    self._save_cache(filtered)
                    logger.info(f"Loaded catalog from local file: {local_path}")
                    return filtered
            return []

    def get_catalog(self, force_refresh: bool = False) -> List[CatalogPluginInfo]:
        """
        Get catalog. Uses cache if valid and not force_refresh.
        """
        if not force_refresh and self._is_cache_valid():
            cached = self._load_cached()
            if cached is not None:
                return cached
        return self.fetch_catalog()

    def get_plugin_from_catalog(self, plugin_id: str) -> Optional[CatalogPluginInfo]:
        """Get a single catalog entry by ID."""
        for p in self.get_catalog():
            if p.id == plugin_id:
                return p
        return None

    def get_updates_available_for_installed(
        self, installed_plugins: dict
    ) -> List[CatalogPluginInfo]:
        """
        Compare catalog versions with installed. Return catalog entries for
        plugins that have a newer version in the catalog.
        installed_plugins: dict of plugin_id -> PluginInfo (or object with .version)
        """
        catalog = self.get_catalog()
        updates = []
        for cat in catalog:
            inst = installed_plugins.get(cat.id)
            if not inst:
                continue
            inst_version = getattr(inst, "version", None)
            if not inst_version:
                continue
            if _compare_versions(cat.version, inst_version) > 0:
                updates.append(cat)
        return updates
