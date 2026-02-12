#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Dynamically scan plugins/ directory and build plugin packages.
Also generates plugin_catalog.json from discovered manifests.
No hardcoded plugin IDs or lists.
"""

import argparse
import hashlib
import json
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path

# Exclusions for packaging (per plan)
EXCLUDE_PATTERNS = frozenset({
    "__pycache__",
    ".git",
    ".gitignore",
    ".coveragerc",
    "pytest.ini",
    "requirements-dev.txt",
})
EXCLUDE_SUFFIXES = (".pyc", ".pyo")


def _resolve_repo_env():
    """Get repo owner/name from GITHUB_REPOSITORY env (e.g. 'owner/repo')."""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if repo:
        parts = repo.split("/", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
    return None, None


def _resolve_branch():
    """Get branch from github.ref (e.g. refs/heads/stable -> stable)."""
    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/heads/"):
        return ref[len("refs/heads/"):]
    return "stable"


def _should_exclude(name):
    """Return True if file/dir should be excluded from ZIP."""
    if name in EXCLUDE_PATTERNS:
        return True
    if name.endswith(EXCLUDE_SUFFIXES):
        return True
    # Exclude *.md except API.md
    if name.endswith(".md") and name != "API.md":
        return True
    return False


def _discover_plugins(plugins_dir):
    """
    Scan plugins_dir for subdirs with manifest.json, plugin.json, or plugin.yaml.
    Returns list of (plugin_dir, manifest_data, manifest_path).
    """
    if not os.path.isdir(plugins_dir):
        return []

    result = []
    for item in sorted(os.listdir(plugins_dir)):
        plugin_dir = os.path.join(plugins_dir, item)
        if not os.path.isdir(plugin_dir):
            continue

        manifest_json = os.path.join(plugin_dir, "manifest.json")
        plugin_json = os.path.join(plugin_dir, "plugin.json")
        plugin_yaml = os.path.join(plugin_dir, "plugin.yaml")
        manifest_path = None
        data = None

        if os.path.exists(manifest_json):
            manifest_path = manifest_json
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        elif os.path.exists(plugin_json):
            manifest_path = plugin_json
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        elif os.path.exists(plugin_yaml):
            manifest_path = plugin_yaml
            try:
                import yaml
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            except ImportError:
                print("Warning: PyYAML not installed, skipping plugin.yaml plugins", file=sys.stderr)
                continue

        if not data:
            continue

        required = ["id", "name", "version", "entry_point"]
        missing = [f for f in required if f not in data]
        if missing:
            print(f"Warning: {plugin_dir} missing required fields: {missing}", file=sys.stderr)
            continue

        result.append((plugin_dir, data, manifest_path))

    return result


def _compute_sha256(zip_path):
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_plugin(plugin_dir, manifest_data, build_dir):
    """
    Build a single plugin ZIP. Contents are plugin dir contents directly (no parent folder).
    Returns (zip_path, sha256).
    """
    plugin_id = manifest_data["id"]
    version = manifest_data["version"]
    zip_name = f"{plugin_id}-{version}.zip"
    zip_path = os.path.join(build_dir, zip_name)

    os.makedirs(build_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(plugin_dir):
            # Filter dirs
            dirs[:] = [d for d in dirs if not _should_exclude(d)]

            rel_root = os.path.relpath(root, plugin_dir)
            for f in files:
                if _should_exclude(f):
                    continue
                fp = os.path.join(root, f)
                arcname = os.path.join(rel_root, f) if rel_root != "." else f
                zf.write(fp, arcname)

    sha = _compute_sha256(zip_path)
    return zip_path, sha


def generate_catalog(plugins_dir, output_path, repo_owner=None, repo_name=None, branch=None):
    """
    Generate plugin_catalog.json from scanned manifests.
    If repo_owner/repo_name not provided, uses GITHUB_REPOSITORY env.
    """
    discovered = _discover_plugins(plugins_dir)
    if not repo_owner or not repo_name:
        repo_owner, repo_name = _resolve_repo_env()
    if not repo_owner or not repo_name:
        repo_owner = "chibashr"
        repo_name = "NetWORKS"
    if not branch:
        branch = _resolve_branch()

    base_url = f"https://github.com/{repo_owner}/{repo_name}/releases/download/plugins"
    plugins = []
    for plugin_dir, data, _ in discovered:
        plugin_id = data["id"]
        version = data["version"]
        download_url = f"{base_url}/{plugin_id}-{version}.zip"
        entry = {
            "id": plugin_id,
            "name": data["name"],
            "version": version,
            "description": data.get("description", ""),
            "author": data.get("author", ""),
            "download_url": download_url,
            "min_app_version": data.get("min_app_version"),
            "changelog": data.get("changelog", []),
        }
        # Add sha256 if we have a built zip
        dist_dir = os.path.join(os.path.dirname(plugins_dir), "dist", "plugins")
        zip_path = os.path.join(dist_dir, f"{plugin_id}-{version}.zip")
        if os.path.exists(zip_path):
            entry["sha256"] = _compute_sha256(zip_path)
        else:
            entry["sha256"] = None
        plugins.append(entry)

    catalog = {
        "version": "1.0",
        "min_app_version": "0.12.0",
        "updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "plugins": plugins,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Build plugin packages and optionally generate catalog"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=True,
        help="Build all discovered plugins (default)",
    )
    parser.add_argument(
        "--plugin",
        metavar="ID",
        help="Build only the specified plugin by ID",
    )
    parser.add_argument(
        "--generate-catalog",
        action="store_true",
        help="Generate plugin_catalog.json from discovered manifests",
    )
    parser.add_argument(
        "--output",
        default="plugin_catalog.json",
        help="Output path for catalog (default: plugin_catalog.json)",
    )
    parser.add_argument(
        "--plugins-dir",
        default=None,
        help="Plugins directory (default: repo_root/plugins)",
    )
    parser.add_argument(
        "--dist-dir",
        default=None,
        help="Output dir for ZIPs (default: repo_root/dist/plugins)",
    )
    args = parser.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    plugins_dir = args.plugins_dir or os.path.join(repo_root, "plugins")
    dist_dir = args.dist_dir or os.path.join(repo_root, "dist", "plugins")

    discovered = _discover_plugins(plugins_dir)
    if not discovered:
        print("No plugins discovered in", plugins_dir)
        sys.exit(0)

    to_build = discovered
    if args.plugin:
        to_build = [(d, m, p) for d, m, p in discovered if m["id"] == args.plugin]
        if not to_build:
            print(f"Plugin '{args.plugin}' not found")
            sys.exit(1)

    for plugin_dir, manifest_data, manifest_path in to_build:
        plugin_id = manifest_data["id"]
        version = manifest_data["version"]
        zip_path, sha = build_plugin(plugin_dir, manifest_data, dist_dir)
        print(f"Built {plugin_id} {version} -> {zip_path} (sha256: {sha[:16]}...)")

    if args.generate_catalog:
        output_path = os.path.join(repo_root, args.output) if not os.path.isabs(args.output) else args.output
        generate_catalog(plugins_dir, output_path)
        print(f"Generated catalog: {output_path}")


if __name__ == "__main__":
    main()
