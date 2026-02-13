#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Update checker for NetWORKS.

Uses GitHub Releases API for the Stable channel (latest published release)
and branch raw manifest for Beta/Alpha/Development channels.
"""

import os
import json
import re
import urllib.request
import urllib.error
import ssl
from loguru import logger
from PySide6.QtCore import QObject, Signal
from .update_manager import UpdateManager

# Default repo (generalized for docs/packaging)
_DEFAULT_REPO = "https://github.com/chibashr/NetWORKS"


class UpdateChecker(QObject):
    """Class for checking for updates from GitHub."""
    
    # Signals
    update_available = Signal(str, str, str)  # current_version, new_version, release_notes
    check_complete = Signal(bool)  # updates_available
    
    def __init__(self, config=None):
        """Initialize the update checker.
        
        Args:
            config: Config instance for accessing settings.
        """
        super().__init__()
        self.config = config
        self.github_repo = _DEFAULT_REPO.rstrip("/")
        self.github_api_url = self._repo_url_to_api(self.github_repo)
        self.current_version = self._get_current_version()
        self.update_manager = UpdateManager(config)
        
        # Prefer general.repository_url, then update.git_remote_url
        custom_repo = ""
        if self.config:
            custom_repo = (
                self.config.get("general.repository_url", "") or
                self.config.get("update.git_remote_url", "")
            )
        if custom_repo:
            self.set_repository_url(custom_repo)
            self.update_manager.repository_url = self.github_repo
        
    @staticmethod
    def _repo_url_to_api(repo_url):
        """Convert GitHub repo URL to API base URL."""
        repo_url = (repo_url or "").rstrip("/")
        if "github.com" not in repo_url:
            return ""
        parts = repo_url.split("github.com/")
        if len(parts) != 2:
            return ""
        path = parts[1].split("#")[0].split("?")[0].rstrip("/")
        return f"https://api.github.com/repos/{path}"
    
    def _get_current_version(self):
        """Get the current version from the manifest file."""
        try:
            root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            manifest_path = os.path.join(root, "manifest.json")
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
                return manifest.get("version_string", "0.0.0")
        except Exception as e:
            logger.error(f"Error reading manifest file: {e}")
            return "0.0.0"
    
    def get_branch(self):
        """Get the configured update branch"""
        if self.config:
            branch_map = {
                "Stable": "stable",
                "Beta": "beta",
                "Alpha": "alpha",
                "Development": "main"
            }
            channel = self.config.get("general.update_channel", "Stable")
            return branch_map.get(channel, "stable")
        return "stable"  # Default to stable branch
    
    def check_for_updates(self, branch=None):
        """Check for updates from GitHub.
        
        For Stable channel uses GitHub Releases API (latest release).
        For Beta/Alpha/Development uses branch raw manifest.
        
        Args:
            branch: Branch to check (stable, beta, alpha, main).
                    If None, uses the configured update channel.
        
        Returns:
            tuple: (updates_available, current_version, new_version, release_notes)
        """
        if branch is None:
            branch = self.get_branch()
        
        logger.info(f"Checking for updates, channel branch: {branch}")
        
        if branch == "stable" and self.github_api_url:
            return self._check_via_releases_api()
        return self._check_via_branch_manifest(branch)
    
    def _check_via_releases_api(self):
        """Use GitHub Releases API to get latest release and compare version."""
        try:
            url = f"{self.github_api_url.rstrip('/')}/releases/latest"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": f"NetWORKS/{self.current_version}",
                    "Accept": "application/vnd.github+json",
                },
            )
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                if resp.getcode() != 200:
                    logger.warning(f"Releases API returned {resp.getcode()}, falling back to branch manifest")
                    return self._check_via_branch_manifest("stable")
                data = json.loads(resp.read().decode("utf-8"))
            
            tag_name = (data.get("tag_name") or "").strip()
            body = (data.get("body") or "").strip() or "No release notes available."
            # Normalize version: v0.10.6 -> 0.10.6
            remote_version = tag_name.lstrip("v") if tag_name else "0.0.0"
            if not re.match(r"[\d.]+\d", remote_version):
                # Not a valid version; fetch manifest from tag if possible
                manifest_url = f"https://raw.githubusercontent.com/{self._api_to_repo_path()}/{tag_name}/manifest.json"
                try:
                    m_req = urllib.request.Request(
                        manifest_url,
                        headers={"User-Agent": f"NetWORKS/{self.current_version}"},
                    )
                    with urllib.request.urlopen(m_req, timeout=8, context=ssl.create_default_context()) as m_resp:
                        if m_resp.getcode() == 200:
                            manifest = json.loads(m_resp.read().decode("utf-8"))
                            remote_version = manifest.get("version_string", remote_version)
                            body = manifest.get("release_notes", body)
                except Exception:
                    pass
            
            updates_available = self._compare_versions(remote_version, self.current_version)
            if updates_available:
                self.update_available.emit(self.current_version, remote_version, body)
            self.check_complete.emit(updates_available)
            return updates_available, self.current_version, remote_version, body
        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.debug("No latest release found, falling back to stable branch manifest")
                return self._check_via_branch_manifest("stable")
            logger.warning(f"GitHub API error {e.code}: {e.reason}")
            self.check_complete.emit(False)
            return False, self.current_version, "0.0.0", "Unable to check for updates (GitHub API error)"
        except (urllib.error.URLError, ssl.SSLError) as e:
            logger.warning(f"Network/SSL error while checking updates: {e}")
            self.check_complete.emit(False)
            return False, self.current_version, "0.0.0", "Unable to check for updates (network/SSL issue)"
        except Exception as e:
            logger.warning(f"Error checking for updates: {e}")
            self.check_complete.emit(False)
            return False, self.current_version, "0.0.0", "Error checking for updates"
    
    def _api_to_repo_path(self):
        """Return owner/repo from github_api_url (e.g. chibashr/NetWORKS)."""
        if not self.github_api_url or "api.github.com/repos/" not in self.github_api_url:
            return ""
        prefix = "https://api.github.com/repos/"
        if self.github_api_url.startswith(prefix):
            path = self.github_api_url[len(prefix):].rstrip("/")
            parts = path.split("/")
            return "/".join(parts[:2]) if len(parts) >= 2 else path
        return ""
    
    def _check_via_branch_manifest(self, branch):
        """Fetch manifest from branch raw URL and compare version."""
        manifest_url = f"{self.github_repo}/raw/{branch}/manifest.json"
        logger.debug(f"Fetching manifest from: {manifest_url}")
        try:
            req = urllib.request.Request(
                manifest_url,
                headers={"User-Agent": f"NetWORKS/{self.current_version}"},
            )
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                if resp.getcode() != 200:
                    self.check_complete.emit(False)
                    return False, self.current_version, "0.0.0", "Unable to check for updates"
                data = resp.read().decode("utf-8")
                manifest = json.loads(data)
            
            remote_version = manifest.get("version_string", "0.0.0")
            release_notes = manifest.get("release_notes", "No release notes available.")
            updates_available = self._compare_versions(remote_version, self.current_version)
            if updates_available:
                self.update_available.emit(self.current_version, remote_version, release_notes)
            self.check_complete.emit(updates_available)
            return updates_available, self.current_version, remote_version, release_notes
        except urllib.error.URLError as e:
            if isinstance(getattr(e, "reason", None), ssl.SSLError):
                logger.warning(f"SSL error while checking for updates: {e.reason}")
            else:
                logger.warning(f"Network error while checking for updates: {e}")
            self.check_complete.emit(False)
            return False, self.current_version, "0.0.0", "Unable to check for updates (network/SSL issue)"
        except Exception as e:
            logger.warning(f"Error checking for updates: {e}")
            self.check_complete.emit(False)
            return False, self.current_version, "0.0.0", "Error checking for updates"
            
    def _compare_versions(self, version1, version2):
        """Compare two version strings
        
        Args:
            version1: First version string (e.g., "0.8.45")
            version2: Second version string (e.g., "0.8.44")
            
        Returns:
            bool: True if version1 is newer than version2
        """
        # Extract version parts as integers
        parts1 = [int(x) for x in re.findall(r'\d+', version1)]
        parts2 = [int(x) for x in re.findall(r'\d+', version2)]
        
        # Pad the shorter list with zeros
        while len(parts1) < len(parts2):
            parts1.append(0)
        while len(parts2) < len(parts1):
            parts2.append(0)
            
        # Compare parts
        for p1, p2 in zip(parts1, parts2):
            if p1 > p2:
                return True
            elif p1 < p2:
                return False
                
        # If we get here, the versions are equal
        return False

    def set_repository_url(self, url):
        """Set a custom repository URL.
        
        Args:
            url: Full repository URL (e.g. https://github.com/username/repo)
        
        Returns:
            self, for chaining.
        """
        url = (url or "").strip().rstrip("/")
        if "github.com" not in url:
            logger.warning(f"Unsupported repository URL format: {url}")
            return self
        self.github_repo = url
        self.github_api_url = self._repo_url_to_api(url)
        logger.debug(f"Set GitHub repo: {self.github_repo}, API: {self.github_api_url}")
        return self 