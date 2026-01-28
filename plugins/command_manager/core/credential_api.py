#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Credential API helpers for the Command Manager plugin.
Holds get/set/delete and device fallback logic; the plugin delegates to these.
"""

from loguru import logger


def get_all_device_credentials(plugin):
    """Get all device credentials."""
    return plugin.credential_store.get_all_device_credentials() if plugin.credential_store else {}


def get_all_group_credentials(plugin):
    """Get all group credentials."""
    return plugin.credential_store.get_all_group_credentials() if plugin.credential_store else {}


def get_all_subnet_credentials(plugin):
    """Get all subnet credentials."""
    return plugin.credential_store.get_all_subnet_credentials() if plugin.credential_store else {}


def get_device_credentials(plugin, device_id, device_ip=None, groups=None):
    """Get credentials for a device with fallback to group/subnet.

    Args:
        plugin: CommandManagerPlugin instance
        device_id: The device ID
        device_ip: The device IP address (for subnet matching)
        groups: Optional list of group names the device belongs to

    Returns:
        dict: Credentials dictionary or None if not found
    """
    logger.debug(f"Getting credentials for device {device_id}")

    if not plugin.credential_store:
        logger.error("Credential store is not available")
        return None

    # 1. First try device-specific credentials
    device_credentials = plugin.credential_store.get_device_credentials(device_id)
    if device_credentials:
        logger.debug(f"Found device-specific credentials for {device_id}")
        return device_credentials

    # 2. If no device credentials, try group credentials
    if plugin.device_manager:
        try:
            device_groups = plugin.device_manager.get_device_groups_for_device(device_id)

            if device_groups:
                logger.debug(f"Found {len(device_groups)} groups for device {device_id}")

                for group in device_groups:
                    group_name = group.name if hasattr(group, "name") else str(group)
                    group_credentials = plugin.credential_store.get_group_credentials(group_name)
                    if group_credentials:
                        logger.debug(
                            f"Using credentials from group '{group_name}' for device {device_id}"
                        )
                        return group_credentials
        except Exception as e:
            logger.error(f"Error getting group credentials for device {device_id}: {e}")

    # 3. If still no credentials, try subnet matching
    if device_ip:
        try:
            parts = device_ip.split(".")
            if len(parts) == 4:
                subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
                subnet_credentials = plugin.credential_store.get_subnet_credentials(subnet)
                if subnet_credentials:
                    logger.debug(
                        f"Using credentials from subnet {subnet} for device {device_id}"
                    )
                    return subnet_credentials
        except Exception as e:
            logger.error(f"Error getting subnet credentials: {e}")

    logger.debug(f"No credentials found for device {device_id}")
    return None


def get_group_credentials(plugin, group_name):
    """Get credentials for a device group."""
    logger.debug(f"Getting credentials for group {group_name}")

    if not plugin.credential_store:
        logger.error("Credential store is not available")
        return None

    return plugin.credential_store.get_group_credentials(group_name)


def get_subnet_credentials(plugin, subnet):
    """Get credentials for a subnet (CIDR notation)."""
    logger.debug(f"Getting credentials for subnet {subnet}")

    if not plugin.credential_store:
        logger.error("Credential store is not available")
        return None

    return plugin.credential_store.get_subnet_credentials(subnet)


def set_device_credentials(plugin, device_id, credentials):
    """Set credentials for a device."""
    if getattr(plugin, "credential_store", None) and plugin.credential_store:
        return plugin.credential_store.set_device_credentials(device_id, credentials)


def set_group_credentials(plugin, group_name, credentials):
    """Set credentials for a group."""
    if getattr(plugin, "credential_store", None) and plugin.credential_store:
        return plugin.credential_store.set_group_credentials(group_name, credentials)


def set_subnet_credentials(plugin, subnet, credentials):
    """Set credentials for a subnet."""
    if getattr(plugin, "credential_store", None) and plugin.credential_store:
        return plugin.credential_store.set_subnet_credentials(subnet, credentials)


def delete_device_credentials(plugin, device_id):
    """Delete credentials for a device."""
    if getattr(plugin, "credential_store", None) and plugin.credential_store:
        return plugin.credential_store.delete_device_credentials(device_id)


def delete_group_credentials(plugin, group_name):
    """Delete credentials for a group."""
    if getattr(plugin, "credential_store", None) and plugin.credential_store:
        return plugin.credential_store.delete_group_credentials(group_name)


def delete_subnet_credentials(plugin, subnet):
    """Delete credentials for a subnet."""
    if getattr(plugin, "credential_store", None) and plugin.credential_store:
        return plugin.credential_store.delete_subnet_credentials(subnet)
