#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Command handler for managing command sets and executing commands
"""

import os
import json
import re
from pathlib import Path
from loguru import logger

from plugins.command_manager.utils.command_set import CommandSet, Command


def expand_command_for_device(command_text, device):
    """Expand {{property}} placeholders in command_text using the device's properties.
    Matches Template Manager / Report Generator syntax so variables translate when
    running template-loaded commands."""
    if not command_text or "{{" not in command_text:
        return command_text
    context = {}
    if hasattr(device, "get_properties"):
        try:
            context = dict(device.get_properties() or {})
        except Exception:
            context = {}
    if hasattr(device, "get_property"):
        for key in ("id", "alias", "hostname", "ip_address", "mac_address", "status", "notes", "tags"):
            if key not in context:
                context[key] = device.get_property(key, "")

    def repl(m):
        key = m.group(1).strip()
        val = context.get(key, "")
        if isinstance(val, list):
            return ", ".join(str(v) for v in val)
        return "" if val is None else str(val)

    pattern = re.compile(r"\{\{\s*([^}]+)\s*\}\}")
    return pattern.sub(repl, command_text)
from plugins.command_manager.utils.ssh_client import SSHClient
from plugins.command_manager.utils.telnet_client import TelnetClient

class CommandHandler:
    """Handler for command sets and command execution"""
    
    def __init__(self, plugin):
        """Initialize the handler
        
        Args:
            plugin: The CommandManagerPlugin instance
        """
        self.plugin = plugin
        self.command_sets = {}  # {device_type: {firmware: CommandSet}}
        
    def load_default_command_sets(self):
        """Load default command sets"""
        logger.debug("Loading default command sets")
        
        # Check if cisco_iosxe.json exists in the commands directory
        cisco_iosxe_path = self.plugin.commands_dir / "cisco_iosxe.json"
        if not cisco_iosxe_path.exists():
            logger.debug(f"Default cisco_iosxe.json not found at {cisco_iosxe_path}")
            # Look for it in the plugin directory
            source_path = Path(self.plugin.plugin_info.path) / "data" / "commands" / "cisco_iosxe.json"
            logger.debug(f"Checking for source file at {source_path}")
            if source_path.exists():
                # Copy to commands directory
                try:
                    logger.debug(f"Source file found, copying to {cisco_iosxe_path}")
                    with open(source_path, "r") as src:
                        data = json.load(src)
                    
                    with open(cisco_iosxe_path, "w") as dst:
                        json.dump(data, dst, indent=2)
                        
                    logger.info(f"Copied default command set: cisco_iosxe.json")
                except Exception as e:
                    logger.error(f"Error copying default command set: {e}")
            else:
                logger.debug("Source file not found, will try to use embedded data")
        else:
            logger.debug(f"Default cisco_iosxe.json already exists at {cisco_iosxe_path}")
        
        # Load all command sets
        logger.debug("Calling _load_command_sets")
        self._load_command_sets()
        
    def _load_command_sets(self):
        """Load command sets from disk"""
        logger.debug("Loading command sets from disk")
        self.command_sets = {}
        
        # Check if the command sets directory exists
        if not self.plugin.commands_dir.exists():
            logger.warning(f"Command sets directory does not exist: {self.plugin.commands_dir}")
            self.plugin.commands_dir.mkdir(parents=True, exist_ok=True)
            return
        
        # Keep track of problematic files to potentially clean up
        problem_files = []
        
        # Iterate through command set files
        command_files = list(self.plugin.commands_dir.glob("*.json"))
        logger.debug(f"Found {len(command_files)} command set files: {[f.name for f in command_files]}")
        
        for file_path in command_files:
            try:
                # Skip empty files
                if file_path.stat().st_size == 0:
                    logger.warning(f"Skipping empty command set file: {file_path}")
                    problem_files.append(file_path)
                    continue
                    
                logger.info(f"Attempting to load command set from {file_path}")
                with open(file_path, "r", encoding='utf-8') as f:
                    data = json.load(f)
                
                # Extract device type and firmware from filename if it's a list of commands
                # This handles legacy files that are simply lists of commands
                if isinstance(data, list):
                    logger.debug(f"File {file_path.name} contains a list of commands. Extracting info from filename...")
                    
                    # Extract device type and firmware from filename
                    filename = file_path.stem
                    parts = filename.split('_')
                    
                    if len(parts) >= 2:
                        # Reconstruct full device type and firmware
                        device_parts = []
                        firmware_parts = []
                        
                        # Check if filename follows the pattern cisco_ios_xe_16_x
                        if "cisco" in parts[0].lower() and "ios" in filename.lower():
                            device_type = "Cisco IOS XE"
                            
                            # Get firmware from the last parts
                            if "16" in filename or "17" in filename:
                                # Find version in filename
                                for part in parts:
                                    if part.isdigit() or part.startswith(("16", "17")):
                                        firmware_parts.append(part)
                                
                                firmware = '.'.join(firmware_parts) if firmware_parts else "16.x"
                            else:
                                firmware = "16.x"  # Default if none found
                        else:
                            # Generic approach for other devices
                            device_type = ' '.join(parts[:-1]).title()
                            firmware = parts[-1].replace('_', '.')
                        
                        # Create a properly formatted command set
                        logger.debug(f"Extracted device_type={device_type}, firmware={firmware}")
                        commands = data
                    else:
                        # Can't determine device type and firmware from filename
                        device_type = "Unknown"
                        firmware = "Unknown"
                        commands = data
                        logger.warning(f"Could not determine device type and firmware from filename: {filename}")
                
                # Handle standard command set format
                elif isinstance(data, dict) and "device_type" in data and "firmware_version" in data and "commands" in data:
                    device_type = data["device_type"]
                    firmware = data["firmware_version"]
                    commands = data["commands"]
                else:
                    logger.warning(f"Invalid command set format in file: {file_path}")
                    logger.debug(f"Data structure: {type(data)}, Fields: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
                    problem_files.append(file_path)
                    continue
                
                logger.debug(f"Loading command set for {device_type} ({firmware}) with {len(commands)} commands")
                
                if device_type not in self.command_sets:
                    self.command_sets[device_type] = {}
                    
                self.command_sets[device_type][firmware] = commands
                
                logger.info(f"Loaded command set: {device_type} ({firmware})")
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON in command set file {file_path}: {e}")
                problem_files.append(file_path)
                # Try to fix the file if it's the Cisco IOS XE one
                if "cisco" in file_path.name.lower():
                    logger.debug(f"Attempting to fix Cisco command set: {file_path}")
                    self._fix_cisco_command_set()
            except Exception as e:
                logger.error(f"Error loading command set from {file_path}: {e}")
                logger.exception("Exception details:")
                problem_files.append(file_path)
        
        # Clean up problematic files if we have at least one good command set
        if self.command_sets and problem_files:
            logger.debug(f"Found {len(problem_files)} problematic files to clean up")
            for path in problem_files:
                try:
                    # Don't delete cisco_iosxe.json as it might have been fixed
                    if path.name.lower() != "cisco_iosxe.json":
                        logger.debug(f"Removing problematic file: {path}")
                        path.unlink()
                        logger.info(f"Removed problematic command set file: {path}")
                except Exception as e:
                    logger.warning(f"Could not remove problematic file {path}: {e}")
                    
        # Ensure we have at least the default command set
        if not self.command_sets:
            logger.info("No command sets loaded, loading defaults")
            self._fix_cisco_command_set()
            # Try loading again after fixing
            self._load_command_sets()
            
        logger.debug(f"Final command sets: {list(self.command_sets.keys())}")
        
        # Update the plugin's command_sets reference
        self.plugin.command_sets = self.command_sets
        
    def _fix_cisco_command_set(self):
        """Create a default Cisco IOS XE command set"""
        logger.debug("Creating default Cisco IOS XE command set")
        
        # Default commands for Cisco IOS XE
        default_commands = [
            {"command": "show version", "alias": "Show Version", "description": "Display the software version"},
            {"command": "show running-config", "alias": "Show Running Configuration", "description": "Display the current configuration"},
            {"command": "show interfaces", "alias": "Show Interfaces", "description": "Display interface status and configuration"},
            {"command": "show ip interface brief", "alias": "Show IP Interfaces Brief", "description": "Display brief IP interface status"},
            {"command": "show ip route", "alias": "Show IP Route", "description": "Display IP routing table"},
            {"command": "show cdp neighbors", "alias": "Show CDP Neighbors", "description": "Display CDP neighbor information"},
            {"command": "show vlan", "alias": "Show VLANs", "description": "Display VLAN information"}
        ]
        
        # Create a command set file
        cisco_iosxe_data = {
            "device_type": "Cisco IOS XE",
            "firmware_version": "16.x",
            "commands": default_commands
        }
        
        # Save to file
        cisco_iosxe_path = self.plugin.commands_dir / "cisco_iosxe.json"
        try:
            with open(cisco_iosxe_path, "w") as f:
                json.dump(cisco_iosxe_data, f, indent=2)
                
            logger.info(f"Created default Cisco IOS XE command set at {cisco_iosxe_path}")
        except Exception as e:
            logger.error(f"Error creating default Cisco IOS XE command set: {e}")
            logger.exception("Exception details:")
            
    def get_device_types(self):
        """Get available device types from command sets
        
        Returns:
            list: List of device types
        """
        logger.debug("Getting available device types")
        if not self.command_sets:
            logger.warning("No command sets loaded")
            return []
            
        device_types = list(self.command_sets.keys())
        logger.debug(f"Found {len(device_types)} device types: {device_types}")
        return device_types
        
    def get_firmware_versions(self, device_type):
        """Get available firmware versions for a device type
        
        Args:
            device_type (str): Device type to get firmware versions for
            
        Returns:
            list: List of firmware versions
        """
        logger.debug(f"Getting firmware versions for {device_type}")
        if not self.command_sets or device_type not in self.command_sets:
            logger.warning(f"Device type {device_type} not found in command sets")
            return []
            
        firmware_versions = list(self.command_sets[device_type].keys())
        logger.debug(f"Found {len(firmware_versions)} firmware versions: {firmware_versions}")
        return firmware_versions
        
    def get_commands(self, device_type, firmware_version):
        """Get commands for a device type and firmware version
        
        Args:
            device_type (str): Device type to get commands for
            firmware_version (str): Firmware version to get commands for
            
        Returns:
            list: List of commands
        """
        logger.debug(f"Getting commands for {device_type} ({firmware_version})")
        if (not self.command_sets or 
            device_type not in self.command_sets or 
            firmware_version not in self.command_sets[device_type]):
            logger.warning(f"Command set for {device_type} ({firmware_version}) not found")
            return []
            
        commands = self.command_sets[device_type][firmware_version]
        logger.debug(f"Found {len(commands)} commands")
        return commands

    def get_command_set(self, device_type, firmware_version):
        """Get a command set for a device type and firmware version
        
        This returns a CommandSet object for compatibility with CommandDialog
        
        Args:
            device_type (str): Device type to get commands for
            firmware_version (str): Firmware version to get commands for
            
        Returns:
            CommandSet: CommandSet object with commands
        """
        logger.debug(f"Getting command set for {device_type} ({firmware_version})")
        commands = self.get_commands(device_type, firmware_version)
        
        # Create a CommandSet object from the commands list
        # Convert commands to Command objects if needed
        command_objects = []
        for cmd in commands:
            if not hasattr(cmd, 'alias'):
                # Convert dict to Command object
                if isinstance(cmd, dict):
                    alias = cmd.get('alias', cmd.get('command', 'Command'))
                    description = cmd.get('description', '')
                    command = cmd.get('command', '')
                    cmd_obj = Command(command, alias, description)
                    command_objects.append(cmd_obj)
                else:
                    # Skip invalid commands
                    logger.warning(f"Invalid command format: {cmd}")
            else:
                # Already a Command object
                command_objects.append(cmd)
                
        # Create CommandSet
        command_set = CommandSet(device_type, firmware_version, command_objects)
        return command_set
        
    def save_command_sets(self):
        """Save command sets to disk"""
        logger.debug("Saving command sets to disk")
        # Check if the commands directory exists
        if not self.plugin.commands_dir.exists():
            self.plugin.commands_dir.mkdir(parents=True, exist_ok=True)
        
        # Iterate through command sets
        for device_type, firmware_sets in self.command_sets.items():
            for firmware, command_set in firmware_sets.items():
                try:
                    # Create filename from device_type and firmware
                    # Use lowercase to maintain consistent filenames
                    device_type_safe = device_type.lower().replace(' ', '_')
                    firmware_safe = firmware.replace('.', '_')
                    filename = f"{device_type_safe}_{firmware_safe}.json"
                    file_path = self.plugin.commands_dir / filename
                    
                    # Save to file - handle both CommandSet objects and plain lists/dicts
                    with open(file_path, "w") as f:
                        if hasattr(command_set, 'to_dict'):
                            # CommandSet object
                            json.dump(command_set.to_dict(), f, indent=2)
                        else:
                            # List of Command objects (from add_command_set storing .commands)
                            if isinstance(command_set, list):
                                data_to_save = {
                                    "device_type": device_type,
                                    "firmware_version": firmware,
                                    "commands": [
                                        c.to_dict() if hasattr(c, "to_dict") else c
                                        for c in command_set
                                    ],
                                }
                            else:
                                data_to_save = command_set
                            json.dump(data_to_save, f, indent=2)
                
                except Exception as e:
                    logger.error(f"Error saving command set {device_type}_{firmware}: {e}")
                    logger.exception("Exception details:")
                    
    def add_command_set(self, command_set, temporary=False):
        """Add or update a command set.
        
        Args:
            command_set: CommandSet object to add or update
            temporary: If True, do not persist to disk (e.g. template-loaded set; unload when applied).
        """
        logger.debug(f"Adding command set: {command_set.device_type} ({command_set.firmware_version}) temporary={temporary}")
        
        if command_set.device_type not in self.command_sets:
            self.command_sets[command_set.device_type] = {}
            
        self.command_sets[command_set.device_type][command_set.firmware_version] = command_set.commands
        
        if not temporary:
            self.save_command_sets()
        
        logger.info(f"Added command set: {command_set.device_type} ({command_set.firmware_version})")
    
    def delete_command_set(self, device_type, firmware_version):
        """Remove a command set from memory and delete its file if present."""
        if device_type not in self.command_sets:
            return
        if firmware_version in self.command_sets[device_type]:
            del self.command_sets[device_type][firmware_version]
        if not self.command_sets[device_type]:
            del self.command_sets[device_type]
        device_type_safe = device_type.lower().replace(" ", "_")
        firmware_safe = firmware_version.replace(".", "_")
        file_path = self.plugin.commands_dir / f"{device_type_safe}_{firmware_safe}.json"
        if file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Deleted command set file: {file_path.name}")
            except Exception as e:
                logger.warning(f"Could not delete command set file {file_path}: {e}")
        self.save_command_sets()
        
    def run_command(self, device, command, credentials=None):
        """Run a command on a device
        
        Args:
            device: Device to run command on
            command (str): Command to run (may contain {{property}} placeholders; expanded per device)
            credentials (dict, optional): Credentials to use
            
        Returns:
            dict: Command result
        """
        logger.debug(f"Running command on device: {device.id}")
        command = expand_command_for_device(command, device)

        # Get device properties
        device_type = device.get_property("device_type", "")
        ip_address = device.get_property("ip_address", "")
        
        # If no credentials provided, get them with proper hierarchy (Device -> Group -> Subnet)
        if not credentials:
            credentials = self.plugin.get_device_credentials(device.id, device_ip=ip_address)
            
        # Default result
        result = {
            "success": False,
            "output": f"Command: {command}\n\nNo connection method available for device: {device.id}"
        }
        
        # Log credential status
        if not credentials or not credentials.get("username"):
            logger.warning(f"No valid credentials found for device {device.id} ({ip_address})")
            result["output"] = f"Command: {command}\n\nNo valid credentials available for {ip_address}"
            return result
            
        # Determine connection type
        connection_type = credentials.get("connection_type", "ssh").lower()
        
        # Handle SSH connections
        if connection_type == "ssh":
            try:
                logger.debug(f"Connecting to {ip_address} via SSH with username: {credentials.get('username')}")
                
                # Create SSH client with required parameters
                ssh = SSHClient(
                    host=ip_address,
                    username=credentials.get("username"),
                    password=credentials.get("password", ""),
                    enable_password=credentials.get("enable_password", "")
                )
                
                try:
                    # Connect to device
                    ssh.connect()
                    
                    # Try to enter enable mode if needed
                    if credentials.get("enable_password"):
                        ssh.enable()
                    
                    # Execute the command
                    output = ssh.execute(command)
                    
                    # Create successful result
                    result = {
                        "success": True,
                        "output": output
                    }
                    
                    # Disconnect cleanly
                    ssh.disconnect()
                    
                    logger.debug(f"SSH command execution completed successfully")
                except Exception as e:
                    logger.error(f"SSH execution error: {e}")
                    result["output"] = f"Command: {command}\n\nSSH Connection error: {str(e)}"
            except Exception as e:
                logger.error(f"Error running SSH command: {e}")
                logger.exception("Exception details:")
                result["output"] = f"Command: {command}\n\nError running SSH command: {str(e)}"
                
        # Handle Telnet connections
        elif connection_type == "telnet":
            try:
                logger.debug(f"Connecting to {ip_address} via Telnet with username: {credentials.get('username')}")
                
                # Create Telnet client with required parameters
                telnet = TelnetClient(
                    host=ip_address,
                    username=credentials.get("username"),
                    password=credentials.get("password", ""),
                    enable_password=credentials.get("enable_password", "")
                )
                
                try:
                    # Connect to device
                    telnet.connect()
                    
                    # Try to enter enable mode if needed
                    if hasattr(telnet, 'enable') and credentials.get("enable_password"):
                        telnet.enable()
                    
                    # Execute the command
                    output = telnet.execute(command)
                    
                    # Create successful result
                    result = {
                        "success": True,
                        "output": output
                    }
                    
                    # Disconnect cleanly
                    telnet.disconnect()
                    
                    logger.debug(f"Telnet command execution completed successfully")
                except Exception as e:
                    logger.error(f"Telnet execution error: {e}")
                    result["output"] = f"Command: {command}\n\nTelnet Connection error: {str(e)}"
            except Exception as e:
                logger.error(f"Error running Telnet command: {e}")
                logger.exception("Exception details:")
                result["output"] = f"Command: {command}\n\nError running Telnet command: {str(e)}"
        else:
            logger.warning(f"Unsupported connection type: {connection_type}")
            result["output"] = f"Command: {command}\n\nUnsupported connection type: {connection_type}"
            
        return result 