#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Load/save of command outputs (file paths, JSON read/write, legacy migration).
OutputHandler calls this for load/save and gets the canonical
{device_id: {command_id: {timestamp: output}}} structure.
"""

import json
from pathlib import Path
from loguru import logger


def _workspace_devices_dir(plugin):
    """Resolve workspace devices path from device manager (current workspace)."""
    dm = getattr(plugin, "device_manager", None)
    if dm:
        ws = getattr(dm, "current_workspace", "default")
        base = Path(getattr(dm, "workspaces_dir", "config/workspaces"))
        return base / ws / "devices"
    return Path("config/workspaces/default/devices")


def load_command_outputs(plugin):
    """Load command outputs from disk. Returns dict {device_id: {command_id: {timestamp: data}}}."""
    logger.debug("Loading command outputs from disk")
    outputs = {}
    output_dir = getattr(plugin, "output_dir", None)
    if not output_dir:
        return outputs
    output_dir = Path(output_dir)
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    device_dirs = [d for d in output_dir.iterdir() if d.is_dir()]
    for device_dir in device_dirs:
        device_id = device_dir.name
        output_file = device_dir / "command_outputs.json"
        if output_file.exists():
            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    device_outputs = json.load(f)
                    outputs[device_id] = device_outputs
                logger.debug(f"Loaded command outputs for device {device_id} from {output_file}")
            except Exception as e:
                logger.error(f"Error loading command outputs for device {device_id}: {e}")
                logger.exception("Exception details:")

    workspace_device_dir = _workspace_devices_dir(plugin)
    if workspace_device_dir.exists():
        for device_dir in workspace_device_dir.iterdir():
            if device_dir.is_dir():
                device_id = device_dir.name
                commands_dir = device_dir / "commands"
                if commands_dir.exists():
                    output_file = commands_dir / "command_outputs.json"
                    if output_file.exists() and device_id not in outputs:
                        try:
                            with open(output_file, "r", encoding="utf-8") as f:
                                device_outputs = json.load(f)
                                outputs[device_id] = device_outputs
                            logger.debug(f"Loaded command outputs for device {device_id} from workspace: {output_file}")
                        except Exception as e:
                            logger.error(f"Error loading command outputs for device {device_id} from workspace: {e}")
                            logger.exception("Exception details:")

    if not outputs:
        legacy_file = output_dir / "command_outputs.json"
        if legacy_file.exists():
            try:
                with open(legacy_file, "r", encoding="utf-8") as f:
                    outputs = json.load(f)
                logger.debug(f"Loaded command outputs from legacy file {legacy_file}")
                save_command_outputs(plugin, outputs)
            except Exception as e:
                logger.error(f"Error loading legacy command outputs: {e}")
                logger.exception("Exception details:")

    device_count = len(outputs)
    command_count = sum(len(cmd) for cmd in outputs.values())
    output_count = sum(
        len(ts) for cmd in outputs.values() for ts in cmd.values()
    )
    logger.info(
        f"Loaded {output_count} command outputs for {command_count} commands across {device_count} devices"
    )
    return outputs


def save_command_outputs(plugin, outputs):
    """Save command outputs to disk. outputs: {device_id: {command_id: {timestamp: data}}}."""
    logger.debug("Saving command outputs to disk")
    output_dir = getattr(plugin, "output_dir", None)
    if not output_dir:
        return
    output_dir = Path(output_dir)
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
    if not outputs:
        logger.debug("No command outputs to save")
        return

    for device_id, commands in outputs.items():
        try:
            device_dir = output_dir / device_id
            device_dir.mkdir(exist_ok=True)
            output_file = device_dir / "command_outputs.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(commands, f, indent=2)
            logger.debug(f"Saved command outputs for device {device_id} to {output_file}")

            try:
                workspace_device_dir = _workspace_devices_dir(plugin) / device_id
                if workspace_device_dir.exists():
                    commands_dir = workspace_device_dir / "commands"
                    commands_dir.mkdir(exist_ok=True)
                    workspace_output_file = commands_dir / "command_outputs.json"
                    with open(workspace_output_file, "w", encoding="utf-8") as f:
                        json.dump(commands, f, indent=2)
                    logger.debug(f"Saved command outputs to workspace: {workspace_output_file}")
            except Exception as e:
                logger.error(f"Error saving command outputs to workspace for device {device_id}: {e}")
                logger.exception("Exception details:")
        except Exception as e:
            logger.error(f"Error saving command outputs for device {device_id}: {e}")
            logger.exception("Exception details:")

    try:
        legacy_file = output_dir / "command_outputs.json"
        with open(legacy_file, "w", encoding="utf-8") as f:
            json.dump(outputs, f, indent=2)
        logger.debug(f"Saved command outputs to {legacy_file}")
    except Exception as e:
        logger.error(f"Error saving command outputs: {e}")
        logger.exception("Exception details:")
