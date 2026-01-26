#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Update manager for NetWORKS - handles git-based automatic updates
"""

import os
import subprocess
import shutil
import json
import time
from loguru import logger
from PySide6.QtCore import QObject, Signal


class UpdateManager(QObject):
    """Manages automatic updates using git operations"""
    
    # Signals for progress reporting
    progress = Signal(str)  # Progress message
    status_changed = Signal(str)  # Status message
    error_occurred = Signal(str)  # Error message
    update_complete = Signal(bool, str)  # success, message
    
    def __init__(self, config=None):
        """Initialize the update manager
        
        Args:
            config: Config instance for accessing settings
        """
        super().__init__()
        self.config = config
        self.app_dir = self._get_app_directory()
        self.git_dir = os.path.join(self.app_dir, ".git")
        
        # Get repository URL from config or use default
        if config:
            custom_repo = config.get("update.git_remote_url", "")
            if custom_repo:
                self.repository_url = custom_repo
            else:
                # Try to get from general.repository_url
                custom_repo = config.get("general.repository_url", "")
                if custom_repo:
                    self.repository_url = custom_repo
                else:
                    self.repository_url = "https://github.com/chibashr/netWORKS"
        else:
            self.repository_url = "https://github.com/chibashr/netWORKS"
    
    def _get_app_directory(self):
        """Get the application root directory"""
        # Get the directory containing this file
        core_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up to src, then to root
        return os.path.dirname(os.path.dirname(core_dir))
    
    def _get_branch(self):
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
        return "stable"
    
    def is_git_installed(self):
        """Check if git is installed and available"""
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False
    
    def is_git_repository(self):
        """Check if the application directory is a git repository"""
        return os.path.exists(self.git_dir)
    
    def initialize_repository(self, branch=None):
        """Initialize git repository for extracted zip installations
        
        Args:
            branch: Branch to initialize (defaults to configured branch)
            
        Returns:
            tuple: (success: bool, message: str)
        """
        if branch is None:
            branch = self._get_branch()
        
        self.status_changed.emit("Checking git installation...")
        
        # Check if git is installed
        if not self.is_git_installed():
            error_msg = (
                "Git is not installed or not available in PATH.\n\n"
                "To enable automatic updates, please install Git:\n"
                "https://git-scm.com/downloads\n\n"
                "After installing Git, restart NetWORKS and try updating again."
            )
            self.error_occurred.emit(error_msg)
            return False, error_msg
        
        # Check if already a git repository
        if self.is_git_repository():
            logger.info("Already a git repository")
            self.status_changed.emit("Repository already initialized")
            return True, "Repository already initialized"
        
        self.status_changed.emit("Initializing git repository...")
        self.progress.emit("Setting up git repository for automatic updates...")
        
        try:
            # Initialize git repository
            result = subprocess.run(
                ["git", "init"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                error_msg = f"Failed to initialize git repository: {result.stderr}"
                logger.error(error_msg)
                self.error_occurred.emit(error_msg)
                return False, error_msg
            
            # Add remote origin
            self.progress.emit("Configuring remote repository...")
            result = subprocess.run(
                ["git", "remote", "add", "origin", self.repository_url],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                # Remote might already exist, try to set URL
                result = subprocess.run(
                    ["git", "remote", "set-url", "origin", self.repository_url],
                    cwd=self.app_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    error_msg = f"Failed to set remote URL: {result.stderr}"
                    logger.error(error_msg)
                    self.error_occurred.emit(error_msg)
                    return False, error_msg
            
            # Add all files to git
            self.progress.emit("Staging current files...")
            result = subprocess.run(
                ["git", "add", "."],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.warning(f"Git add had issues: {result.stderr}")
                # Continue anyway, might be empty repo
            
            # Create initial commit
            self.progress.emit("Creating initial commit...")
            result = subprocess.run(
                ["git", "commit", "-m", "Initial commit from extracted release"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Fetch from remote (shallow)
            self.progress.emit("Fetching from remote repository...")
            result = subprocess.run(
                ["git", "fetch", "origin", branch, "--depth=1"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                error_msg = f"Failed to fetch from remote: {result.stderr}"
                logger.error(error_msg)
                self.error_occurred.emit(error_msg)
                return False, error_msg
            
            # Set upstream branch
            self.progress.emit("Setting up branch tracking...")
            result = subprocess.run(
                ["git", "branch", "--set-upstream-to", f"origin/{branch}", branch],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # If branch doesn't exist locally, create it
            if result.returncode != 0:
                result = subprocess.run(
                    ["git", "checkout", "-b", branch, f"origin/{branch}"],
                    cwd=self.app_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    error_msg = f"Failed to checkout branch: {result.stderr}"
                    logger.error(error_msg)
                    self.error_occurred.emit(error_msg)
                    return False, error_msg
            
            logger.info("Git repository initialized successfully")
            self.status_changed.emit("Repository initialized successfully")
            return True, "Repository initialized successfully"
            
        except subprocess.TimeoutExpired:
            error_msg = "Git operation timed out. Please check your network connection."
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Error initializing repository: {str(e)}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False, error_msg
    
    def perform_update(self, branch=None):
        """Perform the update by pulling from git
        
        Args:
            branch: Branch to update from (defaults to configured branch)
            
        Returns:
            tuple: (success: bool, message: str)
        """
        if branch is None:
            branch = self._get_branch()
        
        # Check if git is installed
        if not self.is_git_installed():
            error_msg = "Git is not installed. Cannot perform automatic update."
            self.error_occurred.emit(error_msg)
            return False, error_msg
        
        # Check if it's a git repository, if not try to initialize
        if not self.is_git_repository():
            self.status_changed.emit("Initializing repository for automatic updates...")
            success, msg = self.initialize_repository(branch)
            if not success:
                return False, msg
        
        try:
            # Check for uncommitted changes
            self.status_changed.emit("Checking for local changes...")
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            has_changes = bool(result.stdout.strip())
            if has_changes:
                logger.warning("Uncommitted changes detected")
                # Stash changes to allow update
                self.progress.emit("Stashing local changes...")
                result = subprocess.run(
                    ["git", "stash", "push", "-m", "Auto-stash before update"],
                    cwd=self.app_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    logger.warning(f"Failed to stash changes: {result.stderr}")
            
            # Fetch latest changes
            self.status_changed.emit("Fetching latest changes...")
            self.progress.emit("Connecting to repository...")
            result = subprocess.run(
                ["git", "fetch", "origin", branch],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                error_msg = f"Failed to fetch updates: {result.stderr}"
                logger.error(error_msg)
                self.error_occurred.emit(error_msg)
                return False, error_msg
            
            # Check if there are updates
            self.progress.emit("Checking for updates...")
            result = subprocess.run(
                ["git", "rev-list", "--count", f"HEAD..origin/{branch}"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            commits_behind = int(result.stdout.strip()) if result.returncode == 0 else 0
            
            if commits_behind == 0:
                return True, "Already up to date"
            
            # Reset to remote branch (clean update)
            self.status_changed.emit("Applying updates...")
            self.progress.emit(f"Updating {commits_behind} commit(s)...")
            result = subprocess.run(
                ["git", "reset", "--hard", f"origin/{branch}"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                error_msg = f"Failed to apply updates: {result.stderr}"
                logger.error(error_msg)
                self.error_occurred.emit(error_msg)
                return False, error_msg
            
            # Verify update by checking manifest version
            self.progress.emit("Verifying update...")
            manifest_path = os.path.join(self.app_dir, "manifest.json")
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                        new_version = manifest.get("version_string", "unknown")
                        logger.info(f"Update successful, new version: {new_version}")
                except Exception as e:
                    logger.warning(f"Could not verify version: {e}")
            
            self.status_changed.emit("Update completed successfully")
            self.update_complete.emit(True, "Update completed successfully")
            return True, "Update completed successfully"
            
        except subprocess.TimeoutExpired:
            error_msg = "Update operation timed out. Please check your network connection."
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Error during update: {str(e)}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return False, error_msg
    
    def get_update_info(self, branch=None):
        """Get information about available updates
        
        Args:
            branch: Branch to check (defaults to configured branch)
            
        Returns:
            dict: Update information with 'behind', 'ahead', 'current_commit', 'remote_commit'
        """
        if branch is None:
            branch = self._get_branch()
        
        if not self.is_git_repository():
            return {"behind": 0, "ahead": 0, "current_commit": None, "remote_commit": None}
        
        try:
            # Fetch to get latest remote info
            subprocess.run(
                ["git", "fetch", "origin", branch],
                cwd=self.app_dir,
                capture_output=True,
                timeout=60
            )
            
            # Get current commit
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            current_commit = result.stdout.strip() if result.returncode == 0 else None
            
            # Get remote commit
            result = subprocess.run(
                ["git", "rev-parse", f"origin/{branch}"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            remote_commit = result.stdout.strip() if result.returncode == 0 else None
            
            # Count commits behind
            result = subprocess.run(
                ["git", "rev-list", "--count", f"HEAD..origin/{branch}"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            behind = int(result.stdout.strip()) if result.returncode == 0 else 0
            
            # Count commits ahead
            result = subprocess.run(
                ["git", "rev-list", "--count", f"origin/{branch}..HEAD"],
                cwd=self.app_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            ahead = int(result.stdout.strip()) if result.returncode == 0 else 0
            
            return {
                "behind": behind,
                "ahead": ahead,
                "current_commit": current_commit,
                "remote_commit": remote_commit
            }
        except Exception as e:
            logger.error(f"Error getting update info: {e}")
            return {"behind": 0, "ahead": 0, "current_commit": None, "remote_commit": None}
