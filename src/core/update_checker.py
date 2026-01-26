#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Update checker for NetWORKS
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

class UpdateChecker(QObject):
    """Class for checking for updates from GitHub"""
    
    # Signals
    update_available = Signal(str, str, str)  # current_version, new_version, release_notes
    check_complete = Signal(bool)  # updates_available
    
    def __init__(self, config=None):
        """Initialize the update checker
        
        Args:
            config: Config instance for accessing settings
        """
        super().__init__()
        self.config = config
        self.github_repo = "https://github.com/chibashr/netWORKS"
        self.github_api_url = "https://api.github.com/repos/chibashr/netWORKS"
        self.current_version = self._get_current_version()
        
        # Initialize update manager
        self.update_manager = UpdateManager(config)
        
        # Set custom repository URL if configured
        custom_repo = self.config.get("general.repository_url", "") if self.config else ""
        if custom_repo:
            self.set_repository_url(custom_repo)
            # Also update the update manager's repository URL
            self.update_manager.repository_url = custom_repo
        
    def _get_current_version(self):
        """Get the current version from the manifest file"""
        try:
            manifest_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "manifest.json")
            with open(manifest_path, 'r') as f:
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
        """Check for updates from GitHub
        
        Args:
            branch: Branch to check for updates (stable, beta, main)
                   If None, uses the configured branch
        
        Returns:
            tuple: (updates_available, current_version, new_version, release_notes)
        """
        if branch is None:
            branch = self.get_branch()
            
        logger.info(f"Checking for updates on branch: {branch}")
        
        # Ensure git repository is initialized if auto-initialization is enabled
        auto_init = self.config.get("update.auto_initialize_git", True) if self.config else True
        if auto_init and not self.update_manager.is_git_repository() and self.update_manager.is_git_installed():
            # Try to initialize in background (non-blocking)
            logger.info("Auto-initializing git repository for updates...")
            try:
                # This is a non-blocking check - actual initialization happens when user clicks update
                pass
            except Exception as e:
                logger.warning(f"Could not auto-initialize repository: {e}")
        
        try:
            # Get the manifest file from GitHub for the specified branch
            manifest_url = f"{self.github_repo}/raw/{branch}/manifest.json"
            logger.debug(f"Fetching manifest from: {manifest_url}")
            
            req = urllib.request.Request(
                manifest_url,
                headers={'User-Agent': f'NetWORKS/{self.current_version}'}
            )
            
            # Create SSL context with default verification
            ssl_context = ssl.create_default_context()
            
            with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
                if response.getcode() == 200:
                    data = response.read().decode('utf-8')
                    manifest = json.loads(data)
                    
                    remote_version = manifest.get("version_string", "0.0.0")
                    logger.debug(f"Remote version: {remote_version}, Current version: {self.current_version}")
                    
                    # Compare versions (simple string comparison for now)
                    updates_available = self._compare_versions(remote_version, self.current_version)
                    release_notes = manifest.get("release_notes", "No release notes available")
                    
                    # Emit signals
                    if updates_available:
                        self.update_available.emit(self.current_version, remote_version, release_notes)
                    
                    self.check_complete.emit(updates_available)
                    
                    return updates_available, self.current_version, remote_version, release_notes
        except urllib.error.URLError as e:
            # Handle SSL certificate errors specifically
            if isinstance(e.reason, ssl.SSLError):
                logger.warning(f"SSL certificate verification failed while checking for updates. This is usually a system configuration issue. Error: {e.reason}")
                logger.info("Update check skipped due to SSL certificate verification failure. This does not affect application functionality.")
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
        """Set a custom repository URL
        
        Args:
            url: Full repository URL (e.g., https://github.com/username/repo)
        """
        url = url.rstrip('/')  # Remove trailing slash if present
        
        # Check if URL is a GitHub URL
        if "github.com" in url:
            self.github_repo = url
            
            # Convert GitHub URL to API URL
            parts = url.split('github.com/')
            if len(parts) == 2:
                repo_path = parts[1]
                self.github_api_url = f"https://api.github.com/repos/{repo_path}"
                logger.debug(f"Set GitHub repo: {self.github_repo}, API: {self.github_api_url}")
        else:
            logger.warning(f"Unsupported repository URL format: {url}")
            
        return self 