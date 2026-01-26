#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Crash reporter for NetWORKS
"""

import os
import sys
import platform
import datetime
import traceback
import json
import threading
from pathlib import Path
from loguru import logger

from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QDialogButtonBox


def get_system_info():
    """Get system information for crash reports"""
    info = {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "qt_version": "unknown",
        "time": datetime.datetime.now().isoformat(),
    }
    
    # Try to get Qt version if QApplication exists
    try:
        app = QApplication.instance()
        if app:
            info["qt_version"] = app.applicationVersion()
        else:
            # Try to get Qt version from PySide6 module
            try:
                import PySide6
                info["qt_version"] = PySide6.__version__
            except:
                pass
    except:
        pass
    
    # Try to get app version from manifest
    try:
        manifest_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
                info["app_version"] = manifest.get("version", "unknown")
        else:
            info["app_version"] = "unknown"
    except Exception:
        info["app_version"] = "unknown"
        
    return info


def report_crash(title, exception, additional_info=None):
    """
    Create a crash report and display a dialog with the details
    
    Args:
        title: Title/description of the crash
        exception: The exception that caused the crash
        additional_info: Additional information to include in the report
    """
    # Get exception information
    exc_type, exc_value, exc_traceback = sys.exc_info() if exception is None else (type(exception), exception, exception.__traceback__)
    
    # Format the traceback
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    traceback_text = ''.join(tb_lines)
    
    # Get system information
    system_info = get_system_info()
    
    # Create report data
    report_data = {
        "title": title,
        "timestamp": datetime.datetime.now().isoformat(),
        "system_info": system_info,
        "exception_type": exc_type.__name__ if exc_type else "Unknown",
        "exception_value": str(exc_value),
        "traceback": traceback_text,
        "additional_info": additional_info or {}
    }
    
    # Ensure crash reports directory exists
    crash_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "crashes")
    os.makedirs(crash_dir, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"crash_{timestamp}.log"
    filepath = os.path.join(crash_dir, filename)
    
    # Write crash report to file
    try:
        with open(filepath, 'w') as f:
            f.write(f"=== NetWORKS Crash Report ===\n")
            f.write(f"Title: {title}\n")
            f.write(f"Time: {system_info['time']}\n")
            f.write(f"App Version: {system_info['app_version']}\n")
            f.write(f"\n=== System Information ===\n")
            for key, value in system_info.items():
                f.write(f"{key}: {value}\n")
            f.write(f"\n=== Exception Details ===\n")
            f.write(f"Type: {report_data['exception_type']}\n")
            f.write(f"Value: {report_data['exception_value']}\n")
            f.write(f"\n=== Traceback ===\n")
            f.write(traceback_text)
            if additional_info:
                f.write(f"\n=== Additional Information ===\n")
                for key, value in additional_info.items():
                    f.write(f"{key}: {value}\n")
    except Exception as e:
        logger.error(f"Failed to write crash report: {e}")
    
    # Log the crash
    logger.error(f"Crash report generated: {filepath}")
    logger.error(f"Exception: {exc_type.__name__}: {exc_value}")
    logger.error(f"Traceback: {traceback_text}")
    
    # Return the filepath to the crash report
    return filepath


def show_crash_dialog(title, exception, additional_info=None):
    """
    Show a dialog with crash information
    
    Args:
        title: Title/description of the crash
        exception: The exception that caused the crash
        additional_info: Additional information to include in the report
    """
    # Generate the crash report
    report_file = report_crash(title, exception, additional_info)
    
    # Ensure QApplication exists
    app = QApplication.instance()
    if app is None:
        import sys
        app = QApplication(sys.argv)
    
    # Create dialog
    dialog = QDialog()
    dialog.setWindowTitle("Application Error")
    dialog.setMinimumSize(600, 400)
    
    layout = QVBoxLayout(dialog)
    
    # Add error information
    error_label = QLabel(f"<h3>{title}</h3>")
    layout.addWidget(error_label)
    
    # Add exception details
    details_label = QLabel(f"<b>Error:</b> {type(exception).__name__}: {str(exception)}")
    layout.addWidget(details_label)
    
    # Add traceback in a text box
    traceback_label = QLabel("<b>Technical Details:</b>")
    layout.addWidget(traceback_label)
    
    traceback_text = QTextEdit()
    traceback_text.setReadOnly(True)
    traceback_text.setPlainText(''.join(traceback.format_exception(
        type(exception), exception, exception.__traceback__
    )))
    layout.addWidget(traceback_text)
    
    # Add report file location
    report_label = QLabel(f"<b>Crash report saved to:</b> {report_file}")
    layout.addWidget(report_label)
    
    # Add buttons
    buttons = QDialogButtonBox(QDialogButtonBox.Ok)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)
    
    dialog.exec()


def setup_global_exception_handler():
    """Set up global exception handler to catch unhandled exceptions"""
    original_excepthook = sys.excepthook
    
    def exception_handler(exc_type, exc_value, exc_traceback):
        """Global exception handler that generates crash reports"""
        # Log the exception
        logger.error("Unhandled exception:", exc_info=(exc_type, exc_value, exc_traceback))
        
        # Generate a crash report
        report_crash("Unhandled Exception", exc_value)
        
        # Call the original exception handler
        original_excepthook(exc_type, exc_value, exc_traceback)
    
    # Set the exception hook
    sys.excepthook = exception_handler
    
    # Handle exceptions in threads
    def thread_exception_handler(args):
        """Exception handler for threads"""
        # args contains:
        # type, value, traceback as a tuple
        # Thread that raised the exception
        # Thread context
        try:
            if len(args) >= 3:
                report_crash("Thread Exception", args[1])
        except Exception as e:
            logger.error(f"Error in thread exception handler: {e}")
    
    # Set thread exception handler
    threading.excepthook = thread_exception_handler 