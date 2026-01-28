#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Helper decorators for the Network Scanner plugin.
"""

import functools
from loguru import logger


def safe_action_wrapper(func):
    """Decorator to safely handle actions without crashing the application."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            logger.debug(f"Starting action: {func.__name__}")
            result = func(self, *args, **kwargs)
            logger.debug(f"Successfully completed action: {func.__name__}")
            return result
        except Exception as e:
            logger.error(f"Error in action {func.__name__}: {e}", exc_info=True)
            try:
                if hasattr(self, "log_message"):
                    self.log_message(f"Error performing action: {e}")
                if hasattr(self, "main_window") and self.main_window and hasattr(self.main_window, "statusBar"):
                    self.main_window.statusBar().showMessage(f"Error: {e}", 3000)
            except Exception as inner_e:
                logger.critical(f"Failed to handle error in UI: {inner_e}")
            return None
    return wrapper
