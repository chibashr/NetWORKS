#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Credential Store for Command Manager plugin.

Credentials are stored per workspace for security: group and subnet credentials
live under the current workspace directory and are reloaded when the workspace
changes. Device credentials remain in device properties (saved with the workspace).
"""

import os
import json
import ipaddress
from pathlib import Path
from loguru import logger

from .encryption import encrypt_password, decrypt_password


class CredentialStore:
    """Secure storage for network device credentials, scoped per workspace."""

    def __init__(self, get_workspace_credentials_dir, device_manager=None):
        """Initialize the credential store.

        Args:
            get_workspace_credentials_dir: Callable() -> Path that returns the
                current workspace's credentials base directory (e.g. workspaces/<name>/plugins/command_manager/credentials).
                Group and subnet credentials are stored under this path and reloaded when it changes.
            device_manager: Optional device manager reference for device credentials and migration.
        """
        self._get_workspace_credentials_dir = get_workspace_credentials_dir
        self.device_manager = device_manager
        self._current_workspace_base = None

        # In-memory caches for the current workspace (group/subnet only)
        self.device_credentials = {}  # Legacy fallback only
        self.group_credentials = {}
        self.subnet_credentials = {}

        self._ensure_workspace_loaded()

    def set_device_manager(self, device_manager):
        """Set the device manager reference."""
        self.device_manager = device_manager
        logger.debug("CredentialStore: Device manager reference set")

    def _ensure_workspace_loaded(self):
        """Load group/subnet credentials for the current workspace if the workspace has changed."""
        base = Path(self._get_workspace_credentials_dir())
        if base != self._current_workspace_base:
            self._current_workspace_base = base
            (base / "groups").mkdir(parents=True, exist_ok=True)
            (base / "subnets").mkdir(parents=True, exist_ok=True)
            (base / "devices").mkdir(parents=True, exist_ok=True)
            self._load_device_credentials()
            self._load_group_credentials()
            self._load_subnet_credentials()
            logger.debug(f"CredentialStore: Loaded credentials for workspace base {base}")

    def _get_group_creds_dir(self):
        """Return the group credentials directory for the current workspace."""
        self._ensure_workspace_loaded()
        d = self._current_workspace_base / "groups"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _get_subnet_creds_dir(self):
        """Return the subnet credentials directory for the current workspace."""
        self._ensure_workspace_loaded()
        d = self._current_workspace_base / "subnets"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _get_device_creds_dir(self):
        """Return the legacy device credentials directory for the current workspace."""
        self._ensure_workspace_loaded()
        d = self._current_workspace_base / "devices"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _load_credentials(self):
        """Load device (legacy), group and subnet credentials from disk for current workspace."""
        self._load_device_credentials()
        self._load_group_credentials()
        self._load_subnet_credentials()
        
    def _load_device_credentials(self):
        """
        Load device credentials from disk for backward compatibility.
        Note: These will be migrated to device properties when accessed.
        """
        self.device_credentials = {}
        device_creds_dir = self._get_device_creds_dir()
        if not device_creds_dir.exists():
            return

        for file_path in device_creds_dir.glob("*.json"):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    
                # Extract device ID from filename
                device_id = file_path.stem
                
                # Store credentials
                self.device_credentials[device_id] = data
                
                # Decrypt password (if needed)
                if "password" in data and data["password"]:
                    try:
                        data["password"] = decrypt_password(data["password"])
                    except:
                        # If decryption fails, keep encrypted
                        pass
                
                # Decrypt enable password (if needed)
                if "enable_password" in data and data["enable_password"]:
                    try:
                        data["enable_password"] = decrypt_password(data["enable_password"])
                    except:
                        # If decryption fails, keep encrypted
                        pass
                
                # Migrate to device properties if device manager is available
                if self.device_manager:
                    device = self.device_manager.get_device(device_id)
                    if device:
                        self._migrate_credentials_to_device(device, data)
                        # Delete the file after migration
                        try:
                            file_path.unlink()
                            logger.debug(f"Migrated and deleted credential file for device {device_id}")
                        except Exception as e:
                            logger.error(f"Error deleting credential file for device {device_id}: {e}")
                
            except Exception as e:
                logger.error(f"Error loading device credentials from {file_path}: {e}")
    
    def _migrate_credentials_to_device(self, device, credentials):
        """Migrate credentials from file to device properties"""
        encrypted_creds = credentials.copy()
        
        # Encrypt the password fields for storage
        if "password" in encrypted_creds and encrypted_creds["password"]:
            encrypted_creds["password"] = encrypt_password(encrypted_creds["password"])
        
        if "enable_password" in encrypted_creds and encrypted_creds["enable_password"]:
            encrypted_creds["enable_password"] = encrypt_password(encrypted_creds["enable_password"])
        
        # Store the encrypted credentials as a property on the device
        device.set_property("credentials", encrypted_creds)
        logger.debug(f"Migrated credentials to device property for device {device.id}")
    
    def _load_group_credentials(self):
        """Load group credentials from disk for the current workspace."""
        self.group_credentials = {}
        group_creds_dir = self._current_workspace_base / "groups" if self._current_workspace_base else None
        if not group_creds_dir or not group_creds_dir.exists():
            return

        for file_path in group_creds_dir.glob("*.json"):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    
                # Extract group name from filename
                group_name = file_path.stem
                
                # Store credentials
                self.group_credentials[group_name] = data
                
                # Decrypt password (if needed)
                if "password" in data and data["password"]:
                    try:
                        data["password"] = decrypt_password(data["password"])
                    except:
                        # If decryption fails, keep encrypted
                        pass
                
                # Decrypt enable password (if needed)
                if "enable_password" in data and data["enable_password"]:
                    try:
                        data["enable_password"] = decrypt_password(data["enable_password"])
                    except:
                        # If decryption fails, keep encrypted
                        pass
                
            except Exception as e:
                logger.error(f"Error loading group credentials from {file_path}: {e}")
    
    def _load_subnet_credentials(self):
        """Load subnet credentials from disk for the current workspace."""
        self.subnet_credentials = {}
        subnet_creds_dir = self._current_workspace_base / "subnets" if self._current_workspace_base else None
        if not subnet_creds_dir or not subnet_creds_dir.exists():
            return

        for file_path in subnet_creds_dir.glob("*.json"):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    
                # Extract subnet from filename (filename might be sanitized with _ instead of /)
                subnet = file_path.stem.replace("_", "/")
                
                # Store credentials
                self.subnet_credentials[subnet] = data
                
                # Decrypt password (if needed)
                if "password" in data and data["password"]:
                    try:
                        data["password"] = decrypt_password(data["password"])
                    except:
                        # If decryption fails, keep encrypted
                        pass
                
                # Decrypt enable password (if needed)
                if "enable_password" in data and data["enable_password"]:
                    try:
                        data["enable_password"] = decrypt_password(data["enable_password"])
                    except:
                        # If decryption fails, keep encrypted
                        pass
                
            except Exception as e:
                logger.error(f"Error loading subnet credentials from {file_path}: {e}")
    
    def save_credentials(self):
        """Save all credentials to disk"""
        # We don't need to save device credentials to files anymore
        # as they are now stored in device properties
        self._save_group_credentials()
        self._save_subnet_credentials()
    
    def _get_credentials_from_device(self, device):
        """Get credentials from device properties"""
        if not device:
            return {}
            
        # Get the credentials property
        encrypted_creds = device.get_property("credentials", {})
        if not encrypted_creds:
            return {}
            
        # Make a copy of the credentials to avoid modifying the original
        creds = encrypted_creds.copy()
        
        # Decrypt password
        if "password" in creds and creds["password"]:
            try:
                creds["password"] = decrypt_password(creds["password"])
            except Exception as e:
                logger.error(f"Error decrypting password for device {device.id}: {e}")
                creds["password"] = ""
        
        # Decrypt enable password
        if "enable_password" in creds and creds["enable_password"]:
            try:
                creds["enable_password"] = decrypt_password(creds["enable_password"])
            except Exception as e:
                logger.error(f"Error decrypting enable password for device {device.id}: {e}")
                creds["enable_password"] = ""
        
        return creds

    def _save_group_credentials(self):
        """Save group credentials to disk for the current workspace."""
        group_creds_dir = self._get_group_creds_dir()
        for group_name, creds in self.group_credentials.items():
            try:
                creds_copy = creds.copy()
                if "password" in creds_copy and creds_copy["password"]:
                    creds_copy["password"] = encrypt_password(creds_copy["password"])
                if "enable_password" in creds_copy and creds_copy["enable_password"]:
                    creds_copy["enable_password"] = encrypt_password(creds_copy["enable_password"])
                file_path = group_creds_dir / f"{group_name}.json"
                with open(file_path, "w") as f:
                    json.dump(creds_copy, f, indent=2)
                
                logger.debug(f"Saved group credentials to {file_path}")
            
            except Exception as e:
                logger.error(f"Error saving credentials for group {group_name}: {e}")
                logger.exception("Exception details:")
    
    def _save_subnet_credentials(self):
        """Save subnet credentials to disk for the current workspace."""
        subnet_creds_dir = self._get_subnet_creds_dir()
        for subnet, creds in self.subnet_credentials.items():
            try:
                creds_copy = creds.copy()
                if "password" in creds_copy and creds_copy["password"]:
                    creds_copy["password"] = encrypt_password(creds_copy["password"])
                if "enable_password" in creds_copy and creds_copy["enable_password"]:
                    creds_copy["enable_password"] = encrypt_password(creds_copy["enable_password"])
                safe_subnet = subnet.replace("/", "_")
                file_path = subnet_creds_dir / f"{safe_subnet}.json"
                with open(file_path, "w") as f:
                    json.dump(creds_copy, f, indent=2)
                
                logger.debug(f"Saved subnet credentials to {file_path}")
            
            except Exception as e:
                logger.error(f"Error saving credentials for subnet {subnet}: {e}")
                logger.exception("Exception details:")
    
    def get_device_credentials(self, device_id, device_ip=None, groups=None):
        """Get credentials for a device
        
        Note: This method no longer falls back to group or subnet credentials.
        This allows the plugin to control the credential hierarchy itself.
        
        Args:
            device_id: The device ID (string) or Device object
            device_ip: The device IP (not used for direct device credentials)
            groups: Device group names (not used for direct device credentials)
            
        Returns:
            dict: Credentials or None if not found
        """
        # Handle Device objects passed as device_id
        if hasattr(device_id, 'id'):
            device_id = device_id.id
            logger.debug(f"Extracted device ID from Device object: {device_id}")
        
        logger.debug(f"Getting credentials for device {device_id}")
        
        # First, check if the device exists and has credentials in its properties
        if self.device_manager:
            device = self.device_manager.get_device(device_id)
            if device:
                creds = self._get_credentials_from_device(device)
                if creds:
                    logger.debug(f"Found credentials in device properties for device {device_id}")
                    return creds
            else:
                logger.debug(f"Device {device_id} not found in device manager")
        else:
            logger.debug("Device manager not available")
        
        # For backward compatibility, check the legacy storage
        if device_id in self.device_credentials:
            logger.debug(f"Found credentials in legacy storage for device {device_id}")
            return self.device_credentials[device_id]
        
        # No credentials found for this device
        logger.debug(f"No credentials found for device {device_id}")
        return None
    
    def get_group_credentials(self, group_name):
        """Get credentials for a device group (current workspace only).
        
        Args:
            group_name: The group name
            
        Returns:
            dict: Credentials or None if not found
        """
        self._ensure_workspace_loaded()
        logger.debug(f"Getting credentials for group {group_name}")
        if group_name in self.group_credentials:
            return self.group_credentials[group_name]
        
        return None
    
    def get_subnet_credentials(self, subnet):
        """Get credentials for a subnet (current workspace only).
        
        Args:
            subnet: The subnet in CIDR notation
            
        Returns:
            dict: Credentials or None if not found
        """
        self._ensure_workspace_loaded()
        logger.debug(f"Getting credentials for subnet {subnet}")
        # First, try exact match
        if subnet in self.subnet_credentials:
            return self.subnet_credentials[subnet]
        
        # Try to match by IP network
        try:
            target_network = ipaddress.ip_network(subnet, strict=False)
            
            for network_str, creds in self.subnet_credentials.items():
                try:
                    network = ipaddress.ip_network(network_str, strict=False)
                    # Check if networks match (same network address and prefix)
                    if (network.network_address == target_network.network_address and 
                        network.prefixlen == target_network.prefixlen):
                        return creds
                except ValueError:
                    continue
        except ValueError:
            # Invalid subnet format
            pass
        
        return None
    
    def set_device_credentials(self, device_id, credentials):
        """Set credentials for a device
        
        Args:
            device_id: The device ID (string) or Device object
            credentials: Dictionary containing credentials
        """
        # Handle Device objects passed as device_id
        if hasattr(device_id, 'id'):
            device_id = device_id.id
            logger.debug(f"Extracted device ID from Device object: {device_id}")
        
        logger.debug(f"Setting credentials for device {device_id} (type: {type(device_id)})")
        
        # Check if we have a device manager reference
        if not self.device_manager:
            logger.warning(f"Device manager not available, falling back to legacy storage for device {device_id}")
        else:
            device = self.device_manager.get_device(device_id)
            if device:
                # Create a copy of the credentials
                creds_copy = credentials.copy()
                
                # Encrypt password before saving
                if "password" in creds_copy and creds_copy["password"]:
                    creds_copy["password"] = encrypt_password(creds_copy["password"])
                
                # Encrypt enable password before saving
                if "enable_password" in creds_copy and creds_copy["enable_password"]:
                    creds_copy["enable_password"] = encrypt_password(creds_copy["enable_password"])
                
                # Save to device property
                # This will emit device.changed signal which triggers workspace autosave
                device.set_property("credentials", creds_copy)
                logger.info(f"Saved credentials to device properties for device {device_id} ({device.get_property('alias', 'Unknown')})")
                
                # Note: Device credentials are persisted via workspace save (triggered by device.changed signal)
                # The workspace autosave mechanism will save device properties including credentials
                
                return True
            else:
                logger.warning(f"Device {device_id} not found in device manager, falling back to legacy storage")
        
        # Fall back to legacy file-based storage
        logger.warning(f"Falling back to legacy credential storage for device {device_id}")
        self.device_credentials[device_id] = credentials
        
        # Save to file for backward compatibility
        try:
            # Create a copy of the credentials
            creds_copy = credentials.copy()
            
            # Encrypt password before saving
            if "password" in creds_copy and creds_copy["password"]:
                creds_copy["password"] = encrypt_password(creds_copy["password"])
            
            # Encrypt enable password before saving
            if "enable_password" in creds_copy and creds_copy["enable_password"]:
                creds_copy["enable_password"] = encrypt_password(creds_copy["enable_password"])
            
            # Save to file
            file_path = self.device_creds_dir / f"{device_id}.json"
            with open(file_path, "w") as f:
                json.dump(creds_copy, f, indent=2)
                
            return True
        except Exception as e:
            logger.error(f"Error saving credentials for device {device_id}: {e}")
            return False
    
    def delete_device_credentials(self, device_id):
        """Delete credentials for a device"""
        success = False
        
        # Delete from device property if available
        if self.device_manager:
            device = self.device_manager.get_device(device_id)
            if device and device.get_property("credentials", None) is not None:
                device.set_property("credentials", None)
                logger.debug(f"Deleted credentials from device properties for device {device_id}")
                success = True
        
        # Also delete from legacy storage if it exists
        if device_id in self.device_credentials:
            del self.device_credentials[device_id]
            success = True
            
            # Remove file if it exists
            file_path = self._get_device_creds_dir() / f"{device_id}.json"
            if file_path.exists():
                try:
                    file_path.unlink()
                    logger.debug(f"Deleted credential file for device {device_id}")
                except Exception as e:
                    logger.error(f"Error deleting credential file for device {device_id}: {e}")
        
        return success
    
    def set_group_credentials(self, group_name, credentials):
        """Set credentials for a group (current workspace only)."""
        self._ensure_workspace_loaded()
        self.group_credentials[group_name] = credentials.copy()
        
        # Save to disk (encrypted)
        self._save_group_credentials()
        
        logger.info(f"Saved credentials for group '{group_name}'")
        return True
    
    def delete_group_credentials(self, group_name):
        """Delete credentials for a group (current workspace only)."""
        self._ensure_workspace_loaded()
        if group_name in self.group_credentials:
            del self.group_credentials[group_name]
            file_path = self._get_group_creds_dir() / f"{group_name}.json"
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception as e:
                    logger.error(f"Error deleting credential file for group {group_name}: {e}")
            
            return True
        
        return False
    
    def set_subnet_credentials(self, subnet, credentials):
        """Set credentials for a subnet"""
        # Validate subnet
        try:
            ipaddress.ip_network(subnet, strict=False)
        except ValueError:
            logger.error(f"Invalid subnet: {subnet}")
            return False
            
        # Store credentials in memory (decrypted for use)
        self.subnet_credentials[subnet] = credentials.copy()
        
        # Save to disk (encrypted)
        self._save_subnet_credentials()
        
        logger.info(f"Saved credentials for subnet '{subnet}'")
        return True
    
    def delete_subnet_credentials(self, subnet):
        """Delete credentials for a subnet (current workspace only)."""
        self._ensure_workspace_loaded()
        if subnet in self.subnet_credentials:
            del self.subnet_credentials[subnet]
            safe_subnet = subnet.replace("/", "_")
            file_path = self._get_subnet_creds_dir() / f"{safe_subnet}.json"
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception as e:
                    logger.error(f"Error deleting credential file for subnet {subnet}: {e}")
            
            return True
        
        return False
    
    def get_all_device_credentials(self):
        """Get all device credentials"""
        # Combine legacy stored credentials with device property-based credentials
        result = self.device_credentials.copy()
        
        # Add credentials from device properties if device manager is available
        if self.device_manager:
            for device in self.device_manager.get_devices():
                creds = self._get_credentials_from_device(device)
                if creds:
                    result[device.id] = creds
        
        return result
    
    def get_all_group_credentials(self):
        """Get all group credentials"""
        return self.group_credentials
    
    def get_all_subnet_credentials(self):
        """Get all subnet credentials for the current workspace."""
        self._ensure_workspace_loaded()
        return self.subnet_credentials.copy() 