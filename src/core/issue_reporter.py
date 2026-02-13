#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GitHub issue reporter for NetWORKS
"""

import os
import json
import urllib.request
import urllib.error
import urllib.parse
import base64
import platform
import time
import threading
from datetime import datetime
from pathlib import Path
from loguru import logger
from PySide6.QtCore import QObject, Signal

class IssueReporter(QObject):
    """Class for reporting issues to GitHub with offline queue support"""
    
    # Signals
    issue_submitted = Signal(bool, str)  # success, issue_url or error message
    queue_processed = Signal(int, int)   # successful, failed
    
    def __init__(self, config=None, app=None):
        """Initialize the issue reporter
        
        Args:
            config: Config instance for accessing settings
            app: Application instance
        """
        super().__init__()
        self.config = config
        self.app = app
        
        # GitHub repository information
        self.github_repo = "https://github.com/chibashr/NetWORKS"
        self.github_api_url = "https://api.github.com/repos/chibashr/NetWORKS/issues"
        
        # Set custom repository URL if configured
        if self.config:
            custom_repo = self.config.get("general.repository_url", "")
            if custom_repo:
                self.set_repository_url(custom_repo)
        
        # Offline queue settings
        self.queue_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "data", "issue_queue"
        )
        os.makedirs(self.queue_dir, exist_ok=True)
        
        # Load GitHub token if exists
        self.github_token = None
        if self.config:
            self.github_token = self.config.get("general.github_token", "")
        
        # Background thread for processing queue
        self.processing_thread = None
        self.is_processing = False
    
    def submit_issue(self, title, description, category, severity, steps_to_reproduce, 
                    expected_result, actual_result, screenshot_path=None, 
                    system_info=True, app_logs=True):
        """Submit an issue to GitHub
        
        Args:
            title: Issue title
            description: Issue description
            category: Bug, Feature Request, or Question
            severity: Critical, High, Medium, Low
            steps_to_reproduce: Steps to reproduce the issue
            expected_result: Expected result
            actual_result: Actual result
            screenshot_path: Path to screenshot file (optional)
            system_info: Whether to include system information
            app_logs: Whether to include application logs
            
        Returns:
            tuple: (success, message)
        """
        # Create issue body
        body = self._format_issue_body(
            description=description,
            category=category,
            severity=severity,
            steps_to_reproduce=steps_to_reproduce,
            expected_result=expected_result,
            actual_result=actual_result,
            system_info=system_info,
            app_logs=app_logs
        )
        
        # Prepare issue data
        issue_data = {
            "title": title,
            "body": body,
            "labels": [category, f"severity:{severity.lower()}"]
        }
        
        # Try to submit the issue online
        if self._is_online():
            try:
                response = self._submit_to_github(issue_data, screenshot_path)
                issue_url = response.get("html_url", "")
                if issue_url:
                    # Save successful submission to config if user is logged in
                    if self.github_token and self.config:
                        recent_issues = self.config.get("issue_reporter.recent_issues", [])
                        recent_issues.insert(0, {
                            "title": title,
                            "url": issue_url,
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "status": "open"
                        })
                        # Keep only the 10 most recent issues
                        if len(recent_issues) > 10:
                            recent_issues = recent_issues[:10]
                        self.config.set("issue_reporter.recent_issues", recent_issues)
                    
                    self.issue_submitted.emit(True, issue_url)
                    return True, issue_url
                else:
                    raise Exception("No issue URL in response")
            except Exception as e:
                logger.error(f"Error submitting issue online: {e}")
                
                # If we have a token but submission failed, queue it for later
                if self.github_token:
                    logger.info("Queueing issue for later submission")
                    self._queue_issue(title, issue_data, screenshot_path)
                    self.issue_submitted.emit(False, "Issue queued for later submission. Will be sent when online.")
                    return False, "Issue queued for later submission. Will be sent when online."
                else:
                    # Without a token, redirect to the GitHub new issue page
                    issue_url = f"{self.github_repo}/issues/new"
                    self.issue_submitted.emit(False, f"Please submit your issue directly: {issue_url}")
                    return False, f"Please submit your issue directly: {issue_url}"
        else:
            # Offline - queue for later
            logger.info("Offline - queueing issue for later submission")
            self._queue_issue(title, issue_data, screenshot_path)
            self.issue_submitted.emit(False, "You are offline. Issue queued for later submission.")
            return False, "You are offline. Issue queued for later submission."
    
    def process_queue(self, synchronous=False):
        """Process the offline queue
        
        Args:
            synchronous: Whether to process the queue synchronously
        """
        if self.is_processing:
            logger.debug("Queue processing already in progress")
            return
            
        if synchronous:
            self._process_queue_internal()
        else:
            # Start a background thread to process the queue
            self.processing_thread = threading.Thread(target=self._process_queue_internal)
            self.processing_thread.daemon = True
            self.processing_thread.start()
    
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
                self.github_api_url = f"https://api.github.com/repos/{repo_path}/issues"
                logger.debug(f"Set GitHub repo: {self.github_repo}, API: {self.github_api_url}")
        else:
            logger.warning(f"Unsupported repository URL format: {url}")
            
        return self
    
    def set_github_token(self, token):
        """Set GitHub personal access token
        
        Args:
            token: GitHub personal access token
        """
        self.github_token = token
        
        # Save to config if available
        if self.config:
            self.config.set("general.github_token", token)
            self.config.save()
        
        return self
    
    def get_queue_status(self):
        """Get the status of the offline queue
        
        Returns:
            tuple: (queue_size, is_processing)
        """
        queue_files = self._get_queue_files()
        return len(queue_files), self.is_processing
    
    def _submit_to_github(self, issue_data, screenshot_path=None):
        """Submit issue to GitHub via API
        
        Args:
            issue_data: Issue data dictionary
            screenshot_path: Path to screenshot file (optional)
            
        Returns:
            dict: Response from GitHub API
        """
        # If screenshot provided, upload it first and get URL
        if screenshot_path and os.path.exists(screenshot_path):
            try:
                image_url = self._upload_image(screenshot_path)
                if image_url:
                    # Add screenshot to issue body
                    issue_data["body"] += f"\n\n### Screenshot\n![Screenshot]({image_url})\n"
            except Exception as e:
                logger.error(f"Error uploading screenshot: {e}")
                # Continue without screenshot
        
        # Prepare request
        headers = {
            'User-Agent': f'NetWORKS/{self.app.get_version() if self.app else "1.0.0"}',
            'Content-Type': 'application/json'
        }
        
        # Add authorization if token is available
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
        
        # Create request
        data = json.dumps(issue_data).encode('utf-8')
        req = urllib.request.Request(
            self.github_api_url,
            data=data,
            headers=headers,
            method='POST'
        )
        
        # Send request
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.getcode() == 201:
                return json.loads(response.read().decode('utf-8'))
            else:
                raise Exception(f"Unexpected response code: {response.getcode()}")
    
    def _upload_image(self, image_path):
        """Upload an image to GitHub and return the URL
        
        Args:
            image_path: Path to image file
            
        Returns:
            str: URL to uploaded image
        """
        # This would need a GitHub token with appropriate permissions
        if not self.github_token:
            logger.warning("GitHub token required for image uploads")
            return None
            
        # Read image file and encode as base64
        with open(image_path, 'rb') as f:
            content = f.read()
            
        # Get file name and mime type
        file_name = os.path.basename(image_path)
        mime_type = "image/png" if file_name.lower().endswith('.png') else "image/jpeg"
        
        # Create data for GitHub API
        upload_data = {
            "message": f"Upload image for issue report",
            "content": base64.b64encode(content).decode('utf-8')
        }
        
        # Generate a unique path for the image
        timestamp = int(time.time())
        upload_path = f"issues/screenshots/{timestamp}_{file_name}"
        
        # Prepare API URL for uploading to content
        parts = self.github_api_url.split('/repos/')
        if len(parts) == 2:
            repo_path = parts[1].split('/issues')[0]
            upload_url = f"https://api.github.com/repos/{repo_path}/contents/{upload_path}"
            
            # Prepare request
            headers = {
                'User-Agent': f'NetWORKS/{self.app.get_version() if self.app else "1.0.0"}',
                'Content-Type': 'application/json',
                'Authorization': f'token {self.github_token}'
            }
            
            # Create request
            data = json.dumps(upload_data).encode('utf-8')
            req = urllib.request.Request(
                upload_url,
                data=data,
                headers=headers,
                method='PUT'
            )
            
            # Send request
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.getcode() == 201:
                    result = json.loads(response.read().decode('utf-8'))
                    return result.get("content", {}).get("download_url")
                else:
                    raise Exception(f"Unexpected response code: {response.getcode()}")
        
        return None
    
    def _queue_issue(self, title, issue_data, screenshot_path=None):
        """Queue an issue for later submission
        
        Args:
            title: Issue title
            issue_data: Issue data dictionary
            screenshot_path: Path to screenshot file (optional)
        """
        # Create a unique, filesystem-safe ID for the issue
        timestamp = int(time.time())
        # Restrict to characters that are safe on all supported filesystems
        safe_title = "".join(
            c if c.isalnum() or c in ("-", "_") else "_"
            for c in title.strip()
        ) or "issue"
        issue_id = f"{timestamp}_{safe_title[:30]}"
        
        # Create queue entry
        queue_entry = {
            "id": issue_id,
            "timestamp": timestamp,
            "issue_data": issue_data,
            "screenshot_path": screenshot_path if screenshot_path and os.path.exists(screenshot_path) else None,
            "attempts": 0,
            "last_attempt": None
        }
        
        # Save queue entry to file
        queue_file = os.path.join(self.queue_dir, f"{issue_id}.json")
        with open(queue_file, 'w') as f:
            json.dump(queue_entry, f, indent=2)
            
        logger.debug(f"Issue queued: {issue_id}")
        
        # If we have a screenshot, copy it to queue directory to ensure it's available later
        if screenshot_path and os.path.exists(screenshot_path):
            screenshot_ext = os.path.splitext(screenshot_path)[1]
            screenshot_copy = os.path.join(self.queue_dir, f"{issue_id}{screenshot_ext}")
            try:
                import shutil
                shutil.copy2(screenshot_path, screenshot_copy)
                
                # Update the queue entry with the new screenshot path
                queue_entry["screenshot_path"] = screenshot_copy
                with open(queue_file, 'w') as f:
                    json.dump(queue_entry, f, indent=2)
            except Exception as e:
                logger.error(f"Error copying screenshot: {e}")
    
    def _process_queue_internal(self):
        """Process the offline queue (internal implementation)"""
        if not self.github_token:
            logger.warning("GitHub token required for processing queue")
            return
            
        if not self._is_online():
            logger.warning("Cannot process queue while offline")
            return
            
        self.is_processing = True
        logger.info("Processing offline queue")
        
        queue_files = self._get_queue_files()
        if not queue_files:
            logger.info("No queued issues to process")
            self.is_processing = False
            self.queue_processed.emit(0, 0)
            return
            
        successful = 0
        failed = 0
        
        for queue_file in queue_files:
            try:
                with open(queue_file, 'r') as f:
                    queue_entry = json.load(f)
                    
                # Update attempt information
                queue_entry["attempts"] += 1
                queue_entry["last_attempt"] = int(time.time())
                
                # Get issue data
                issue_data = queue_entry["issue_data"]
                screenshot_path = queue_entry["screenshot_path"]
                
                # Try to submit to GitHub
                try:
                    response = self._submit_to_github(issue_data, screenshot_path)
                    issue_url = response.get("html_url", "")
                    if issue_url:
                        # Success! Remove from queue
                        os.remove(queue_file)
                        
                        # Remove screenshot copy if exists
                        if screenshot_path and os.path.exists(screenshot_path) and screenshot_path.startswith(self.queue_dir):
                            try:
                                os.remove(screenshot_path)
                            except Exception as e:
                                logger.error(f"Error removing screenshot: {e}")
                        
                        # Save to recent issues
                        if self.config:
                            recent_issues = self.config.get("issue_reporter.recent_issues", [])
                            recent_issues.insert(0, {
                                "title": issue_data["title"],
                                "url": issue_url,
                                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "status": "open"
                            })
                            # Keep only the 10 most recent issues
                            if len(recent_issues) > 10:
                                recent_issues = recent_issues[:10]
                            self.config.set("issue_reporter.recent_issues", recent_issues)
                        
                        successful += 1
                    else:
                        # No URL - consider it a failure
                        raise Exception("No issue URL in response")
                except Exception as e:
                    logger.error(f"Error submitting queued issue: {e}")
                    failed += 1
                    
                    # Save updated attempt information
                    with open(queue_file, 'w') as f:
                        json.dump(queue_entry, f, indent=2)
                    
                    # If too many attempts, move to a "failed" directory
                    if queue_entry["attempts"] >= 5:
                        failed_dir = os.path.join(self.queue_dir, "failed")
                        os.makedirs(failed_dir, exist_ok=True)
                        failed_file = os.path.join(failed_dir, os.path.basename(queue_file))
                        
                        try:
                            import shutil
                            shutil.move(queue_file, failed_file)
                        except Exception as e:
                            logger.error(f"Error moving failed issue: {e}")
            except Exception as e:
                logger.error(f"Error processing queue file {queue_file}: {e}")
                failed += 1
        
        self.is_processing = False
        self.queue_processed.emit(successful, failed)
        logger.info(f"Queue processing complete: {successful} successful, {failed} failed")
    
    def _get_queue_files(self):
        """Get list of queue files
        
        Returns:
            list: List of queue file paths
        """
        return [os.path.join(self.queue_dir, f) for f in os.listdir(self.queue_dir) 
                if f.endswith('.json') and os.path.isfile(os.path.join(self.queue_dir, f))]
    
    def _is_online(self):
        """Check if we're online
        
        Returns:
            bool: True if online, False if offline
        """
        try:
            # Try to connect to GitHub to check connectivity
            req = urllib.request.Request(
                "https://api.github.com",
                headers={'User-Agent': f'NetWORKS/{self.app.get_version() if self.app else "1.0.0"}'}
            )
            urllib.request.urlopen(req, timeout=2)
            return True
        except:
            return False
    
    def _format_issue_body(self, description, category, severity, steps_to_reproduce,
                          expected_result, actual_result, system_info=True, app_logs=True):
        """Format issue body for GitHub
        
        Args:
            description: Issue description
            category: Bug, Feature Request, or Question
            severity: Critical, High, Medium, Low
            steps_to_reproduce: Steps to reproduce the issue
            expected_result: Expected result
            actual_result: Actual result
            system_info: Whether to include system information
            app_logs: Whether to include application logs
            
        Returns:
            str: Formatted issue body
        """
        body = f"""
