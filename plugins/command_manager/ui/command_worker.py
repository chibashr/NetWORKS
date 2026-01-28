#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Background worker for running commands in the Command Dialog.
"""

from PySide6.QtCore import QObject, Signal


class CommandWorker(QObject):
    """Worker for running commands in the background."""

    command_started = Signal(object, object)  # device, command
    command_complete = Signal(object, object, object, object)  # device, command, result, command_set
    command_progress = Signal(int, int)  # current, total
    all_commands_complete = Signal(object)  # command_set that was run (None for custom commands)

    def __init__(self, plugin, devices, commands, command_set=None):
        """Initialize the worker."""
        super().__init__()
        self.plugin = plugin
        self.devices = devices
        self.commands = commands
        self.command_set = command_set
        self.stop_requested = False

    def run(self):
        """Run the commands on the devices."""
        from loguru import logger
        from plugins.command_manager.core.command_handler import expand_command_for_device
        from plugins.command_manager.utils.ssh_client import SSHClient
        from plugins.command_manager.utils.telnet_client import TelnetClient

        logger.debug(
            f"Starting command execution for {len(self.devices)} devices and {len(self.commands)} commands"
        )
        total_commands = len(self.devices) * len(self.commands)
        completed_commands = 0

        for device in self.devices:
            if self.stop_requested:
                logger.debug("Stop requested - halting command execution")
                break

            device_name = device.get_property(
                "alias", device.get_property("hostname", "Unknown Device")
            )
            device_ip = device.get_property("ip_address", "Unknown IP")
            logger.debug(f"Processing device: {device_name} ({device_ip})")

            device_groups = []
            try:
                device_groups = self.plugin.device_manager.get_device_groups_for_device(
                    device.id
                )
                group_names = []
                for group in device_groups:
                    if isinstance(group, dict) and "name" in group:
                        group_names.append(group["name"])
                    elif hasattr(group, "name"):
                        group_names.append(group.name)
                    elif hasattr(group, "get_name"):
                        group_names.append(group.get_name())
                    else:
                        group_names.append(str(group))
                logger.debug(f"Device {device_name} is in groups: {group_names}")
            except Exception as e:
                logger.error(f"Error getting device groups for device {device_name}: {e}")

            credentials = self.plugin.get_device_credentials(device.id, device_ip)
            if not credentials and device_groups:
                for group in device_groups:
                    try:
                        group_name = None
                        if isinstance(group, dict) and "name" in group:
                            group_name = group["name"]
                        elif hasattr(group, "name"):
                            group_name = group.name
                        elif hasattr(group, "get_name"):
                            group_name = group.get_name()
                        else:
                            group_name = str(group)
                        group_credentials = self.plugin.get_group_credentials(group_name)
                        if group_credentials:
                            logger.debug(
                                f"Using credentials from '{group_name}' for device: {device_name}"
                            )
                            credentials = group_credentials
                            break
                    except Exception as e:
                        logger.error(f"Error getting credentials for group: {e}")

            if not credentials and device_ip:
                parts = device_ip.split(".")
                if len(parts) == 4:
                    subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
                    subnet_credentials = self.plugin.get_subnet_credentials(subnet)
                    if subnet_credentials:
                        logger.debug(
                            f"Using subnet credentials from '{subnet}' for device: {device_name}"
                        )
                        credentials = subnet_credentials

            if not credentials:
                logger.warning(f"No credentials found for device: {device_name} ({device_ip})")
                for command in self.commands:
                    result = {
                        "success": False,
                        "output": f"Command: {command['command']}\n\nNo credentials available for this device.",
                    }
                    self.command_complete.emit(device, command, result, self.command_set)
                    completed_commands += 1
                    self.command_progress.emit(completed_commands, total_commands)
                continue

            logger.debug(
                f"Using credentials for device: {device_name}, type: {credentials.get('connection_type', 'ssh')}"
            )

            # Reuse a single session per device for speed (connect once, execute all commands, disconnect).
            connection_type = (credentials.get("connection_type", "ssh") or "ssh").lower()
            session = None
            try:
                if connection_type == "ssh":
                    session = SSHClient(
                        host=device_ip,
                        username=credentials.get("username"),
                        password=credentials.get("password", ""),
                        enable_password=credentials.get("enable_password", ""),
                        use_shell=True,
                    )
                    session.connect()
                    if credentials.get("enable_password"):
                        session.enable()
                    # Disable paging where supported to speed multi-command runs.
                    for pager_cmd in ("terminal length 0", "terminal pager 0", "no page"):
                        try:
                            session.execute(pager_cmd)
                        except Exception:
                            pass
                elif connection_type == "telnet":
                    session = TelnetClient(
                        host=device_ip,
                        username=credentials.get("username"),
                        password=credentials.get("password", ""),
                        enable_password=credentials.get("enable_password", ""),
                    )
                    session.connect()
                    if credentials.get("enable_password"):
                        session.enable()
                    for pager_cmd in ("terminal length 0", "terminal pager 0", "no page"):
                        try:
                            session.execute(pager_cmd)
                        except Exception:
                            pass
                else:
                    raise Exception(f"Unsupported connection type: {connection_type}")

                for command in self.commands:
                    if self.stop_requested:
                        logger.debug("Stop requested - halting command execution")
                        break

                    expanded_command = expand_command_for_device(command["command"], device)
                    logger.debug(f"Executing command: {expanded_command!r} on device: {device_name}")
                    self.command_started.emit(device, command)
                    try:
                        output = session.execute(expanded_command)
                        result = {"success": True, "output": output}
                    except Exception as e:
                        logger.error(
                            f"Error executing command: {expanded_command!r} on device: {device_name}: {e}"
                        )
                        result = {
                            "success": False,
                            "output": f"Command: {expanded_command}\n\nError: {str(e)}",
                        }

                    self.command_complete.emit(device, command, result, self.command_set)

                    if result.get("success"):
                        command_set_id = ""
                        if self.command_set:
                            command_set_id = (
                                f"{self.command_set.device_type}_{self.command_set.firmware_version}"
                            )
                        command_id = f"{command_set_id}_{command['alias']}".replace(" ", "_")
                        self.plugin.add_command_output(
                            device.id, command_id, result["output"], expanded_command
                        )
                    completed_commands += 1
                    self.command_progress.emit(completed_commands, total_commands)

            except Exception as e:
                # Connection failure: mark remaining commands for this device as failed.
                logger.error(f"Session setup/connection failed for {device_name} ({device_ip}): {e}")
                for command in self.commands:
                    if self.stop_requested:
                        break
                    expanded_command = expand_command_for_device(command["command"], device)
                    result = {
                        "success": False,
                        "output": f"Command: {expanded_command}\n\nConnection error: {str(e)}",
                    }
                    self.command_complete.emit(device, command, result, self.command_set)
                    completed_commands += 1
                    self.command_progress.emit(completed_commands, total_commands)
            finally:
                try:
                    if session:
                        session.disconnect()
                except Exception:
                    pass

        logger.debug("All commands completed")
        self.all_commands_complete.emit(self.command_set)

    def stop(self):
        """Stop the worker."""
        self.stop_requested = True
