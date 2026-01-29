#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Plugin manager for NetWORKS
"""

from .plugin_types import PluginInfo, PluginState

import sys
import os
import gc
import importlib.util
import importlib.machinery
import inspect
import json
import pkgutil
import shutil
import time
import typing
import warnings
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union, Set

from loguru import logger
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QToolBar, QMenu, QDockWidget, QWidget, QTabWidget, QMessageBox

from .plugin_interface import PluginInterface
from .plugin.plugin_registry import (
    build_registry_data,
    load_registry_from_file,
    save_registry_to_file,
)
from .plugin.plugin_discovery import run_discovery


class PluginManager(QObject):
    """
    Manages plugin discovery, loading, and lifecycle
    """
    
    plugin_loaded = Signal(object)
    plugin_unloaded = Signal(object)
    plugin_enabled = Signal(object)
    plugin_disabled = Signal(object)
    plugin_state_changed = Signal(object)  # New signal for any state change
    plugin_status_changed = Signal(object, object)  # New signal for plugin status changes
    
    def __init__(self, app):
        """Initialize the plugin manager"""
        super().__init__()
        logger.debug("Initializing plugin manager")
        
        self.app = app
        self.plugins = {}  # id -> PluginInfo
        
        # Set default plugin directories
        self.internal_plugins_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "plugins"))
        
        # For external plugins, first look for a local plugins folder relative to application
        app_dir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        local_plugins_dir = os.path.join(app_dir, "plugins")
        
        # Set external plugins directory - only use from config if explicitly set by user
        if hasattr(self.app, 'config'):
            # Get configured external plugins directory, with local_plugins_dir as default
            self.external_plugins_dir = self.app.config.get(
                "application.external_plugins_directory", 
                local_plugins_dir
            )
        else:
            self.external_plugins_dir = local_plugins_dir
        
        # Ensure external plugins directory exists
        os.makedirs(self.external_plugins_dir, exist_ok=True)
        
        # Plugin registry file
        self.registry_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config", "plugins.json"
        )
        
        # Registry caching to avoid excessive file operations
        self._registry_cache = None
        self._registry_dirty = False
        
        # Flag to prevent concurrent discovery
        self._discovering = False
        
        # Discover and register plugins
        self.discover_plugins()
        
    def _sync_registry(self):
        """Sync plugins to registry."""
        logger.debug("Syncing plugins to registry")
        self._registry_dirty = True
        registry_data = build_registry_data(self.plugins)
        self._registry_cache = registry_data
        save_registry_to_file(self.registry_file, registry_data)
        self._registry_dirty = False

    def _load_registry(self):
        """Load plugin registry. Uses in-memory cache when not dirty."""
        if self._registry_cache is not None and not self._registry_dirty:
            logger.debug("Using cached registry")
            return self._registry_cache
        self._registry_cache = load_registry_from_file(self.registry_file)
        self._registry_dirty = False
        return self._registry_cache

    def _save_registry(self):
        """Save plugin registry to disk if dirty."""
        if not self._registry_dirty:
            logger.debug("Registry not dirty, skipping save")
            return
        registry_data = build_registry_data(self.plugins)
        save_registry_to_file(self.registry_file, registry_data)
        self._registry_cache = registry_data.copy()
        self._registry_dirty = False

    def discover_plugins(self):
        """Discover plugins in the configured directories."""
        return run_discovery(self)

    def get_plugins(self):
        """Get all plugins"""
        return list(self.plugins.values())
        
    def get_plugin(self, plugin_id):
        """Get a plugin by ID"""
        return self.plugins.get(plugin_id)
        
    def _transition_plugin_state(self, plugin_id, target_state, operation_name):
        """
        Central method to handle plugin state transitions.
        
        Args:
            plugin_id: The ID of the plugin
            target_state: The PluginState to transition to
            operation_name: The name of the operation for logging
            
        Returns:
            tuple: (success, plugin_info)
        """
        logger.debug(f"Attempting to {operation_name} plugin: {plugin_id} to state {target_state}")
        
        plugin_info = self.get_plugin(plugin_id)
        
        if not plugin_info:
            logger.warning(f"Cannot {operation_name} plugin: Plugin not found with ID: {plugin_id}")
            return False, None
            
        # Track the state before we change it
        previous_state = plugin_info.state
        current_state = previous_state
        
        # Check if already in the target state
        if current_state == target_state:
            logger.debug(f"Plugin {plugin_id} already in state {target_state}, no action needed")
            return True, plugin_info
        
        # Validate the transition
        if not PluginState.validate_transition(current_state, target_state):
            logger.error(f"Invalid state transition for plugin {plugin_id}: {current_state} -> {target_state}")
            return False, plugin_info
            
        logger.info(f"{operation_name.capitalize()} plugin: {plugin_info} from {current_state} to {target_state}")
        
        # Apply the transition
        plugin_info.state = target_state
        
        # Mark registry as dirty to be saved later
        self._registry_dirty = True
        
        # Emit appropriate signals based on the transition
        if current_state != PluginState.LOADED and target_state == PluginState.LOADED:
            self.plugin_loaded.emit(plugin_info)
        elif current_state == PluginState.LOADED and target_state != PluginState.LOADED:
            self.plugin_unloaded.emit(plugin_info)
            
        if not current_state.is_enabled and target_state.is_enabled:
            self.plugin_enabled.emit(plugin_info)
        elif current_state.is_enabled and not target_state.is_enabled:
            self.plugin_disabled.emit(plugin_info)
            
        # Always emit the state changed signal
        self.plugin_state_changed.emit(plugin_info)
        
        # Sync with registry
        self._sync_registry()
        
        # Persist plugin state into the active workspace so that
        # enabled/disabled and loaded flags remain workspace-specific.
        # Skip during plugin restore so we never overwrite loaded_plugins with a partial list.
        try:
            dm = getattr(self.app, "device_manager", None)
            if dm is None or not getattr(dm, "current_workspace", None):
                pass
            elif getattr(dm, "_restoring_plugins", False):
                logger.debug("Skipping workspace save during plugin restore to avoid partial loaded_plugins")
            else:
                dm.save_workspace(dm.current_workspace)
        except Exception as e:
            logger.error(f"Failed to save workspace after plugin state change: {e}", exc_info=True)
        
        logger.info(f"Successfully transitioned plugin {plugin_id} from {previous_state} to {target_state}")
        return True, plugin_info
    
    def enable_plugin(self, plugin_id):
        """Enable a plugin by ID. Compatibility: equivalent to load_plugin (no separate enable step)."""
        return self.load_plugin(plugin_id) is not None

    def disable_plugin(self, plugin_id):
        """Disable a plugin by ID"""
        logger.info(f"Attempting to disable plugin: {plugin_id}")
        
        plugin_info = self.get_plugin(plugin_id)
        if not plugin_info:
            logger.warning(f"Cannot disable plugin: Plugin not found with ID: {plugin_id}")
            return False
            
        if not plugin_info.state.is_enabled:
            logger.debug(f"Plugin {plugin_id} already disabled, no action needed")
            return True
            
        # ALWAYS attempt to unload the plugin first if it has an instance, regardless of state
        if plugin_info.instance is not None:
            logger.info(f"Unloading plugin {plugin_id} as part of disabling it")
            unload_success = self.unload_plugin(plugin_id)
            if not unload_success:
                logger.error(f"Failed to unload plugin {plugin_id} while disabling it, will force instance to None")
                # Force instance to None even if unload failed
                try:
                    if hasattr(plugin_info.instance, 'cleanup') and callable(plugin_info.instance.cleanup):
                        try:
                            plugin_info.instance.cleanup()
                        except Exception as e:
                            logger.error(f"Error during forced cleanup: {e}")
                    
                    # Force clear the instance
                    plugin_info.instance = None
                    
                    # Force GC
                    import gc
                    gc.collect()
                except Exception as e:
                    logger.error(f"Error during forced instance clear: {e}")
                    plugin_info.instance = None  # Try one more time
        
        # Now set the state to DISABLED - this will also force instance to None again via state setter
        success, _ = self._transition_plugin_state(plugin_id, PluginState.DISABLED, "disable")
        
        if success:
            # Verify plugin is in disabled state
            if plugin_info.state != PluginState.DISABLED:
                logger.warning(f"Plugin state transition did not complete correctly: {plugin_info.state.name}")
                # Force the state directly
                plugin_info.state = PluginState.DISABLED
                self._registry_dirty = True
                self._sync_registry()
            
            # Verify instance is completely cleared
            if plugin_info.instance is not None:
                logger.warning(f"Plugin instance still exists after disabling - forcing clear")
                plugin_info.instance = None
                
                # Run GC one more time
                import gc
                gc.collect()
            
            logger.info(f"Successfully disabled plugin: {plugin_id}")
        else:
            logger.error(f"Failed to disable plugin: {plugin_id}")
        
        # Always sync the registry to make sure changes are saved
        self._registry_dirty = True
        self._sync_registry()
        
        return success
    
    def load_plugin(self, plugin_id):
        """Load a plugin by ID"""
        logger.info(f"Attempting to load plugin: {plugin_id}")
        
        plugin_info = self.get_plugin(plugin_id)
        if not plugin_info:
            error_msg = f"Plugin not found with ID: {plugin_id}"
            logger.warning(f"Cannot load plugin: {error_msg}")
            self._show_error_dialog(
                "Plugin Not Found",
                f"Cannot load plugin '{plugin_id}'.\n\nPlugin not found in the system.",
                f"Plugin ID: {plugin_id}"
            )
            return None
            
        # Skip if already loaded
        if plugin_info.state.is_loaded:
            logger.debug(f"Plugin {plugin_id} already loaded, skipping")
            return plugin_info.instance
            
        # Load from DISCOVERED, DISABLED, or ERROR (no separate enable step)
        # Check and install plugin requirements if needed
        if plugin_info.requirements["python"]:
            logger.info(f"Checking Python requirements for plugin {plugin_id}")
            self.plugin_status_changed.emit(plugin_info, f"Checking requirements...")
            
            # Check if requirements are installed
            all_installed, missing, requires_restart = self._check_plugin_requirements_installed(plugin_info)
            
            if not all_installed:
                logger.info(f"Installing missing Python requirements for plugin {plugin_id}: {missing}")
                self.plugin_status_changed.emit(plugin_info, f"Installing missing requirements...")
                
                # Install only missing requirements
                original_requirements = plugin_info.requirements["python"]
                plugin_info.requirements["python"] = missing
                
                if not self._install_plugin_requirements(plugin_info):
                    error_msg = f"Failed to install requirements for plugin {plugin_id}"
                    logger.error(error_msg)
                    plugin_info.requirements["python"] = original_requirements
                    plugin_info.state = PluginState.ERROR
                    plugin_info.error = "Failed to install required Python packages"
                    self._registry_dirty = True
                    self._sync_registry()
                    
                    # Show error dialog
                    self._show_error_dialog(
                        "Plugin Requirements Installation Failed",
                        f"Failed to install required Python packages for plugin '{plugin_info.name}'.\n\n"
                        f"Missing packages: {', '.join(missing)}\n\n"
                        f"Please check your internet connection and try again, or install the packages manually.",
                        f"Plugin: {plugin_id}\nMissing packages: {', '.join(missing)}"
                    )
                    return None
                
                # Restore original requirements list
                plugin_info.requirements["python"] = original_requirements
                
                # Check if restart is required
                if self._requires_restart_after_install(missing):
                    logger.info(f"Plugin {plugin_id} requires application restart after dependency installation")
                    
                    # Get current workspace name
                    workspace_name = "default"
                    if hasattr(self.app, 'device_manager') and self.app.device_manager.current_workspace:
                        workspace_name = self.app.device_manager.current_workspace
                    
                    # Save workspace state
                    if self._save_workspace_for_restart(workspace_name):
                        # Show message to user
                        from PySide6.QtWidgets import QMessageBox
                        msg = QMessageBox()
                        msg.setWindowTitle("Restart Required")
                        msg.setText("Application restart required")
                        msg.setInformativeText(
                            f"Plugin '{plugin_info.name}' requires dependencies that need a restart to take effect.\n\n"
                            f"Your workspace '{workspace_name}' will be automatically restored after restart."
                        )
                        msg.setStandardButtons(QMessageBox.Ok)
                        msg.exec()
                        
                        # Trigger restart
                        if hasattr(self.app, 'main_window') and self.app.main_window:
                            # Save workspace and close
                            self.app.device_manager.save_workspace(workspace_name)
                            self.app.main_window.close()
                        else:
                            # If main window not available, just exit
                            import sys
                            sys.exit(0)
                        
                        return None  # Plugin not loaded yet, will be after restart
                    else:
                        error_msg = "Failed to save workspace state for restart"
                        logger.error(error_msg)
                        plugin_info.state = PluginState.ERROR
                        plugin_info.error = error_msg
                        self._registry_dirty = True
                        self._sync_registry()
                        
                        # Show error dialog
                        self._show_error_dialog(
                            "Workspace Save Failed",
                            f"Failed to save workspace state before restart.\n\n"
                            f"Plugin '{plugin_info.name}' requires a restart, but the workspace could not be saved.\n\n"
                            f"Please save your workspace manually before restarting.",
                            f"Workspace: {workspace_name}\nPlugin: {plugin_id}"
                        )
                        return None
            
        # Check if the plugin's dependencies are satisfied
        if not self._check_plugin_dependencies(plugin_info):
            error_msg = f"Cannot load plugin {plugin_id}: Dependencies not satisfied"
            logger.warning(error_msg)
            self._show_error_dialog(
                "Plugin Dependencies Not Satisfied",
                f"Cannot load plugin '{plugin_info.name}'.\n\n"
                f"One or more required plugin dependencies are missing or not enabled.\n\n"
                f"Please check the plugin dependencies and ensure all required plugins are enabled.",
                f"Plugin: {plugin_id}\nDependencies: {plugin_info.dependencies}"
            )
            return None
            
        try:
            # Emit status signal that we're starting to load
            self.plugin_status_changed.emit(plugin_info, f"Loading plugin...")
            
            # Import the plugin entry point
            import importlib.util
            import sys
            import os
            
            # Prepare the path to the plugin's entry point
            plugin_file = os.path.join(plugin_info.path, plugin_info.entry_point)
            
            # Check if the file exists
            if not os.path.exists(plugin_file):
                error_msg = f"Entry point file not found: {plugin_file}"
                logger.error(f"Cannot load plugin: {error_msg}")
                self.plugin_status_changed.emit(plugin_info, f"Error: Entry point file not found")
                self._show_error_dialog(
                    "Plugin Entry Point Not Found",
                    f"Cannot load plugin '{plugin_info.name}'.\n\n"
                    f"The plugin entry point file could not be found.\n\n"
                    f"The plugin may be corrupted or incorrectly installed.",
                    f"Plugin: {plugin_id}\nExpected file: {plugin_file}"
                )
                return None
                
            # Add the plugin directory to sys.path if not already there
            if plugin_info.path not in sys.path:
                sys.path.insert(0, plugin_info.path)
                
            # Load the module
            self.plugin_status_changed.emit(plugin_info, f"Importing plugin module...")
            
            # First, try to find the module if it's already loaded
            module_name = os.path.splitext(plugin_info.entry_point)[0]
            spec = importlib.util.find_spec(module_name)
            
            if spec is None:
                # Module not found in sys.path, try to load from file
                spec = importlib.util.spec_from_file_location(module_name, plugin_file)
                
            if spec is None:
                error_msg = f"Failed to create module spec for {module_name}"
                logger.error(f"Cannot load plugin: {error_msg}")
                self.plugin_status_changed.emit(plugin_info, f"Error: Failed to create module spec")
                self._show_error_dialog(
                    "Plugin Module Load Failed",
                    f"Cannot load plugin '{plugin_info.name}'.\n\n"
                    f"Failed to create module specification for the plugin.\n\n"
                    f"The plugin file may be corrupted or have syntax errors.",
                    f"Plugin: {plugin_id}\nModule: {module_name}\nFile: {plugin_file}"
                )
                return None
                
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            
            # Execute the module
            spec.loader.exec_module(module)
            
            # Find the plugin class
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and attr.__module__ == module.__name__ and hasattr(attr, 'initialize'):
                    # Found a class with initialize method defined in this module
                    plugin_class = attr
                    break
                    
            if not plugin_class:
                error_msg = f"No plugin class found in {plugin_file}"
                logger.error(f"Cannot load plugin: {error_msg}")
                self.plugin_status_changed.emit(plugin_info, f"Error: No plugin class found")
                self._show_error_dialog(
                    "Plugin Class Not Found",
                    f"Cannot load plugin '{plugin_info.name}'.\n\n"
                    f"No valid plugin class was found in the plugin file.\n\n"
                    f"The plugin must contain a class that inherits from PluginInterface and has an 'initialize' method.",
                    f"Plugin: {plugin_id}\nFile: {plugin_file}\nEntry point: {plugin_info.entry_point}"
                )
                return None
                
            # Create an instance of the plugin
            self.plugin_status_changed.emit(plugin_info, f"Creating plugin instance...")
            instance = plugin_class()
            
            # Initialize the plugin
            self.plugin_status_changed.emit(plugin_info, f"Initializing plugin...")
            try:
                success = instance.initialize(self.app, plugin_info)
                if not success:
                    error_msg = f"Plugin {plugin_id} initialization returned False"
                    logger.error(error_msg)
                    self.plugin_status_changed.emit(plugin_info, f"Error: Plugin initialization failed")
                    self._show_error_dialog(
                        "Plugin Initialization Failed",
                        f"Plugin '{plugin_info.name}' failed to initialize.\n\n"
                        f"The plugin's initialize() method returned False, indicating initialization failure.\n\n"
                        f"Please check the plugin's requirements and configuration.",
                        f"Plugin: {plugin_id}"
                    )
                    return None
            except Exception as e:
                import traceback
                error_msg = f"Error during plugin initialization: {str(e)}"
                error_details = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
                logger.error(error_msg, exc_info=True)
                self.plugin_status_changed.emit(plugin_info, f"Error during initialization: {str(e)}")
                self._show_error_dialog(
                    "Plugin Initialization Error",
                    f"An error occurred while initializing plugin '{plugin_info.name}'.\n\n"
                    f"Error: {str(e)}\n\n"
                    f"Please check the plugin's code and requirements.",
                    f"Plugin: {plugin_id}\n\n{error_details}"
                )
                return None
                
            # Store the instance in the plugin info
            plugin_info.instance = instance
            
            # Verify plugin is actually working
            self.plugin_status_changed.emit(plugin_info, f"Verifying plugin...")
            is_working, error_msg = self._verify_plugin_working(plugin_info)
            
            if not is_working:
                error_msg_display = error_msg or "Plugin verification failed"
                logger.error(f"Plugin {plugin_id} verification failed: {error_msg_display}")
                plugin_info.instance = None
                plugin_info.state = PluginState.ERROR
                plugin_info.error = error_msg_display
                self._registry_dirty = True
                self._sync_registry()
                self.plugin_status_changed.emit(plugin_info, f"Error: {error_msg_display}")
                self._show_error_dialog(
                    "Plugin Verification Failed",
                    f"Plugin '{plugin_info.name}' failed verification after loading.\n\n"
                    f"{error_msg_display}\n\n"
                    f"The plugin may not be properly initialized or may have compatibility issues.",
                    f"Plugin: {plugin_id}\nError: {error_msg_display}"
                )
                return None
            
            # Update plugin state to LOADED
            self._set_plugin_state(plugin_info, PluginState.LOADED)
            
            # Emit plugin loaded signal
            self.plugin_loaded.emit(plugin_info)
            
            # Success status
            self.plugin_status_changed.emit(plugin_info, f"Plugin loaded and verified successfully")
            logger.info(f"Plugin loaded and verified successfully: {plugin_id}")
            
            # Persist to workspace immediately so a crash or sudden close keeps this plugin as loaded
            try:
                dm = getattr(self.app, "device_manager", None)
                if dm and getattr(dm, "current_workspace", None) and not getattr(dm, "_restoring_plugins", False):
                    dm.save_workspace(dm.current_workspace)
            except Exception as e:
                logger.error(f"Failed to save workspace after loading plugin: {e}", exc_info=True)
            
            return instance
            
        except Exception as e:
            import traceback
            error_msg = f"Error loading plugin {plugin_id}: {str(e)}"
            error_details = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            logger.error(error_msg, exc_info=True)
            self.plugin_status_changed.emit(plugin_info, f"Error: {str(e)}")
            self._show_error_dialog(
                "Plugin Load Error",
                f"An unexpected error occurred while loading plugin '{plugin_info.name}'.\n\n"
                f"Error: {str(e)}\n\n"
                f"Please check the plugin's code and file structure.",
                f"Plugin: {plugin_id}\n\n{error_details}"
            )
            return None
            
    def unload_plugin(self, plugin_id):
        """
        Unload a plugin from memory.
        
        Args:
            plugin_id: The ID of the plugin to unload
            
        Returns:
            bool: True if the plugin was successfully unloaded, False otherwise
        """
        if plugin_id not in self.plugins:
            logger.warning(f"Cannot unload plugin {plugin_id}: Plugin not loaded")
            return False
        
        plugin_info = self.plugins[plugin_id]
        logger.info(f"Unloading plugin: {plugin_info}")
        
        try:
            # Keep reference to instance for cleanup
            instance = plugin_info.instance
            
            # Remove UI components
            self._remove_plugin_ui_components(plugin_info)
            
            # Disconnect all signals
            self._disconnect_device_manager_signals(plugin_info)
            self._disconnect_plugin_signals(plugin_info)
            
            # Call cleanup if needed
            if instance and hasattr(instance, 'cleanup'):
                try:
                    instance.cleanup()
                except Exception as e:
                    logger.error(f"Error during plugin cleanup for {plugin_id}: {e}", exc_info=True)
            
            # Set state first to prevent any accidental reloading (unload -> DISCOVERED so can load again)
            original_state = plugin_info.state
            plugin_info.state = PluginState.DISCOVERED if original_state.is_enabled else PluginState.DISABLED
            
            # Force delete the instance
            if instance:
                # Clear any modules first to break circular references
                self._clear_plugin_from_cache(plugin_id)
                
                # Nullify all attributes that might contain references
                for attr_name in dir(instance):
                    if not attr_name.startswith('__'):
                        try:
                            setattr(instance, attr_name, None)
                        except (AttributeError, TypeError):
                            pass
                
                # Remove the instance reference from plugin_info
                plugin_info.instance = None
                
                # Break any potential circular references
                try:
                    instance.__dict__.clear()
                except:
                    pass
                
                # Force deletion attempt
                try:
                    del instance
                except:
                    pass
                
                # Force GC to run
                import gc
                gc.collect()
            
            # Triple check that instance is None
            if hasattr(plugin_info, 'instance') and plugin_info.instance is not None:
                logger.warning(f"Plugin instance reference still persists after unload for {plugin_id}, forcing to None")
                plugin_info.instance = None
                gc.collect()
            
            # Save changes to the registry
            self._sync_registry()
            
            logger.info(f"Successfully unloaded plugin: {plugin_id}")
            return True
        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_id}: {e}", exc_info=True)
            # Make sure the instance is still cleared even on error
            if hasattr(plugin_info, 'instance') and plugin_info.instance is not None:
                plugin_info.instance = None
                # Force GC
                import gc
                gc.collect()
            return False

    def _remove_plugin_ui_components(self, plugin_info):
        """Remove all UI components added by the plugin"""
        if not plugin_info.instance or not self.app.main_window:
            return
            
        instance = plugin_info.instance
        main_window = self.app.main_window
        
        logger.debug(f"Removing UI components for plugin: {plugin_info.id}")
        
        try:
            # Remove toolbar actions
            toolbar_actions = getattr(instance, 'get_toolbar_actions', lambda: [])()
            if toolbar_actions:
                logger.debug(f"Removing {len(toolbar_actions)} toolbar actions")
                # Find all toolbars in the main window
                toolbars = [tb for tb in main_window.findChildren(QToolBar)]
                for action in toolbar_actions:
                    try:
                        for toolbar in toolbars:
                            if action in toolbar.actions():
                                logger.debug(f"Removing action from toolbar: {toolbar.objectName()}")
                                toolbar.removeAction(action)
                        if hasattr(action, 'deleteLater'):
                            action.deleteLater()
                    except Exception as e:
                        logger.error(f"Error removing toolbar action: {e}")
                        
            # Remove menu actions
            menu_actions = getattr(instance, 'get_menu_actions', lambda: {})()
            if menu_actions:
                logger.debug(f"Removing menu actions from {len(menu_actions)} menus")
                for menu_name, actions in menu_actions.items():
                    try:
                        menu = main_window.findMenu(menu_name)
                        if menu:
                            logger.debug(f"Found menu {menu_name}, removing {len(actions)} actions")
                            for action in actions:
                                menu.removeAction(action)
                                if hasattr(action, 'deleteLater'):
                                    action.deleteLater()
                    except Exception as e:
                        logger.error(f"Error removing menu action from {menu_name}: {e}")
                        
            # Remove dock widgets
            dock_widgets = getattr(instance, 'get_dock_widgets', lambda: [])()
            if dock_widgets:
                logger.debug(f"Removing {len(dock_widgets)} dock widgets")
                # First try to find existing dock widgets with the same title
                all_dock_widgets = main_window.findChildren(QDockWidget)
                for dock_info in dock_widgets:
                    try:
                        dock_name, widget, area = dock_info
                        removed = False
                        
                        # Try to find by title first
                        for dock in all_dock_widgets:
                            if dock.windowTitle() == dock_name:
                                logger.debug(f"Found dock widget by title: {dock_name}")
                                main_window.removeDockWidget(dock)
                                dock.setWidget(None)  # Detach widget to prevent it from being deleted
                                dock.deleteLater()
                                removed = True
                                break
                                
                        # If not found by title, try by widget reference
                        if not removed:
                            for dock in all_dock_widgets:
                                if dock.widget() == widget:
                                    logger.debug(f"Found dock widget by widget reference")
                                    main_window.removeDockWidget(dock)
                                    dock.setWidget(None)
                                    dock.deleteLater()
                                    removed = True
                                    break
                                    
                        # If still not found, look for the exact dock passed
                        if not removed and isinstance(widget, QDockWidget):
                            logger.debug(f"Widget is a QDockWidget, removing directly")
                            main_window.removeDockWidget(widget)
                            widget.deleteLater()
                            removed = True
                            
                        # Clean up the widget if it wasn't part of a dock
                        if not removed and widget:
                            logger.debug(f"Dock not found by title or widget, cleaning up widget")
                            if widget.parent() == main_window:
                                widget.setParent(None)
                            widget.deleteLater()
                            
                    except Exception as e:
                        logger.error(f"Error removing dock widget: {e}", exc_info=True)
                        
            # Remove device panels
            device_panels = getattr(instance, 'get_device_panels', lambda: [])()
            if device_panels:
                logger.debug(f"Removing {len(device_panels)} device panels")
                if hasattr(main_window, 'device_details_panel'):
                    for panel_info in device_panels:
                        try:
                            panel_name, panel_widget = panel_info
                            logger.debug(f"Removing device panel: {panel_name}")
                            main_window.device_details_panel.remove_panel(panel_name)
                        except Exception as e:
                            logger.error(f"Error removing device panel: {e}")
                elif hasattr(main_window, 'properties_widget') and isinstance(main_window.properties_widget, QTabWidget):
                    # Fallback to looking for tabs in the properties widget
                    for panel_info in device_panels:
                        try:
                            panel_name, panel_widget = panel_info
                            logger.debug(f"Fallback: looking for tab with name {panel_name}")
                            
                            # Look for the tab by name
                            for i in range(main_window.properties_widget.count()):
                                if main_window.properties_widget.tabText(i) == panel_name:
                                    logger.debug(f"Found tab with name {panel_name}, removing")
                                    main_window.properties_widget.removeTab(i)
                                    if panel_widget.parent() == main_window.properties_widget:
                                        panel_widget.setParent(None)
                                    panel_widget.deleteLater()
                                    break
                        except Exception as e:
                            logger.error(f"Error removing tab from properties widget: {e}")
            
            # Remove custom device columns
            if hasattr(main_window, 'device_table_model'):
                columns = getattr(instance, 'get_device_table_columns', lambda: [])()
                if columns:
                    logger.debug(f"Removing {len(columns)} custom device columns")
                    for column_info in columns:
                        try:
                            column_name = column_info[0]
                            logger.debug(f"Removing device column: {column_name}")
                            main_window.device_table_model.remove_column(column_name)
                        except Exception as e:
                            logger.error(f"Error removing device column: {e}")
            
            logger.debug(f"Successfully removed UI components for plugin: {plugin_info.id}")
        except Exception as e:
            logger.error(f"Error while removing UI components for plugin {plugin_info.id}: {e}", exc_info=True)
            
    def _disconnect_device_manager_signals(self, plugin_info):
        """Disconnect all device manager signals for a plugin"""
        if not plugin_info.instance:
            return
        
        instance = plugin_info.instance
        logger.debug(f"Disconnecting device manager signals for plugin: {plugin_info.id}")
        
        try:
            # Check for connected signals attribute from plugin
            connected_signals = getattr(instance, '_connected_signals', set())
            
            # Only disconnect signals that were actually connected
            if connected_signals:
                logger.debug(f"Plugin has tracked connected signals: {connected_signals}")
                
                if "device_added" in connected_signals and hasattr(instance, 'on_device_added'):
                    try:
                        self.app.device_manager.device_added.disconnect(instance.on_device_added)
                        logger.debug(f"Successfully disconnected device_added signal for {plugin_info.id}")
                    except Exception as e:
                        logger.debug(f"Error disconnecting device_added signal: {e}")
                
                if "device_removed" in connected_signals and hasattr(instance, 'on_device_removed'):
                    try:
                        self.app.device_manager.device_removed.disconnect(instance.on_device_removed)
                        logger.debug(f"Successfully disconnected device_removed signal for {plugin_info.id}")
                    except Exception as e:
                        logger.debug(f"Error disconnecting device_removed signal: {e}")
                
                if "device_changed" in connected_signals and hasattr(instance, 'on_device_changed'):
                    try:
                        self.app.device_manager.device_changed.disconnect(instance.on_device_changed)
                        logger.debug(f"Successfully disconnected device_changed signal for {plugin_info.id}")
                    except Exception as e:
                        logger.debug(f"Error disconnecting device_changed signal: {e}")
                
                if "group_added" in connected_signals and hasattr(instance, 'on_group_added'):
                    try:
                        self.app.device_manager.group_added.disconnect(instance.on_group_added)
                        logger.debug(f"Successfully disconnected group_added signal for {plugin_info.id}")
                    except Exception as e:
                        logger.debug(f"Error disconnecting group_added signal: {e}")
                
                if "group_removed" in connected_signals and hasattr(instance, 'on_group_removed'):
                    try:
                        self.app.device_manager.group_removed.disconnect(instance.on_group_removed)
                        logger.debug(f"Successfully disconnected group_removed signal for {plugin_info.id}")
                    except Exception as e:
                        logger.debug(f"Error disconnecting group_removed signal: {e}")
                
                if "selection_changed" in connected_signals and hasattr(instance, 'on_device_selected'):
                    try:
                        self.app.device_manager.selection_changed.disconnect(instance.on_device_selected)
                        logger.debug(f"Successfully disconnected selection_changed signal for {plugin_info.id}")
                    except Exception as e:
                        logger.debug(f"Error disconnecting selection_changed signal: {e}")
            else:
                # Fall back to the old method of trying to disconnect all potential signals
                logger.debug(f"No tracked signals found for {plugin_info.id}, using fallback disconnection")
                
                # Helper function to safely disconnect a signal
                def safe_disconnect(signal, slot, signal_name):
                    """Safely disconnect a signal from a slot, suppressing warnings"""
                    if signal is None or slot is None:
                        return False
                    try:
                        # Check if signal has any receivers before attempting disconnect
                        # receivers() returns the number of connected receivers
                        if hasattr(signal, 'receivers') and signal.receivers(slot) > 0:
                            with warnings.catch_warnings():
                                warnings.simplefilter("ignore", RuntimeWarning)
                                signal.disconnect(slot)
                            logger.debug(f"Successfully disconnected {signal_name} signal for {plugin_info.id}")
                            return True
                        else:
                            logger.debug(f"Signal {signal_name} not connected to {plugin_info.id}")
                            return False
                    except (RuntimeError, TypeError) as e:
                        # Signal or slot may be invalid/deleted, ignore
                        logger.debug(f"Signal {signal_name} disconnection skipped: {e}")
                        return False
                    except Exception as e:
                        logger.debug(f"Signal {signal_name} disconnection error: {e}")
                        return False
                
                if hasattr(self.app.device_manager, 'device_added') and hasattr(instance, 'on_device_added'):
                    safe_disconnect(self.app.device_manager.device_added, instance.on_device_added, "device_added")
                
                if hasattr(self.app.device_manager, 'device_removed') and hasattr(instance, 'on_device_removed'):
                    safe_disconnect(self.app.device_manager.device_removed, instance.on_device_removed, "device_removed")
                
                if hasattr(self.app.device_manager, 'device_changed') and hasattr(instance, 'on_device_changed'):
                    safe_disconnect(self.app.device_manager.device_changed, instance.on_device_changed, "device_changed")
                
                if hasattr(self.app.device_manager, 'group_added') and hasattr(instance, 'on_group_added'):
                    safe_disconnect(self.app.device_manager.group_added, instance.on_group_added, "group_added")
                
                if hasattr(self.app.device_manager, 'group_removed') and hasattr(instance, 'on_group_removed'):
                    safe_disconnect(self.app.device_manager.group_removed, instance.on_group_removed, "group_removed")
                
                if hasattr(self.app.device_manager, 'selection_changed') and hasattr(instance, 'on_device_selected'):
                    safe_disconnect(self.app.device_manager.selection_changed, instance.on_device_selected, "selection_changed")
                
            logger.debug(f"Successfully disconnected device manager signals for plugin: {plugin_info.id}")
        except Exception as e:
            logger.error(f"Error disconnecting device manager signals for plugin {plugin_info.id}: {e}", exc_info=True)

    def _disconnect_plugin_signals(self, plugin_info):
        """Disconnect all plugin-specific signals"""
        if not plugin_info.instance:
            return
        
        instance = plugin_info.instance
        logger.debug(f"Disconnecting plugin signals for: {plugin_info.id}")
        
        try:
            # Check for connected signals attribute from plugin
            connected_signals = getattr(instance, '_connected_signals', None)
            if connected_signals:
                logger.debug(f"Found tracked signals in plugin: {connected_signals}")
                
            # List of signals to disconnect from the plugin instance
            signal_names = [
                'plugin_initialized', 'plugin_starting', 'plugin_running',
                'plugin_stopping', 'plugin_cleaned_up', 'plugin_error'
            ]
            
            for signal_name in signal_names:
                if hasattr(instance, signal_name):
                    signal = getattr(instance, signal_name)
                    # Only attempt disconnect if it's actually a Signal object
                    if hasattr(signal, 'disconnect'):
                        try:
                            # Check if the signal has any receivers before attempting disconnect
                            # receivers() without arguments returns total number of connections
                            if hasattr(signal, 'receivers'):
                                receiver_count = signal.receivers()
                                if receiver_count > 0:
                                    logger.debug(f"Attempting safe disconnect of {signal_name} ({receiver_count} receivers)")
                                    with warnings.catch_warnings():
                                        warnings.simplefilter("ignore", RuntimeWarning)
                                        signal.disconnect()
                                    logger.debug(f"Successfully disconnected signal {signal_name}")
                                else:
                                    logger.debug(f"Signal {signal_name} has no receivers, skipping disconnect")
                            else:
                                # Fallback: try to disconnect and catch exceptions
                                logger.debug(f"Attempting disconnect of {signal_name} (no receivers() method)")
                                with warnings.catch_warnings():
                                    warnings.simplefilter("ignore", RuntimeWarning)
                                    signal.disconnect()
                                logger.debug(f"Successfully disconnected signal {signal_name}")
                        except (RuntimeError, TypeError) as e:
                            # Signal may be invalid/deleted, ignore
                            logger.debug(f"Signal {signal_name} disconnection skipped: {e}")
                        except Exception as e:
                            # Downgrade to debug level since this is not a critical error
                            logger.debug(f"Signal {signal_name} disconnection error: {e}")
                    else:
                        logger.debug(f"Attribute {signal_name} is not a disconnectable signal")
                    
            logger.debug(f"Successfully disconnected plugin signals for: {plugin_info.id}")
        except Exception as e:
            logger.error(f"Error disconnecting plugin signals for {plugin_info.id}: {e}", exc_info=True)

    def _is_plugin_compatible(self, plugin_info):
        """Check if plugin is compatible with current app version"""
        current_version = self.app.get_version()
        
        # Check minimum version requirement
        min_version = getattr(plugin_info, "min_app_version", None)
        if min_version and self._compare_versions(current_version, min_version) < 0:
            logger.warning(f"Plugin {plugin_info.id} requires minimum app version {min_version}, but current is {current_version}")
            return False
            
        # Check maximum version constraint
        max_version = getattr(plugin_info, "max_app_version", None)
        if max_version and self._compare_versions(current_version, max_version) > 0:
            logger.warning(f"Plugin {plugin_info.id} requires maximum app version {max_version}, but current is {current_version}")
            return False
            
        return True

    def _compare_versions(self, version1, version2):
        """Compare two version strings, returns -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2"""
        def parse_version(v):
            return tuple(map(int, v.split('.')))
            
        v1_parts = parse_version(version1)
        v2_parts = parse_version(version2)
        
        # Compare each part of the version
        for i in range(max(len(v1_parts), len(v2_parts))):
            v1 = v1_parts[i] if i < len(v1_parts) else 0
            v2 = v2_parts[i] if i < len(v2_parts) else 0
            
            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1
                
        return 0  # Versions are equal 

    def _check_plugin_dependencies(self, plugin_info):
        """Check if plugin dependencies are satisfied"""
        if not plugin_info.dependencies:
            return True
            
        # Emit status signal
        self.plugin_status_changed.emit(plugin_info, f"Checking dependencies...")
            
        for dependency in plugin_info.dependencies:
            dep_id = dependency["id"]
            dep_version_req = dependency.get("version", "")
            
            # Check if the dependency plugin is installed
            if dep_id not in self.plugins:
                error_msg = f"Dependency plugin '{dep_id}' not found"
                logger.error(f"Cannot load plugin {plugin_info.id}: {error_msg}")
                self.plugin_status_changed.emit(plugin_info, f"Error: {error_msg}")
                return False
                
            # Check if the dependency plugin is enabled
            dep_plugin = self.plugins[dep_id]
            if not dep_plugin.state.is_enabled:
                error_msg = f"Dependency plugin '{dep_id}' is not enabled"
                logger.error(f"Cannot load plugin {plugin_info.id}: {error_msg}")
                self.plugin_status_changed.emit(plugin_info, f"Error: {error_msg}")
                return False
                
            # If version requirement specified, check version compatibility
            if dep_version_req:
                # Basic version check (can be expanded for more complex requirements)
                if dep_version_req.startswith(">="):
                    min_version = dep_version_req[2:]
                    if dep_plugin.version < min_version:
                        error_msg = f"Dependency '{dep_id}' version too low. Required: {dep_version_req}, Found: {dep_plugin.version}"
                        logger.error(f"Cannot load plugin {plugin_info.id}: {error_msg}")
                        self.plugin_status_changed.emit(plugin_info, f"Error: {error_msg}")
                        return False
                # Add other version check types as needed
                
        # All dependencies satisfied
        self.plugin_status_changed.emit(plugin_info, f"All dependencies satisfied")
        return True
        
    def reload_plugin(self, plugin_id):
        """Reload a plugin by ID"""
        logger.info(f"Attempting to reload plugin: {plugin_id}")
        
        plugin_info = self.get_plugin(plugin_id)
        if not plugin_info:
            logger.warning(f"Cannot reload plugin: Plugin not found with ID: {plugin_id}")
            return None
            
        # Remember if the plugin was enabled
        was_enabled = plugin_info.state.is_enabled
        was_loaded = plugin_info.state.is_loaded
        
        # First unload the plugin
        if was_loaded:
            logger.debug(f"Unloading plugin {plugin_id} before reload")
            success = self.unload_plugin(plugin_id)
            if not success:
                logger.error(f"Failed to unload plugin {plugin_id} for reload")
                return None
        
        # If the plugin wasn't enabled, nothing more to do
        if not was_enabled:
            logger.warning(f"Plugin {plugin_id} is disabled, skipping reload")
            return None
        
        # Reload the plugin
        logger.debug(f"Loading plugin {plugin_id} to complete reload")
        instance = self.load_plugin(plugin_id)
        
        # Verify reload was successful
        if instance:
            logger.info(f"Successfully reloaded plugin: {plugin_id}")
        else:
            logger.error(f"Failed to reload plugin: {plugin_id}")
            
            # If the plugin was enabled but failed to load, make sure it stays in ERROR state
            if was_enabled and plugin_info.state != PluginState.ERROR:
                plugin_info.state = PluginState.ERROR
                self._registry_dirty = True
                self._sync_registry()
        
        return instance
        
    def load_all_plugins(self):
        """Load all enabled plugins"""
        logger.info("Loading all enabled plugins")
        
        # Auto-enable newly discovered plugins if configured to do so
        if hasattr(self.app, 'config') and self.app.config.get("application.auto_enable_discovered_plugins", True):
            discovered_plugins = [p for p in self.plugins.values() if p.state == PluginState.DISCOVERED]
            if discovered_plugins:
                logger.info(f"Auto-enabling {len(discovered_plugins)} newly discovered plugins")
                for plugin_info in discovered_plugins:
                    logger.info(f"Auto-enabling plugin: {plugin_info.id}")
                    self.enable_plugin(plugin_info.id)
        
        # Get all plugins that can be loaded (DISCOVERED, not DISABLED)
        plugins_to_load = [p for p in self.plugins.values() if not p.state.is_loaded and p.state != PluginState.DISABLED]
        total_to_load = len(plugins_to_load)
        logger.debug(f"Found {total_to_load} plugins to load")
        
        # Track plugins that were already loaded
        already_loaded = [p.id for p in self.plugins.values() if p.state.is_loaded]
        logger.debug(f"Found {len(already_loaded)} plugins already loaded")
        
        # First, create a dependency graph
        dependencies = {}
        
        try:
            # Build dependency graph - handle varying formats of dependencies
            for plugin_info in plugins_to_load:
                plugin_deps = []
                
                # Handle possible different dependency formats
                if hasattr(plugin_info, 'dependencies'):
                    if isinstance(plugin_info.dependencies, list):
                        # Handle case where dependencies is a list of plugin IDs
                        plugin_deps = plugin_info.dependencies
                    elif isinstance(plugin_info.dependencies, dict) and "plugins" in plugin_info.dependencies:
                        # Handle case where dependencies is a dict with a "plugins" key
                        if isinstance(plugin_info.dependencies["plugins"], list):
                            plugin_deps = plugin_info.dependencies["plugins"]
                        else:
                            logger.warning(f"Unexpected format for plugin dependencies in {plugin_info.id}: {plugin_info.dependencies}")
                
                dependencies[plugin_info.id] = plugin_deps
                logger.debug(f"Plugin {plugin_info.id} dependencies: {plugin_deps}")
                
            # Sort plugins by dependency order using topological sort
            sorted_plugins = self._topological_sort(dependencies)
            
            # Filter to only include plugins to load
            sorted_plugins = [p for p in sorted_plugins if p in [plugin.id for plugin in plugins_to_load]]
            
            logger.debug(f"Ordered plugins to load: {', '.join(sorted_plugins)}")
        except Exception as e:
            logger.error(f"Error determining plugin load order: {e}", exc_info=True)
            # Fall back to loading in arbitrary order if we couldn't sort dependencies
            sorted_plugins = [p.id for p in plugins_to_load]
            logger.warning(f"Falling back to unsorted plugin loading: {', '.join(sorted_plugins)}")
        
        loaded_plugins = []
        load_failed = []
        
        # Load each plugin in dependency order
        for plugin_id in sorted_plugins:
            try:
                logger.debug(f"Loading plugin: {plugin_id}")
                instance = self.load_plugin(plugin_id)
                
                if instance:
                    loaded_plugins.append(self.plugins[plugin_id])
                    logger.debug(f"Successfully loaded plugin: {plugin_id}")
                else:
                    load_failed.append(plugin_id)
                    logger.error(f"Failed to load plugin: {plugin_id}")
            except Exception as e:
                load_failed.append(plugin_id)
                logger.error(f"Exception loading plugin {plugin_id}: {e}", exc_info=True)
                # Set plugin to ERROR state
                if plugin_id in self.plugins:
                    self.plugins[plugin_id].state = PluginState.ERROR
                    self.plugins[plugin_id].error = str(e)
                    self._registry_dirty = True
        
        # Save the registry after all operations
        self._sync_registry()
        
        # Log results
        if loaded_plugins:
            logger.info(f"Successfully loaded {len(loaded_plugins)} plugins: {', '.join([p.id for p in loaded_plugins])}")
        
        if load_failed:
            logger.warning(f"Failed to load {len(load_failed)} plugins: {', '.join(load_failed)}")
            
            # Show error dialog if some plugins failed to load
            if len(load_failed) > 0:
                failed_plugin_names = [self.plugins[p].name if p in self.plugins else p for p in load_failed]
                self._show_error_dialog(
                    "Some Plugins Failed to Load",
                    f"Failed to load {len(load_failed)} plugin(s).\n\n"
                    f"Failed plugins: {', '.join(failed_plugin_names)}\n\n"
                    f"Please check the plugin manager for details on each plugin's error.",
                    f"Failed plugin IDs: {', '.join(load_failed)}"
                )
            
        return loaded_plugins

    def _topological_sort(self, dependencies):
        """
        Perform a topological sort of plugins based on dependencies
        
        Args:
            dependencies: Dictionary mapping plugin_id to list of dependency plugin ids
            
        Returns:
            List of plugin ids in dependency order (dependencies first)
        """
        # Create a dictionary to track visited nodes
        visited = {node: False for node in dependencies}
        temp_visited = {node: False for node in dependencies}  # For cycle detection
        # Create a list for the sorted elements
        sorted_list = []
        
        # Define the recursive dfs function
        def dfs(node):
            # If node is already in sorted list, we can skip
            if node in sorted_list:
                return True
                
            # If the node is temporarily visited, we have a cycle
            if temp_visited.get(node, False):
                logger.warning(f"Dependency cycle detected involving plugin: {node}")
                return False
                
            # Mark node as temporarily visited for cycle detection
            temp_visited[node] = True
            
            # Visit all dependencies if they exist
            if node in dependencies:
                for dependency in dependencies[node]:
                    # Skip if dependency doesn't exist in our plugin system
                    if dependency not in visited:
                        logger.warning(f"Plugin {node} has missing dependency: {dependency}")
                        continue
                    
                    # If dependency not yet visited, visit it
                    if not visited.get(dependency, False):
                        success = dfs(dependency)
                        if not success:
                            # We detected a cycle, abort
                            return False
            
            # Mark node as permanently visited
            visited[node] = True
            # Clear temporary visit marker
            temp_visited[node] = False
            
            # After visiting all dependencies, add this node
            sorted_list.append(node)
            return True
        
        # Visit all nodes
        for node in list(dependencies.keys()):
            if not visited.get(node, False):
                dfs(node)
                
        # Return the sorted list (dependencies first)
        return sorted_list

    def unload_all_plugins(self):
        """Unload all loaded plugins"""
        logger.info("Unloading all loaded plugins")
        
        # Get all loaded plugins
        loaded_plugins = [p for p in self.plugins.values() if p.state.is_loaded]
        logger.debug(f"Found {len(loaded_plugins)} loaded plugins to unload")
        
        unloaded_plugins = []
        unload_failed = []
        
        # Unload in reverse order of loading (in case of dependencies)
        for plugin_info in reversed(loaded_plugins):
            logger.debug(f"Unloading plugin: {plugin_info.id}")
            success = self.unload_plugin(plugin_info.id)
            
            if success:
                unloaded_plugins.append(plugin_info)
                logger.debug(f"Successfully unloaded plugin: {plugin_info.id}")
            else:
                unload_failed.append(plugin_info.id)
                logger.error(f"Failed to unload plugin: {plugin_info.id}")
        
        # Log results
        if unloaded_plugins:
            logger.info(f"Successfully unloaded {len(unloaded_plugins)} plugins: {', '.join([p.id for p in unloaded_plugins])}")
        
        if unload_failed:
            logger.warning(f"Failed to unload {len(unload_failed)} plugins: {', '.join(unload_failed)}")
            
        # Final check to ensure all plugins are properly unloaded
        still_loaded = [p.id for p in self.plugins.values() if p.state.is_loaded]
        if still_loaded:
            logger.error(f"Some plugins are still in LOADED state after unload_all_plugins: {', '.join(still_loaded)}")
            
        logger.info(f"Unloaded {len(unloaded_plugins)} plugins")
        return unloaded_plugins

    def _clear_plugin_from_cache(self, plugin_id):
        """
        Clear a plugin and all its related modules from the Python module cache.
        This helps ensure a clean reload next time.
        
        Args:
            plugin_id: The plugin ID to clear from cache
        """
        # Find all modules that belong to this plugin
        modules_to_remove = [
            mod_name for mod_name in list(sys.modules.keys())
            if mod_name.startswith(plugin_id) or  # Direct module match
               (mod_name.startswith('plugins.') and plugin_id in mod_name)  # Plugin in plugins directory
        ]
        
        # Log what we're removing
        if modules_to_remove:
            logger.debug(f"Clearing {len(modules_to_remove)} modules from cache for plugin {plugin_id}: {modules_to_remove}")
            
            # Actually remove the modules
            for mod_name in modules_to_remove:
                try:
                    if mod_name in sys.modules:
                        del sys.modules[mod_name]
                except Exception as e:
                    logger.error(f"Error removing module {mod_name} from cache: {e}")
        else:
            logger.debug(f"No modules found to clear for plugin {plugin_id}")
        
        # Check both plugin directories
        for plugin_dir_attr in ['external_plugins_dir', 'internal_plugins_dir']:
            if hasattr(self, plugin_dir_attr):
                plugin_dir = os.path.join(getattr(self, plugin_dir_attr), plugin_id)
                if os.path.isdir(plugin_dir):
                    pycache_dir = os.path.join(plugin_dir, "__pycache__")
                    if os.path.isdir(pycache_dir):
                        try:
                            logger.debug(f"Clearing __pycache__ directory for plugin {plugin_id} in {plugin_dir_attr}")
                            for cached_file in os.listdir(pycache_dir):
                                try:
                                    os.remove(os.path.join(pycache_dir, cached_file))
                                except Exception as e:
                                    logger.debug(f"Could not remove cached file {cached_file}: {e}")
                        except Exception as e:
                            logger.error(f"Error clearing __pycache__ for plugin {plugin_id}: {e}") 

    def _check_system_requirements(self, plugin_info):
        """
        Check if plugin system requirements are available
        
        Args:
            plugin_info: The PluginInfo object
            
        Returns:
            tuple: (all_available: bool, missing: list, messages: dict)
        """
        if not plugin_info.requirements.get("system", []):
            return True, [], {}
        
        missing = []
        messages = {}
        import subprocess
        import platform
        
        for req in plugin_info.requirements["system"]:
            req_lower = req.lower()
            
            # Check for nmap
            if "nmap" in req_lower:
                try:
                    # Try to find nmap in PATH
                    result = subprocess.run(
                        ["nmap", "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        logger.debug(f"System requirement {req} (nmap) is available")
                        continue
                except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
                    logger.debug(f"nmap not found or error checking: {e}")
                
                missing.append(req)
                # Provide platform-specific installation instructions
                system = platform.system()
                if system == "Windows":
                    messages[req] = (
                        "Nmap executable not found in PATH.\n\n"
                        "To install:\n"
                        "1. Download from https://nmap.org/download.html\n"
                        "2. Run the installer\n"
                        "3. Make sure nmap is added to your system PATH\n"
                        "4. Restart NetWORKS"
                    )
                elif system == "Darwin":  # macOS
                    messages[req] = (
                        "Nmap executable not found in PATH.\n\n"
                        "To install:\n"
                        "1. Run: brew install nmap\n"
                        "2. Restart NetWORKS"
                    )
                else:  # Linux
                    messages[req] = (
                        "Nmap executable not found in PATH.\n\n"
                        "To install:\n"
                        "1. Run: sudo apt install nmap (or equivalent for your distribution)\n"
                        "2. Restart NetWORKS"
                    )
            
            # Add checks for other system requirements here as needed
            # For now, we'll just log that we don't know how to check it
            else:
                logger.debug(f"System requirement {req} check not implemented, assuming available")
        
        all_available = len(missing) == 0
        return all_available, missing, messages
    
    def _check_plugin_requirements_installed(self, plugin_info):
        """
        Check if plugin Python requirements are already installed
        
        Args:
            plugin_info: The PluginInfo object
            
        Returns:
            tuple: (all_installed: bool, missing: list, requires_restart: bool)
        """
        if not plugin_info.requirements["python"]:
            return True, [], False
        
        missing = []
        requires_restart = False
        
        for req in plugin_info.requirements["python"]:
            # Extract package name (remove version specification)
            pkg_name = req.split(">=")[0].split("==")[0].split(">")[0].split("<")[0].split("~")[0].strip()
            
            # Handle packages with different import names
            import_name_map = {
                'pycryptodome': 'Crypto',
                'pycryptodomex': 'Cryptodome',
                'pyside6': 'PySide6',
                'pyqt5': 'PyQt5',
                'pyqt6': 'PyQt6',
                'python-nmap': 'nmap',
            }
            
            # Try the mapped import name first, then the package name
            import_names = [import_name_map.get(pkg_name.lower(), pkg_name), pkg_name]
            
            # Try to import the package to check if it's available
            found = False
            for import_name in import_names:
                try:
                    import importlib.util
                    spec = importlib.util.find_spec(import_name)
                    if spec is not None:
                        found = True
                        logger.debug(f"Requirement {req} (package {pkg_name}, import {import_name}) is already installed")
                        break
                except Exception as e:
                    logger.debug(f"Error checking requirement {req} with import name {import_name}: {e}")
                    continue
            
            if not found:
                missing.append(req)
                logger.debug(f"Requirement {req} (package {pkg_name}) is not installed")
        
        # Some packages require a restart after installation (e.g., compiled extensions)
        # Check if any missing packages might require restart
        restart_required_packages = ['scapy', 'netifaces', 'pyside6', 'pyqt5', 'pyqt6']
        if missing:
            for req in missing:
                pkg_name = req.split(">=")[0].split("==")[0].split(">")[0].split("<")[0].split("~")[0].strip().lower()
                if any(restart_pkg in pkg_name for restart_pkg in restart_required_packages):
                    requires_restart = True
                    break
        
        all_installed = len(missing) == 0
        return all_installed, missing, requires_restart
    
    def _verify_plugin_working(self, plugin_info):
        """
        Verify that a plugin is actually working after loading
        
        Args:
            plugin_info: The PluginInfo object
            
        Returns:
            tuple: (is_working: bool, error_message: str or None)
        """
        if not plugin_info.instance:
            return False, "Plugin instance is None"
        
        try:
            # Check if plugin has required attributes
            if not hasattr(plugin_info.instance, 'initialize'):
                return False, "Plugin missing initialize method"
            
            # Check if plugin is properly initialized
            if not hasattr(plugin_info.instance, '_initialized'):
                # Some plugins might not set this, so check if app is set
                if not hasattr(plugin_info.instance, 'app') or plugin_info.instance.app is None:
                    return False, "Plugin not properly initialized (app is None)"
            elif not plugin_info.instance._initialized:
                return False, "Plugin initialization flag is False"
            
            # Try to call a simple method to verify it's working
            # Use get_settings as it's a safe method that should always work
            try:
                settings = plugin_info.instance.get_settings()
                # If we get here without exception, plugin is at least callable
            except Exception as e:
                logger.warning(f"Plugin {plugin_info.id} get_settings() raised exception: {e}")
                # Don't fail on this, as some plugins might not implement it properly
            
            return True, None
            
        except Exception as e:
            error_msg = f"Error verifying plugin: {str(e)}"
            logger.error(f"Plugin {plugin_info.id} verification failed: {error_msg}")
            return False, error_msg
    
    def _requires_restart_after_install(self, installed_packages):
        """
        Check if installed packages require a restart
        
        Args:
            installed_packages: List of package names that were just installed
            
        Returns:
            bool: True if restart is required
        """
        # Packages that typically require a restart after installation
        restart_required = [
            'scapy', 'netifaces', 'pyside6', 'pyqt5', 'pyqt6', 
            'pywin32', 'pycryptodome', 'cryptography'
        ]
        
        for pkg in installed_packages:
            pkg_lower = pkg.lower()
            for restart_pkg in restart_required:
                if restart_pkg in pkg_lower:
                    logger.info(f"Package {pkg} requires application restart")
                    return True
        
        return False
    
    def _save_workspace_for_restart(self, workspace_name):
        """
        Save workspace state before restart
        
        Args:
            workspace_name: Name of the workspace to save
            
        Returns:
            bool: True if saved successfully
        """
        try:
            # Save workspace state
            if hasattr(self.app, 'device_manager'):
                self.app.device_manager.save_workspace(workspace_name)
            
            # Save window layout
            if hasattr(self.app, 'main_window') and self.app.main_window:
                self.app.main_window._save_workspace_layout()
            
            # Create restart state file
            restart_state_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "config", "restart_state.json"
            )
            
            restart_state = {
                "workspace_name": workspace_name,
                "timestamp": str(datetime.now()),
                "reason": "plugin_dependency_install"
            }
            
            os.makedirs(os.path.dirname(restart_state_file), exist_ok=True)
            with open(restart_state_file, 'w') as f:
                json.dump(restart_state, f, indent=2)
            
            logger.info(f"Saved workspace state for restart: {workspace_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving workspace for restart: {e}", exc_info=True)
            return False
    
    def _offer_system_dependency_installation(self, plugin_info, missing_deps, dep_messages):
        """
        Offer to install missing system dependencies with download/install options
        
        Args:
            plugin_info: The PluginInfo object
            missing_deps: List of missing system dependencies
            dep_messages: Dict mapping dependency names to installation messages
            
        Returns:
            bool: True if user chose to install, False if declined
        """
        import platform
        import webbrowser
        import subprocess
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit, QMessageBox
        
        system = platform.system()
        
        # Get parent window
        parent = None
        if hasattr(self.app, 'main_window') and self.app.main_window:
            parent = self.app.main_window
        elif hasattr(self.app, 'activeWindow') and self.app.activeWindow():
            parent = self.app.activeWindow()
        
        # Create dialog
        dialog = QDialog(parent)
        dialog.setWindowTitle(f"Install System Dependencies for {plugin_info.name}")
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout(dialog)
        
        # Main message
        main_label = QLabel(
            f"Plugin '{plugin_info.name}' requires the following system dependencies:\n\n"
            f"{chr(10).join([f'  • {dep}' for dep in missing_deps])}\n\n"
            f"Would you like to install them now?"
        )
        main_label.setWordWrap(True)
        layout.addWidget(main_label)
        
        # Installation instructions
        instructions_text = QTextEdit()
        instructions_text.setReadOnly(True)
        instructions_text.setMaximumHeight(150)
        instructions = []
        
        for dep in missing_deps:
            dep_lower = dep.lower()
            if "nmap" in dep_lower:
                if system == "Windows":
                    instructions.append(
                        "Nmap (Windows):\n"
                        "  • Click 'Download Installer' to open the download page\n"
                        "  • Download and run the installer\n"
                        "  • Make sure to add nmap to PATH during installation\n"
                        "  • Restart NetWORKS after installation"
                    )
                elif system == "Darwin":  # macOS
                    instructions.append(
                        "Nmap (macOS):\n"
                        "  • Click 'Install via Homebrew' to run: brew install nmap\n"
                        "  • Or install manually: brew install nmap\n"
                        "  • Restart NetWORKS after installation"
                    )
                else:  # Linux
                    instructions.append(
                        "Nmap (Linux):\n"
                        "  • Click 'Install via Package Manager' to run the install command\n"
                        "  • Or install manually: sudo apt install nmap (or equivalent)\n"
                        "  • Restart NetWORKS after installation"
                    )
        
        instructions_text.setPlainText("\n\n".join(instructions))
        layout.addWidget(instructions_text)
        
        # Buttons
        button_layout = QVBoxLayout()
        
        install_clicked = False
        
        def download_installer():
            """Open download page for Windows installer"""
            nonlocal install_clicked
            try:
                webbrowser.open("https://nmap.org/download.html")
                install_clicked = True
                QMessageBox.information(
                    dialog,
                    "Download Started",
                    "The download page has been opened in your browser.\n\n"
                    "After downloading and installing nmap, please restart NetWORKS."
                )
                dialog.accept()
            except Exception as e:
                logger.error(f"Failed to open download page: {e}")
                QMessageBox.critical(
                    dialog,
                    "Error",
                    f"Failed to open download page: {e}\n\n"
                    "Please visit https://nmap.org/download.html manually."
                )
        
        def install_via_package_manager():
            """Install via package manager (macOS/Linux)"""
            nonlocal install_clicked
            try:
                if system == "Darwin":  # macOS
                    # Check if brew is available
                    try:
                        subprocess.run(["brew", "--version"], capture_output=True, check=True, timeout=5)
                        # Run brew install
                        result = QMessageBox.question(
                            dialog,
                            "Install via Homebrew",
                            "This will run: brew install nmap\n\n"
                            "Do you want to continue?",
                            QMessageBox.Yes | QMessageBox.No
                        )
                        if result == QMessageBox.Yes:
                            # Run in a way that shows output
                            import threading
                            def run_install():
                                try:
                                    proc = subprocess.Popen(
                                        ["brew", "install", "nmap"],
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        text=True
                                    )
                                    stdout, stderr = proc.communicate()
                                    if proc.returncode == 0:
                                        install_clicked = True
                                        QMessageBox.information(
                                            dialog,
                                            "Installation Complete",
                                            "Nmap has been installed successfully!\n\n"
                                            "Please restart NetWORKS."
                                        )
                                        dialog.accept()
                                    else:
                                        QMessageBox.warning(
                                            dialog,
                                            "Installation Failed",
                                            f"Installation failed:\n{stderr}\n\n"
                                            "Please install manually: brew install nmap"
                                        )
                                except Exception as e:
                                    QMessageBox.critical(
                                        dialog,
                                        "Error",
                                        f"Failed to install: {e}"
                                    )
                            thread = threading.Thread(target=run_install, daemon=True)
                            thread.start()
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        QMessageBox.warning(
                            dialog,
                            "Homebrew Not Found",
                            "Homebrew is not installed or not in PATH.\n\n"
                            "Please install Homebrew first, or install nmap manually:\n"
                            "brew install nmap"
                        )
                else:  # Linux
                    # Try to detect package manager
                    package_managers = [
                        ("apt", ["sudo", "apt", "install", "-y", "nmap"]),
                        ("yum", ["sudo", "yum", "install", "-y", "nmap"]),
                        ("dnf", ["sudo", "dnf", "install", "-y", "nmap"]),
                        ("pacman", ["sudo", "pacman", "-S", "--noconfirm", "nmap"]),
                        ("zypper", ["sudo", "zypper", "install", "-y", "nmap"]),
                    ]
                    
                    detected_pm = None
                    for pm_name, pm_cmd in package_managers:
                        try:
                            subprocess.run([pm_name, "--version"], capture_output=True, check=True, timeout=2)
                            detected_pm = pm_cmd
                            break
                        except (FileNotFoundError, subprocess.TimeoutExpired):
                            continue
                    
                    if detected_pm:
                        result = QMessageBox.question(
                            dialog,
                            "Install via Package Manager",
                            f"This will run: {' '.join(detected_pm)}\n\n"
                            "You may be prompted for your password.\n\n"
                            "Do you want to continue?",
                            QMessageBox.Yes | QMessageBox.No
                        )
                        if result == QMessageBox.Yes:
                            import threading
                            def run_install():
                                try:
                                    proc = subprocess.Popen(
                                        detected_pm,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        text=True
                                    )
                                    stdout, stderr = proc.communicate()
                                    if proc.returncode == 0:
                                        install_clicked = True
                                        QMessageBox.information(
                                            dialog,
                                            "Installation Complete",
                                            "Nmap has been installed successfully!\n\n"
                                            "Please restart NetWORKS."
                                        )
                                        dialog.accept()
                                    else:
                                        QMessageBox.warning(
                                            dialog,
                                            "Installation Failed",
                                            f"Installation failed:\n{stderr}\n\n"
                                            f"Please install manually: {' '.join(detected_pm)}"
                                        )
                                except Exception as e:
                                    QMessageBox.critical(
                                        dialog,
                                        "Error",
                                        f"Failed to install: {e}"
                                    )
                            thread = threading.Thread(target=run_install, daemon=True)
                            thread.start()
                    else:
                        QMessageBox.warning(
                            dialog,
                            "Package Manager Not Detected",
                            "Could not detect a supported package manager.\n\n"
                            "Please install nmap manually using your distribution's package manager."
                        )
            except Exception as e:
                logger.error(f"Error in package manager installation: {e}")
                QMessageBox.critical(dialog, "Error", f"Installation error: {e}")
        
        # Add appropriate buttons based on platform
        if system == "Windows":
            download_btn = QPushButton("Download Installer")
            download_btn.clicked.connect(download_installer)
            button_layout.addWidget(download_btn)
        elif system == "Darwin":  # macOS
            brew_btn = QPushButton("Install via Homebrew")
            brew_btn.clicked.connect(install_via_package_manager)
            button_layout.addWidget(brew_btn)
        else:  # Linux
            pm_btn = QPushButton("Install via Package Manager")
            pm_btn.clicked.connect(install_via_package_manager)
            button_layout.addWidget(pm_btn)
        
        # Manual install button (always available)
        manual_btn = QPushButton("I'll Install Manually")
        manual_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(manual_btn)
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Show dialog
        result = dialog.exec()
        return install_clicked or result == QDialog.Accepted
    
    def _show_warning_dialog(self, title, message, detailed_text=None, parent=None):
        """
        Show a warning dialog to the user
        
        Args:
            title: Dialog title
            message: Main warning message
            detailed_text: Optional detailed warning text
            parent: Optional parent widget
        """
        try:
            # Get parent window if available
            if parent is None:
                if hasattr(self.app, 'main_window') and self.app.main_window:
                    parent = self.app.main_window
                elif hasattr(self.app, 'activeWindow') and self.app.activeWindow():
                    parent = self.app.activeWindow()
            
            msg = QMessageBox(parent)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle(title)
            msg.setText(message)
            
            if detailed_text:
                msg.setDetailedText(detailed_text)
            
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
        except Exception as e:
            # Fallback to console if dialog fails
            logger.warning(f"Failed to show warning dialog: {e}")
            logger.warning(f"Warning: {title} - {message}")
            if detailed_text:
                logger.warning(f"Details: {detailed_text}")
    
    def _show_error_dialog(self, title, message, detailed_text=None, parent=None):
        """
        Show an error dialog to the user
        
        Args:
            title: Dialog title
            message: Main error message
            detailed_text: Optional detailed error text
            parent: Optional parent widget
        """
        try:
            # Get parent window if available
            if parent is None:
                if hasattr(self.app, 'main_window') and self.app.main_window:
                    parent = self.app.main_window
                elif hasattr(self.app, 'activeWindow') and self.app.activeWindow():
                    parent = self.app.activeWindow()
            
            msg = QMessageBox(parent)
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle(title)
            msg.setText(message)
            
            if detailed_text:
                msg.setDetailedText(detailed_text)
            
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
        except Exception as e:
            # Fallback to console if dialog fails
            logger.error(f"Failed to show error dialog: {e}")
            logger.error(f"Error: {title} - {message}")
            if detailed_text:
                logger.error(f"Details: {detailed_text}")
    
    def _check_and_restore_workspace_after_restart(self):
        """
        Check if we need to restore workspace after restart and do so
        
        Returns:
            bool: True if workspace was restored, False otherwise
        """
        try:
            restart_state_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "config", "restart_state.json"
            )
            
            if not os.path.exists(restart_state_file):
                return False
            
            # Load restart state
            with open(restart_state_file, 'r') as f:
                restart_state = json.load(f)
            
            workspace_name = restart_state.get("workspace_name")
            if not workspace_name:
                logger.warning("Restart state file exists but no workspace name found")
                return False
            
            # Restore workspace
            if hasattr(self.app, 'device_manager'):
                logger.info(f"Restoring workspace after restart: {workspace_name}")
                success = self.app.device_manager.load_workspace(workspace_name)
                
                if success and hasattr(self.app, 'main_window') and self.app.main_window:
                    self.app.main_window.refresh_workspace_ui()
                
                # Remove restart state file
                try:
                    os.remove(restart_state_file)
                except Exception as e:
                    logger.warning(f"Could not remove restart state file: {e}")
                
                return success
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking/restoring workspace after restart: {e}", exc_info=True)
            return False
    
    def validate_plugin(self, plugin_info, check_structure=True, check_requirements=True, check_dependencies=True):
        """
        Validate a plugin's structure and configuration without loading it
        
        Args:
            plugin_info: The PluginInfo object to validate
            check_structure: Whether to check file structure and entry point
            check_requirements: Whether to check if requirements are installed
            check_dependencies: Whether to check if dependencies are satisfied
            
        Returns:
            dict: Validation result with keys:
                - valid: bool - Whether plugin passed all checks
                - errors: list - List of error messages
                - warnings: list - List of warning messages
                - checks: dict - Individual check results
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "checks": {}
        }
        
        logger.info(f"Validating plugin: {plugin_info.id}")
        
        # Check 1: Plugin directory exists
        if check_structure:
            if not plugin_info.path or not os.path.exists(plugin_info.path):
                error_msg = f"Plugin directory does not exist: {plugin_info.path}"
                result["errors"].append(error_msg)
                result["checks"]["directory_exists"] = False
                result["valid"] = False
            else:
                result["checks"]["directory_exists"] = True
            
            # Check 2: Entry point file exists
            if plugin_info.path and os.path.exists(plugin_info.path):
                plugin_file = os.path.join(plugin_info.path, plugin_info.entry_point)
                if not os.path.exists(plugin_file):
                    error_msg = f"Entry point file not found: {plugin_file}"
                    result["errors"].append(error_msg)
                    result["checks"]["entry_point_exists"] = False
                    result["valid"] = False
                else:
                    result["checks"]["entry_point_exists"] = True
                    
                    # Check 3: Entry point file is readable Python
                    try:
                        with open(plugin_file, 'r', encoding='utf-8') as f:
                            # Try to compile to check for syntax errors
                            compile(f.read(), plugin_file, 'exec')
                        result["checks"]["entry_point_syntax"] = True
                    except SyntaxError as e:
                        error_msg = f"Syntax error in entry point file: {str(e)}"
                        result["errors"].append(error_msg)
                        result["checks"]["entry_point_syntax"] = False
                        result["valid"] = False
                    except Exception as e:
                        warning_msg = f"Could not verify entry point syntax: {str(e)}"
                        result["warnings"].append(warning_msg)
                        result["checks"]["entry_point_syntax"] = None
            
            # Check 4: API.md documentation exists
            api_doc_path = os.path.join(plugin_info.path, "API.md")
            if not os.path.exists(api_doc_path):
                warning_msg = "API.md documentation file is missing"
                result["warnings"].append(warning_msg)
                result["checks"]["has_documentation"] = False
            else:
                result["checks"]["has_documentation"] = True
        
        # Check 5: Requirements are installed (if checking requirements)
        if check_requirements and plugin_info.requirements["python"]:
            all_installed, missing, _ = self._check_plugin_requirements_installed(plugin_info)
            if not all_installed:
                warning_msg = f"Missing Python requirements: {', '.join(missing)}"
                result["warnings"].append(warning_msg)
                result["checks"]["requirements_installed"] = False
            else:
                result["checks"]["requirements_installed"] = True
        
        # Check 6: Dependencies are satisfied (if checking dependencies)
        if check_dependencies and plugin_info.dependencies:
            for dependency in plugin_info.dependencies:
                dep_id = dependency.get("id") if isinstance(dependency, dict) else dependency
                if dep_id not in self.plugins:
                    warning_msg = f"Dependency plugin '{dep_id}' not found"
                    result["warnings"].append(warning_msg)
                    result["checks"]["dependencies_satisfied"] = False
                else:
                    dep_plugin = self.plugins[dep_id]
                    if not dep_plugin.state.is_enabled:
                        warning_msg = f"Dependency plugin '{dep_id}' is not enabled"
                        result["warnings"].append(warning_msg)
                        result["checks"]["dependencies_satisfied"] = False
                    else:
                        result["checks"]["dependencies_satisfied"] = True
        
        # Check 7: App version compatibility
        if plugin_info.min_app_version or plugin_info.max_app_version:
            if not self._is_plugin_compatible(plugin_info):
                error_msg = "Plugin is not compatible with current app version"
                result["errors"].append(error_msg)
                result["checks"]["version_compatible"] = False
                result["valid"] = False
            else:
                result["checks"]["version_compatible"] = True
        
        # Update plugin info with validation results
        plugin_info.validation_result = result
        plugin_info.last_validated = datetime.now()
        plugin_info.validation_errors = result["errors"]
        plugin_info.validation_warnings = result["warnings"]
        
        logger.info(f"Plugin {plugin_info.id} validation: {'PASSED' if result['valid'] else 'FAILED'}")
        if result["errors"]:
            logger.error(f"Validation errors: {', '.join(result['errors'])}")
        if result["warnings"]:
            logger.warning(f"Validation warnings: {', '.join(result['warnings'])}")
        
        return result
    
    def test_plugin(self, plugin_info, dry_run=True):
        """
        Test a plugin by attempting to load it without actually initializing it
        
        This performs a more thorough test than validate_plugin by actually
        trying to import the module and find the plugin class.
        
        Args:
            plugin_info: The PluginInfo object to test
            dry_run: If True, don't actually create an instance or initialize
            
        Returns:
            dict: Test result with keys:
                - success: bool - Whether test passed
                - errors: list - List of error messages
                - warnings: list - List of warning messages
                - can_import: bool - Whether module can be imported
                - can_find_class: bool - Whether plugin class can be found
                - can_instantiate: bool - Whether plugin can be instantiated (if not dry_run)
        """
        result = {
            "success": True,
            "errors": [],
            "warnings": [],
            "can_import": False,
            "can_find_class": False,
            "can_instantiate": False
        }
        
        logger.info(f"Testing plugin: {plugin_info.id} (dry_run={dry_run})")
        
        # First, validate the plugin structure
        validation = self.validate_plugin(plugin_info, check_structure=True, check_requirements=False, check_dependencies=False)
        if not validation["valid"]:
            result["errors"].extend(validation["errors"])
            result["success"] = False
            return result
        
        result["warnings"].extend(validation["warnings"])
        
        try:
            import importlib.util
            import sys
            
            # Test 1: Can we import the module?
            plugin_file = os.path.join(plugin_info.path, plugin_info.entry_point)
            module_name = os.path.splitext(plugin_info.entry_point)[0]
            
            # Add plugin directory to sys.path temporarily
            plugin_path_in_sys = plugin_info.path in sys.path
            if not plugin_path_in_sys:
                sys.path.insert(0, plugin_info.path)
            
            try:
                # Try to find the module spec
                spec = importlib.util.find_spec(module_name)
                if spec is None:
                    spec = importlib.util.spec_from_file_location(module_name, plugin_file)
                
                if spec is None:
                    error_msg = f"Failed to create module spec for {module_name}"
                    result["errors"].append(error_msg)
                    result["success"] = False
                    return result
                
                # Try to load the module (but don't execute if it's already loaded)
                if module_name in sys.modules:
                    module = sys.modules[module_name]
                    result["can_import"] = True
                else:
                    # Create module but don't execute yet
                    module = importlib.util.module_from_spec(spec)
                    # For testing, we'll try to execute it in a controlled way
                    try:
                        spec.loader.exec_module(module)
                        result["can_import"] = True
                    except Exception as e:
                        error_msg = f"Failed to execute module: {str(e)}"
                        result["errors"].append(error_msg)
                        result["success"] = False
                        # Clean up
                        if module_name in sys.modules:
                            del sys.modules[module_name]
                        return result
                
                # Test 2: Can we find the plugin class?
                plugin_class = None
                for attr_name in dir(module):
                    try:
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            attr.__module__ == module.__name__ and 
                            hasattr(attr, 'initialize')):
                            plugin_class = attr
                            break
                    except Exception as e:
                        # Skip attributes that can't be accessed
                        continue
                
                if not plugin_class:
                    error_msg = "No plugin class found with 'initialize' method"
                    result["errors"].append(error_msg)
                    result["success"] = False
                    return result
                
                result["can_find_class"] = True
                
                # Test 3: Can we instantiate the plugin? (only if not dry_run)
                if not dry_run:
                    try:
                        instance = plugin_class()
                        result["can_instantiate"] = True
                        
                        # Don't actually initialize, just verify the class structure
                        if not hasattr(instance, 'initialize'):
                            error_msg = "Plugin instance missing 'initialize' method"
                            result["errors"].append(error_msg)
                            result["success"] = False
                        
                        # Clean up instance
                        del instance
                    except Exception as e:
                        error_msg = f"Failed to instantiate plugin class: {str(e)}"
                        result["errors"].append(error_msg)
                        result["success"] = False
                
            finally:
                # Clean up: remove from sys.path if we added it
                if not plugin_path_in_sys and plugin_info.path in sys.path:
                    sys.path.remove(plugin_info.path)
                
                # Clean up module from sys.modules if we loaded it for testing
                if module_name in sys.modules and not plugin_info.state.is_loaded:
                    # Only remove if plugin isn't actually loaded
                    try:
                        del sys.modules[module_name]
                    except:
                        pass
            
            if result["success"]:
                logger.info(f"Plugin {plugin_info.id} test: PASSED")
            else:
                logger.error(f"Plugin {plugin_info.id} test: FAILED - {', '.join(result['errors'])}")
            
        except Exception as e:
            import traceback
            error_msg = f"Unexpected error during plugin test: {str(e)}"
            error_details = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            result["errors"].append(error_msg)
            result["errors"].append(f"Traceback: {error_details}")
            result["success"] = False
            logger.error(f"Plugin {plugin_info.id} test error: {error_msg}", exc_info=True)
        
        return result
    
    def validate_all_plugins(self):
        """
        Validate all discovered plugins
        
        Returns:
            dict: Summary of validation results
        """
        logger.info("Validating all plugins...")
        
        results = {
            "total": len(self.plugins),
            "valid": 0,
            "invalid": 0,
            "warnings": 0,
            "plugins": {}
        }
        
        for plugin_id, plugin_info in self.plugins.items():
            validation = self.validate_plugin(plugin_info)
            results["plugins"][plugin_id] = validation
            
            if validation["valid"]:
                results["valid"] += 1
            else:
                results["invalid"] += 1
            
            if validation["warnings"]:
                results["warnings"] += 1
        
        logger.info(f"Validation complete: {results['valid']} valid, {results['invalid']} invalid, {results['warnings']} with warnings")
        return results
    
    def _install_plugin_requirements(self, plugin_info):
        """Install Python package requirements for a plugin"""
        if not plugin_info.requirements["python"]:
            logger.debug(f"No Python requirements to install for plugin {plugin_info.id}")
            return True
            
        try:
            import subprocess
            import sys
            import platform
            
            # Get the path to the current Python executable
            python_exe = sys.executable
            
            # Packages that should use pre-built wheels on Windows to avoid compilation issues
            # These packages require Microsoft Visual C++ Build Tools if compiled from source
            binary_only_packages = ['netifaces', 'scapy', 'pycryptodome', 'cryptography']
            
            # Use pip to install the requirements
            requirements = plugin_info.requirements["python"]
            logger.info(f"Installing {len(requirements)} Python package(s) for plugin {plugin_info.id}")
            
            # Emit status signal
            self.plugin_status_changed.emit(plugin_info, f"Installing requirements: {', '.join(requirements)}")
            
            for req in requirements:
                logger.info(f"Installing requirement: {req}")
                self.plugin_status_changed.emit(plugin_info, f"Installing: {req}")
                
                # Extract package name to check if it needs binary-only installation
                pkg_name = req.split(">=")[0].split("==")[0].split(">")[0].split("<")[0].split("~")[0].split("!")[0].strip().lower()
                
                # On Windows, try pre-built wheels first for packages that require compilation
                use_binary_only = platform.system() == "Windows" and any(binary_pkg in pkg_name for binary_pkg in binary_only_packages)
                
                # Build pip install command - try binary-only first if needed
                cmd = [python_exe, "-m", "pip", "install", req, "--no-cache-dir"]
                if use_binary_only:
                    cmd.append("--only-binary=:all:")
                    logger.debug(f"Attempting to install {req} using pre-built wheels only")
                
                # Run pip install
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                # If binary-only failed with "no matching distribution", try fallback strategies
                if result.returncode != 0 and use_binary_only:
                    error_output = result.stderr or result.stdout
                    if "Could not find a version" in error_output or "No matching distribution found" in error_output:
                        logger.warning(f"Pre-built wheel not available for {req}, trying fallback strategies...")
                        
                        # Strategy 1: Try without version constraint (just package name)
                        logger.debug(f"Fallback 1: Trying to install {pkg_name} without version constraint")
                        self.plugin_status_changed.emit(plugin_info, f"Trying alternative installation method...")
                        cmd_fallback1 = [python_exe, "-m", "pip", "install", pkg_name, "--no-cache-dir", "--prefer-binary"]
                        result = subprocess.run(cmd_fallback1, capture_output=True, text=True)
                        
                        # Strategy 2: If that fails, try with --upgrade and prefer binary
                        if result.returncode != 0:
                            logger.debug(f"Fallback 2: Trying with --upgrade flag")
                            cmd_fallback2 = [python_exe, "-m", "pip", "install", "--upgrade", pkg_name, "--no-cache-dir", "--prefer-binary"]
                            result = subprocess.run(cmd_fallback2, capture_output=True, text=True)
                        
                        # Strategy 3: If still failing, upgrade pip and try once more
                        if result.returncode != 0:
                            logger.debug(f"Fallback 3: Upgrading pip and retrying")
                            self.plugin_status_changed.emit(plugin_info, f"Upgrading pip and retrying...")
                            subprocess.run([python_exe, "-m", "pip", "install", "--upgrade", "pip"], capture_output=True)
                            cmd_fallback3 = [python_exe, "-m", "pip", "install", pkg_name, "--no-cache-dir", "--prefer-binary"]
                            result = subprocess.run(cmd_fallback3, capture_output=True, text=True)
                
                if result.returncode != 0:
                    error_msg = result.stderr or result.stdout
                    logger.error(f"Failed to install requirement {req}: {error_msg}")
                    
                    # Provide helpful error message for compilation errors
                    if "Microsoft Visual C++" in error_msg or "error: Microsoft Visual C++" in error_msg:
                        helpful_msg = (
                            f"Failed to install {req}. This package requires compilation on Windows.\n\n"
                            f"Solution: Install Microsoft C++ Build Tools from:\n"
                            f"https://visualstudio.microsoft.com/visual-cpp-build-tools/\n\n"
                            f"After installing, try manually:\n"
                            f"pip install {req}\n\n"
                            f"Error details: {error_msg[:500]}"
                        )
                        self.plugin_status_changed.emit(plugin_info, f"Error installing {req}: Compilation required")
                        logger.error(helpful_msg)
                    elif "Could not find a version" in error_msg or "No matching distribution found" in error_msg:
                        helpful_msg = (
                            f"Failed to install {req}. No compatible version found for your Python version.\n\n"
                            f"Your Python version: {sys.version}\n\n"
                            f"Possible solutions:\n"
                            f"1. Try installing without version constraint: pip install {pkg_name}\n"
                            f"2. Check if the package supports your Python version\n"
                            f"3. Update Python to a supported version\n\n"
                            f"Error details: {error_msg[:300]}"
                        )
                        self.plugin_status_changed.emit(plugin_info, f"Error installing {req}: No compatible version")
                        logger.error(helpful_msg)
                    else:
                        self.plugin_status_changed.emit(plugin_info, f"Error installing {req}: {error_msg[:200]}")
                    
                    return False
                    
                logger.info(f"Successfully installed requirement: {req}")
                self.plugin_status_changed.emit(plugin_info, f"Installed: {req}")
                
            logger.info(f"All requirements for plugin {plugin_info.id} installed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error installing requirements for plugin {plugin_info.id}: {str(e)}")
            self.plugin_status_changed.emit(plugin_info, f"Error installing requirements: {str(e)}")
            return False
            
    def _uninstall_plugin_requirements(self, plugin_info):
        """Uninstall Python package requirements for a plugin"""
        if not plugin_info.requirements["python"]:
            return True
            
        try:
            import subprocess
            import sys
            
            # Get the path to the current Python executable
            python_exe = sys.executable
            
            # Use pip to uninstall the requirements
            requirements = plugin_info.requirements["python"]
            logger.info(f"Uninstalling {len(requirements)} Python package(s) for plugin {plugin_info.id}")
            
            # Emit status signal
            self.plugin_status_changed.emit(plugin_info, f"Uninstalling requirements: {', '.join(requirements)}")
            
            for req in requirements:
                # Extract package name (remove version specification)
                pkg_name = req.split(">=")[0].split("==")[0].split(">")[0].split("<")[0].strip()
                
                logger.info(f"Uninstalling requirement: {pkg_name}")
                self.plugin_status_changed.emit(plugin_info, f"Uninstalling: {pkg_name}")
                
                # Run pip uninstall
                cmd = [python_exe, "-m", "pip", "uninstall", "-y", pkg_name]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.warning(f"Failed to uninstall requirement {pkg_name}: {result.stderr}")
                    self.plugin_status_changed.emit(plugin_info, f"Warning: Could not uninstall {pkg_name}")
                    # Continue with other requirements
                else:
                    logger.info(f"Successfully uninstalled requirement: {pkg_name}")
                    self.plugin_status_changed.emit(plugin_info, f"Uninstalled: {pkg_name}")
                
            return True
            
        except Exception as e:
            logger.error(f"Error uninstalling requirements for plugin {plugin_info.id}: {str(e)}")
            self.plugin_status_changed.emit(plugin_info, f"Error uninstalling requirements: {str(e)}")
            return False
            
    def _set_plugin_state(self, plugin_info, state):
        """Set the state of a plugin"""
        if not isinstance(state, PluginState):
            raise TypeError("Expected PluginState value")
            
        # Previous state for logging
        previous_state = plugin_info.state
        
        # Always clear the instance when transitioning to DISABLED or ERROR state
        if state in (PluginState.DISABLED, PluginState.ERROR) and plugin_info.instance is not None:
            logger.debug(f"Clearing instance for plugin {plugin_info.id} during transition to {state.name}")
            
            # Call cleanup if possible
            if hasattr(plugin_info.instance, 'cleanup') and callable(plugin_info.instance.cleanup):
                try:
                    logger.debug(f"Calling cleanup for plugin {plugin_info.id} during state transition")
                    plugin_info.instance.cleanup()
                except Exception as e:
                    logger.error(f"Error during cleanup in state transition: {e}")
            
            # Force clear instance
            plugin_info.instance = None
            
            # Force garbage collection
            import gc
            gc.collect()
            
        # Set the new state
        plugin_info.state = state
        
        # Log the transition
        if previous_state != plugin_info.state:
            logger.debug(f"Plugin {plugin_info.id} state transition: {previous_state.name} -> {plugin_info.state.name}")
            
            # If transitioning to DISABLED, enforce instance is None
            if plugin_info.state == PluginState.DISABLED and plugin_info.instance is not None:
                logger.warning(f"Plugin {plugin_info.id} instance still exists after transition to DISABLED - forcing clear")
                plugin_info.instance = None
                
                # Run garbage collection again
                import gc
                gc.collect()
        
    def uninstall_plugin(self, plugin_id):
        """Uninstall a plugin completely"""
        if plugin_id not in self.plugins:
            logger.warning(f"Cannot uninstall unknown plugin: {plugin_id}")
            return False
            
        plugin_info = self.plugins[plugin_id]
        
        # Ensure plugin is disabled and unloaded first
        if plugin_info.state.is_enabled:
            if not self.disable_plugin(plugin_id):
                logger.warning(f"Failed to disable plugin {plugin_id} during uninstall operation")
                return False
        
        # Uninstall Python requirements if any were installed
        if plugin_info.requirements["python"]:
            logger.info(f"Uninstalling Python requirements for plugin {plugin_id}")
            self._uninstall_plugin_requirements(plugin_info)
        
        # Remove the plugin directory
        plugin_dir = plugin_info.path
        try:
            if os.path.exists(plugin_dir) and os.path.isdir(plugin_dir):
                logger.info(f"Removing plugin directory: {plugin_dir}")
                shutil.rmtree(plugin_dir)
        except Exception as e:
            logger.error(f"Failed to remove plugin directory: {e}")
            return False
            
        # Remove from registry
        del self.plugins[plugin_id]
        self._registry_dirty = True
        self._sync_registry()
        
        return True 