## Description
{description}

## Category
{category}

## Severity
{severity}

## Steps to Reproduce
{steps_to_reproduce}

## Expected Result
{expected_result}

## Actual Result
{actual_result}
"""
        
        # Add system information if requested
        if system_info:
            sys_info = self._get_system_info()
            body += f"\n## System Information\n{sys_info}\n"
            
        # Add application logs if requested and available
        if app_logs and self.app:
            logs = self._get_recent_logs()
            if logs:
                body += f"\n## Application Logs\n```\n{logs}\n```\n"
                
        return body
    
    def _get_system_info(self):
        """Get system information
        
        Returns:
            str: Formatted system information
        """
        app_version = self.app.get_version() if self.app else "Unknown"
        
        system_info = f"""
- Application Version: {app_version}
- OS: {platform.system()} {platform.version()}
- Python: {platform.python_version()}
- Qt: {self._get_qt_version()}
"""
        return system_info
    
    def _get_qt_version(self):
        """Get Qt version
        
        Returns:
            str: Qt version string
        """
        try:
            from PySide6 import __version__
            return __version__
        except:
            return "Unknown"
    
    def _get_recent_logs(self, lines=50):
        """Get recent application logs
        
        Args:
            lines: Number of log lines to include
            
        Returns:
            str: Recent log lines as text
        """
        try:
            log_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "logs", "latest.log"
            )
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    # Get the last 'lines' lines
                    log_lines = f.readlines()
                    if len(log_lines) > lines:
                        log_lines = log_lines[-lines:]
                    return "".join(log_lines)
            else:
                return "Log file not found"
        except Exception as e:
            return f"Error reading logs: {e}" 