#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Network Scanner Plugin for NetWORKS

This plugin adds network scanning capabilities to NetWORKS using Nmap.
It allows scanning network ranges and adding discovered devices to the
device inventory.
"""

from loguru import logger
import sys
import os
import time
import datetime
import ipaddress
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple

# Try to import nmap with error handling
try:
    import nmap
    HAS_NMAP = True
except ImportError as e:
    logger.error(f"Could not import python-nmap: {e}")
    HAS_NMAP = False

# Try to import psutil for interface detection (preferred, wheels available on most platforms)
try:
    import psutil
    HAS_PSUTIL = True
except ImportError as e:
    logger.error(f"Could not import psutil for interface detection: {e}")
    HAS_PSUTIL = False

from PySide6.QtWidgets import (
    QApplication, QLabel, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QDockWidget,
    QPushButton, QTabWidget, QScrollArea, QTreeWidget, QTreeWidgetItem,
    QGridLayout, QFormLayout, QGroupBox, QCheckBox, QComboBox,
    QSplitter, QProgressBar, QMessageBox, QLineEdit, QTableWidget,
    QTableWidgetItem, QDialog, QDialogButtonBox, QMenu, QFileDialog,
    QRadioButton, QInputDialog, QHeaderView, QSizePolicy, QListWidget,
    QListWidgetItem, QStyle, QSpinBox
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer, QThread, QObject
from PySide6.QtGui import QIcon, QAction, QFont, QColor, QIntValidator


def _split_range_into_chunks(network_range, max_hosts_per_chunk=32):
    """Split a network range into smaller chunks for incremental scanning.
    Returns a list of strings (chunk targets). Single-host or small ranges return [network_range].
    """
    import re
    target_text = (network_range or "").strip()
    if not target_text:
        return [network_range]
    try:
        if "/" in target_text:
            net = ipaddress.IPv4Network(target_text, strict=False)
            n = net.num_addresses
            if n <= max_hosts_per_chunk:
                return [network_range]
            # Split into /28 subnets (16 hosts each) or similar
            new_prefix = min(28, net.prefixlen + 4)  # aim for ~16–256 hosts per subnet
            while new_prefix < 31:
                subnets = list(net.subnets(new_prefix=new_prefix))
                if len(subnets) < 2:
                    new_prefix += 1
                    continue
                return [str(s) for s in subnets]
            return [network_range]
        targets = [t for t in re.split(r"[,\s]+", target_text) if t]
        if len(targets) <= 1:
            if len(targets) == 1 and "-" in targets[0]:
                start_s, end_s = targets[0].split("-", 1)
                start_s, end_s = start_s.strip(), end_s.strip()
                start_ip = ipaddress.IPv4Address(start_s)
                end_ip = ipaddress.IPv4Address(end_s)
                n = int(end_ip) - int(start_ip) + 1
                if n <= max_hosts_per_chunk:
                    return [network_range]
                out = []
                step = max_hosts_per_chunk
                for i in range(0, n, step):
                    a = ipaddress.IPv4Address(int(start_ip) + i)
                    b = ipaddress.IPv4Address(min(int(start_ip) + i + step - 1, int(end_ip)))
                    out.append(f"{a}-{b}")
                return out
            return [network_range]
        if len(targets) <= max_hosts_per_chunk:
            return [network_range]
        out = []
        for i in range(0, len(targets), max_hosts_per_chunk):
            out.append(",".join(targets[i : i + max_hosts_per_chunk]))
        return out
    except Exception:
        return [network_range]


# Import the plugin interface
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.core.plugin_interface import PluginInterface
from src.ui.plugin_ui_theme import mark_plugin_ui
from src.ui.material_icons import material_icon


# Safe action wrapper from sample plugin
def safe_action_wrapper(func):
    """Decorator to safely handle actions without crashing the application"""
    import functools
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            # Log the action start
            action_name = func.__name__
            logger.debug(f"Starting action: {action_name}")
            
            # Execute the action
            result = func(self, *args, **kwargs)
            logger.debug(f"Successfully completed action: {action_name}")
            return result
        except Exception as e:
            # Log the error
            logger.error(f"Error in action {func.__name__}: {e}", exc_info=True)
            
            # Try to log to the UI if possible
            try:
                if hasattr(self, 'log_message'):
                    self.log_message(f"Error performing action: {e}")
                
                # Try to show a status message
                if hasattr(self, 'main_window') and hasattr(self.main_window, 'statusBar'):
                    self.main_window.statusBar().showMessage(f"Error: {e}", 3000)
            except Exception as inner_e:
                # Absolute fallback to console logging
                logger.critical(f"Failed to handle error in UI: {inner_e}")
                
            # Return a safe value (None)
            return None
    return wrapper


class ScannerWorker(QObject):
    """Worker thread for network scanning"""
    
    # Signals
    progress = Signal(int, int)  # current, total
    device_found = Signal(dict)  # device data
    scan_complete = Signal(dict)  # scan results
    scan_error = Signal(str)  # error message
    
    def __init__(self, network_range, scan_type="quick", timeout=600,
                 use_sudo=False, custom_scan_args="", nmap_path=None):
        """Initialize the scanner worker. Scan behavior is defined by profile/scan-type arguments only."""
        super().__init__()
        self.network_range = network_range
        self.scan_type = scan_type
        self.timeout = timeout
        self.use_sudo = use_sudo
        self.custom_scan_args = custom_scan_args
        self.nmap_path = nmap_path
        self.is_running = False
        self.should_stop = False
        
        # Create scanner in the worker thread when run is called
        self.scanner = None
        
    def stop(self):
        """Stop the scan"""
        logger.debug("Request to stop scanner received")
        self.should_stop = True
        
    def run(self):
        """Run the network scan"""
        self.is_running = True
        
        try:
            # Initialize the scanner instance
            try:
                import nmap
                
                # If we have a specific nmap path and it's not in PATH, add it temporarily
                if self.nmap_path and os.path.exists(self.nmap_path):
                    nmap_dir = os.path.dirname(self.nmap_path)
                    current_path = os.environ.get("PATH", "")
                    
                    # Only modify PATH if nmap directory is not already in it
                    if nmap_dir not in current_path.split(os.pathsep):
                        # Temporarily add nmap directory to PATH
                        os.environ["PATH"] = nmap_dir + os.pathsep + current_path
                        logger.debug(f"Added nmap directory to PATH: {nmap_dir}")
                
                # Create the scanner
                self.scanner = nmap.PortScanner()
                
                # If python-nmap supports setting the path directly, try that too
                if self.nmap_path and hasattr(self.scanner, 'nmap_path'):
                    self.scanner.nmap_path = self.nmap_path
                    logger.debug(f"Set python-nmap path to: {self.nmap_path}")
                
                logger.debug(f"Created nmap scanner instance for {self.network_range}")
            except ImportError:
                logger.error("Failed to import python-nmap. Make sure it's installed.")
                self.scan_error.emit("Failed to import python-nmap. Make sure it's installed.")
                self.is_running = False
                return
            except Exception as e:
                logger.error(f"Error initializing nmap scanner: {e}")
                self.scan_error.emit(f"Error initializing scanner: {str(e)}")
                self.is_running = False
                return
            
            # Build the arguments string
            arguments = ""
            
            # Use profile arguments if provided
            if self.scan_type and self.scan_type != "custom":
                if self.scan_type == "quick":
                    arguments = "-sn -T4"  # Ping scan (no port scan)
                elif self.scan_type == "standard":
                    arguments = "-sn -F -O -T4"  # Fast scan with OS detection
                elif self.scan_type == "comprehensive":
                    arguments = "-sS -p 1-1000 -O -A -T4"  # SYN scan with OS and service detection
                elif self.scan_type == "stealth":
                    arguments = "-sS -T2"  # SYN scan with timing template 2 (slower)
                elif self.scan_type == "service":
                    arguments = "-sV -p 21,22,23,25,53,80,110,111,135,139,143,443,445,993,995,1723,3306,3389,5900,8080 -T4"
            
            # Add custom arguments if provided (profile/scan-type arguments define nmap behavior)
            if self.custom_scan_args:
                arguments += f" {self.custom_scan_args}"
                
            # Make sure we don't have duplicate arguments by splitting and rejoining
            # This prevents issues like having "-sn -T4 -sn -T4"
            arg_parts = arguments.split()
            unique_args = []
            seen_options = set()
            port_options = []  # Store all port options
            
            # First pass - collect all port options and other unique args
            for arg in arg_parts:
                if arg.startswith("-p"):
                    # Store port option separately
                    if len(arg) > 2:  # Format is "-pXXX"
                        port_options.append(arg[2:])  # Just the port numbers
                    elif arg == "-p" and len(arg_parts) > arg_parts.index(arg) + 1:
                        # Handle space-separated format like "-p 22,80"
                        next_idx = arg_parts.index(arg) + 1
                        next_arg = arg_parts[next_idx]
                        if not next_arg.startswith("-"):  # Ensure it's actually port numbers
                            port_options.append(next_arg)
                elif arg.startswith("-"):
                    # For other options, only add if we haven't seen them before
                    option_char = arg[1:].split(" ")[0]  # Extract the option character
                    if option_char not in seen_options:
                        seen_options.add(option_char)
                        unique_args.append(arg)
                else:
                    # For non-option arguments, always add
                    unique_args.append(arg)
            
            # Now add the consolidated port option if we collected any
            if port_options:
                # Merge all port specifications, removing duplicates
                all_ports = set()
                for ports in port_options:
                    # Split by commas, handle ranges like "1-1000"
                    for port_spec in ports.split(","):
                        all_ports.add(port_spec.strip())
                
                # Add consolidated port option
                unique_args.append(f"-p {','.join(sorted(all_ports))}")
                
            # Rebuild the arguments string
            arguments = " ".join(unique_args)
                
            # Log the scan command
            logger.info(f"Starting network scan of {self.network_range} with arguments: {arguments}")
            
            # Add verbose output if not already specified to provide more feedback
            if "-v" not in arguments:
                arguments += " -v"
                
            # Tracking variables
            scan_start_time = time.time()
            devices_found = 0
            last_progress_update = time.time()
            last_status_message = ""
            
            try:
                # Check if we should stop before even starting
                if self.should_stop:
                    logger.info("Scan stopped before starting")
                    self.is_running = False
                    return
                    
                # Provide initial progress feedback
                self.progress.emit(0, 100)  # We don't know total yet, use 100 as placeholder
                
                # Emit a message to show scan is starting
                self.device_found.emit({"status_update": "Initializing nmap scan..."})
                
                # Extract network range info to estimate host count
                host_count_estimate = 256
                try:
                    import ipaddress
                    import re
                    target_text = self.network_range.strip()
                    if "/" in target_text:  # CIDR notation
                        try:
                            network = ipaddress.IPv4Network(target_text, strict=False)
                            host_count_estimate = network.num_addresses
                        except Exception:
                            pass
                    else:
                        targets = [t for t in re.split(r"[,\s]+", target_text) if t]
                        if len(targets) > 1:
                            host_count_estimate = len(targets)
                        elif len(targets) == 1:
                            target = targets[0]
                            if "-" in target:
                                try:
                                    start, end = target.split("-", 1)
                                    if end.isdigit():
                                        parts = start.split(".")
                                        if len(parts) == 4:
                                            start_octet = int(parts[3])
                                            end_octet = int(end)
                                            if 0 <= start_octet <= end_octet <= 255:
                                                host_count_estimate = end_octet - start_octet + 1
                                    else:
                                        start_ip = ipaddress.IPv4Address(start)
                                        end_ip = ipaddress.IPv4Address(end)
                                        if int(end_ip) >= int(start_ip):
                                            host_count_estimate = int(end_ip) - int(start_ip) + 1
                                except Exception:
                                    pass
                            else:
                                host_count_estimate = 1
                except Exception:
                    pass

                # Warn if network is very large (more than /20 = 4096 hosts)
                # Large networks can cause nmap assertion failures
                if host_count_estimate > 4096:
                    logger.warning(f"Very large network range detected ({host_count_estimate} hosts). This may cause nmap issues.")
                    self.device_found.emit({
                        "status_update": f"Warning: Large network ({host_count_estimate} hosts). Scan may take a long time or fail..."
                    })
                else:
                    self.device_found.emit({"status_update": f"Preparing to scan {host_count_estimate} potential addresses..."})
                
                # Start the scan within a try/except block
                try:
                    # Use a reasonable timeout value
                    timeout_val = max(60, min(self.timeout, 900))  # Between 60 and 900 seconds
                    
                    # For large networks, use a more conservative timing template to avoid assertion failures
                    # Large networks can trigger nmap internal bugs with aggressive timing
                    # Check if timing template is already in arguments (from scan type)
                    has_timing = any(arg in arguments for arg in ["-T1", "-T2", "-T3", "-T4", "-T5"])
                    
                    if host_count_estimate > 1024:
                        # For large networks, replace T4 with T3 if present, or add T3 if not
                        if "-T4" in arguments or "-T5" in arguments:
                            # Replace aggressive timing with normal timing for large networks
                            arguments = arguments.replace("-T4", "-T3").replace("-T5", "-T3")
                            logger.debug("Replaced aggressive timing template with T3 for large network to avoid nmap assertion failures")
                        elif not has_timing:
                            arguments += " -T3"
                            logger.debug("Using T3 timing template for large network to avoid nmap assertion failures")
                    elif not has_timing:
                        # For smaller networks, T4 is fine if not already specified
                        arguments += " -T4"
                        
                    # For large networks, add host timeout to prevent individual hosts from hanging
                    # This helps avoid nmap assertion failures
                    if host_count_estimate > 512 and "--host-timeout" not in arguments:
                        arguments += " --host-timeout 30s"
                        logger.debug("Added --host-timeout for large network scan")
                    
                    logger.debug(f"Starting nmap scan (estimated {host_count_estimate} hosts) with arguments: {arguments}")
                    
                    # Let the user know we're starting
                    self.device_found.emit({"status_update": f"Starting nmap scan of {host_count_estimate} hosts..."})
                    
                    chunks = _split_range_into_chunks(self.network_range, max_hosts_per_chunk=32)
                    total_hosts_acc = 0
                    
                    for chunk_idx, chunk in enumerate(chunks):
                        if self.should_stop:
                            break
                        if len(chunks) > 1:
                            self.device_found.emit({
                                "status_update": f"Scanning {chunk} ({chunk_idx + 1}/{len(chunks)})..."
                            })
                        else:
                            self.device_found.emit({"status_update": f"Scanning {chunk}..."})
                        
                        # Timer only for single-chunk (long) scans
                        update_timer = None
                        if len(chunks) == 1:
                            def provide_status_update():
                                if not self.is_running or self.should_stop:
                                    return
                                elapsed = time.time() - scan_start_time
                                status = f"Scanning in progress... ({int(elapsed)}s elapsed)"
                                progress_percent = min(95, int((elapsed / timeout_val) * 100))
                                self.progress.emit(progress_percent, 100)
                                nonlocal last_status_message
                                if status != last_status_message:
                                    self.device_found.emit({"status_update": status})
                                    last_status_message = status
                                nonlocal update_timer
                                if self.is_running and not self.should_stop:
                                    update_timer = threading.Timer(1.0, provide_status_update)
                                    update_timer.daemon = True
                                    update_timer.start()
                            update_timer = threading.Timer(1.0, provide_status_update)
                            update_timer.daemon = True
                            update_timer.start()
                        
                        self.scanner.scan(hosts=chunk, arguments=arguments, sudo=self.use_sudo)
                        
                        if len(chunks) == 1 and update_timer:
                            update_timer.cancel()
                        
                        # Process this chunk's results (devices appear incrementally)
                        all_hosts = self.scanner.all_hosts()
                        total_hosts_acc += len(all_hosts)
                        total_hosts = len(all_hosts)
                        if total_hosts > 0 and len(chunks) > 1:
                            self.device_found.emit({
                                "status_update": f"Processing {total_hosts} hosts from {chunk}..."
                            })
                        elif total_hosts > 0 and len(chunks) == 1:
                            self.device_found.emit({
                                "status_update": f"Scan complete - processing {total_hosts} discovered hosts..."
                            })
                        self.progress.emit(0, total_hosts)
                        for i, host in enumerate(all_hosts):
                            if self.should_stop:
                                break
                            self.progress.emit(i + 1, total_hosts)
                            current_time = time.time()
                            if current_time - last_progress_update > 0.5:
                                self.device_found.emit({
                                    "status_update": f"Processing host {i+1} of {total_hosts}: {host}"
                                })
                                last_progress_update = current_time
                            try:
                                if 'status' not in self.scanner[host] or not self.scanner[host]['status'] or self.scanner[host]['status'].get('state') != 'up':
                                    continue
                                host_data = {}
                                host_data["ip_address"] = host
                                host_data["scan_source"] = "nmap"
                                host_data["scan_type"] = self.scan_type
                                if 'status' in self.scanner[host] and self.scanner[host]['status']:
                                    host_data["status"] = self.scanner[host]['status'].get('state', 'unknown')
                                    host_data["status_reason"] = self.scanner[host]['status'].get('reason', '')
                                try:
                                    if 'hostnames' in self.scanner[host] and self.scanner[host]['hostnames']:
                                        hostnames = self.scanner[host]['hostnames']
                                        if isinstance(hostnames, list) and hostnames:
                                            for hostname_entry in hostnames:
                                                if 'name' in hostname_entry and hostname_entry['name']:
                                                    host_data["hostname"] = hostname_entry['name']
                                                    break
                                except Exception:
                                    pass
                                try:
                                    if 'addresses' in self.scanner[host]:
                                        addresses = self.scanner[host]['addresses']
                                        if 'ipv4' in addresses:
                                            host_data["ipv4_address"] = addresses['ipv4']
                                        if 'ipv6' in addresses:
                                            host_data["ipv6_address"] = addresses['ipv6']
                                        if 'mac' in addresses:
                                            host_data["mac_address"] = addresses['mac']
                                    if 'vendor' in self.scanner[host] and self.scanner[host]['vendor'] and host_data.get("mac_address") in self.scanner[host]['vendor']:
                                        host_data["mac_vendor"] = self.scanner[host]['vendor'][host_data["mac_address"]]
                                except Exception:
                                    pass
                                try:
                                    if 'osmatch' in self.scanner[host] and self.scanner[host]['osmatch']:
                                        os_matches = self.scanner[host]['osmatch']
                                        if isinstance(os_matches, list) and os_matches:
                                            best = max(os_matches, key=lambda x: int(x.get('accuracy', 0) or 0))
                                            if 'name' in best:
                                                host_data["os"] = best['name']
                                except Exception:
                                    pass
                                try:
                                    if 'tcp' in self.scanner[host]:
                                        tcp_ports = [int(p) for p, d in self.scanner[host]['tcp'].items() if d.get('state') == 'open']
                                        tcp_services = {int(p): d.get('name', '') for p, d in self.scanner[host]['tcp'].items() if d.get('state') == 'open' and d.get('name')}
                                        if tcp_ports:
                                            host_data["open_tcp_ports"] = sorted(tcp_ports)
                                        if tcp_services:
                                            host_data["tcp_services"] = tcp_services
                                    if 'udp' in self.scanner[host]:
                                        udp_ports = [int(p) for p, d in self.scanner[host]['udp'].items() if d.get('state') == 'open']
                                        udp_services = {int(p): d.get('name', '') for p, d in self.scanner[host]['udp'].items() if d.get('state') == 'open' and d.get('name')}
                                        if udp_ports:
                                            host_data["open_udp_ports"] = sorted(udp_ports)
                                        if udp_services:
                                            host_data["udp_services"] = udp_services
                                    open_ports = host_data.get("open_tcp_ports", []) + host_data.get("open_udp_ports", [])
                                    if open_ports:
                                        host_data["open_ports"] = sorted(open_ports)
                                    host_data["services"] = {**host_data.get("tcp_services", {}), **host_data.get("udp_services", {})}
                                except Exception:
                                    pass
                                host_data["last_scan_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                host_data["tags"] = ["scanned", "nmap"]
                                host_data["alias"] = host_data.get("hostname") or (f"{host_data.get('mac_vendor', '')} Device" if host_data.get("mac_vendor") else f"Device at {host}")
                                if host_data.get("ip_address"):
                                    self.device_found.emit(host_data)
                                    devices_found += 1
                            except Exception as e:
                                logger.error(f"Error processing host {host}: {e}", exc_info=True)
                    
                    # After all chunks, emit scan complete
                    scan_time = time.time() - scan_start_time
                    scan_results = {
                        "network_range": self.network_range,
                        "scan_type": self.scan_type,
                        "total_hosts": total_hosts_acc,
                        "devices_found": devices_found,
                        "scan_time": scan_time,
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    self.scan_complete.emit(scan_results)
                        
                except Exception as scan_error:
                    logger.error(f"Error during nmap scan: {scan_error}")
                    
                    # Stop the update timer if still running
                    if update_timer:
                        try:
                            update_timer.cancel()
                        except Exception:
                            pass
                    
                    # Check for specific error types and provide helpful messages
                    error_msg = str(scan_error).lower()
                    error_str = str(scan_error)
                    
                    # Check for nmap assertion failures (internal nmap bugs)
                    if "assertion failed" in error_msg or "htn.toclock_running" in error_msg:
                        logger.warning("Nmap internal assertion failure detected. This may be due to a large network range or nmap version issue.")
                        # Try to provide helpful guidance
                        helpful_msg = (
                            "Nmap encountered an internal error during the scan.\n\n"
                            "This can happen with:\n"
                            "  • Very large network ranges (try scanning smaller subnets)\n"
                            "  • Certain nmap versions (try updating nmap)\n"
                            "  • Network timeout issues\n\n"
                            "Suggestions:\n"
                            "  • Try scanning a smaller range (e.g., /24 instead of /22)\n"
                            "  • Use a ping-only scan type for faster discovery\n"
                            "  • Update nmap to the latest version\n"
                            "  • Try increasing the scan timeout in settings"
                        )
                        self.scan_error.emit(helpful_msg)
                    elif "timed out" in error_msg or "timeout" in error_msg:
                        self.scan_error.emit(
                            "Scan timed out. Try using a smaller network range or increasing the timeout value in settings."
                        )
                    elif "permission denied" in error_msg or "requires root" in error_msg:
                        self.scan_error.emit(
                            "Scan requires elevated permissions. Enable 'Use Elevated Permissions' in scan settings or run NetWORKS as administrator."
                        )
                    else:
                        # Generic error - provide the error message but also suggest solutions
                        generic_msg = (
                            f"Scan error: {error_str}\n\n"
                            "Troubleshooting:\n"
                            "  • Try scanning a smaller network range\n"
                            "  • Check that nmap is properly installed\n"
                            "  • Try using a ping-only scan type\n"
                            "  • Ensure you have network connectivity"
                        )
                        self.scan_error.emit(generic_msg)
                    
                    self.is_running = False
                    return
                
            except Exception as e:
                logger.error(f"Unhandled scan error: {e}", exc_info=True)
                self.scan_error.emit(str(e))
                
        finally:
            # Cleanup to prevent memory leaks
            try:
                logger.debug("Cleaning up scanner resources")
                # Clear the scanner reference and explicitly help garbage collection
                if hasattr(self, 'scanner') and self.scanner:
                    self.scanner = None
                
                # Force a garbage collection cycle to clean up any lingering objects
                import gc
                gc.collect()
            except Exception as cleanup_error:
                logger.error(f"Error during scanner cleanup: {cleanup_error}")
                
            self.is_running = False
            logger.debug("Scanner worker finished")


class NetworkScannerPlugin(PluginInterface):
    """
    Network Scanner Plugin for NetWORKS
    
    This plugin provides network scanning capabilities for discovering
    and adding devices to the NetWORKS inventory.
    """
    
    # Custom signals
    scan_started = Signal(str)  # network_range
    scan_progress = Signal(int, int)  # current, total
    scan_device_found = Signal(object)  # device
    scan_completed = Signal(dict)  # results_dict
    scan_error = Signal(str)  # error_message
    
    def __init__(self):
        """Initialize the plugin"""
        super().__init__()
        self.name = "Network Scanner"
        self.version = "10.5"
        self.description = "Scan network segments for devices and add them to NetWORKS"
        self.author = "NetWORKS Team"
        
        # Internal state
        self._connected_signals = set()  # Track connected signals for safe disconnection
        self._scanner_thread = None
        self._scanner_worker = None
        self._is_scanning = False
        self._scan_results = {}
        self._scan_log = []
        self._batch_scan_queue = []
        self._batch_scan_total = 0
        self._batch_scan_index = 0
        self._batch_scan_current = None
        self._batch_scan_active = False
        self._batch_scan_slots = []  # for parallel batch: list of {"thread", "worker", "target", "index"}
        
        # Plugin settings
        self.settings = {
            "scan_profiles": {
                "name": "Scan Profiles",
                "description": "Customizable scan profiles with predefined settings",
                "type": "json",
                "default": {
                    "quick": {"name": "Quick Scan", "description": "Fast ping scan to discover hosts (minimal network impact)", "arguments": "-sn -T4", "timeout": 120},
                    "standard": {"name": "Standard Scan", "description": "Balanced scan with basic port scanning and OS detection", "arguments": "-sn -F -O -T4", "timeout": 300},
                    "comprehensive": {"name": "Comprehensive Scan", "description": "In-depth scan with full port scanning and OS fingerprinting", "arguments": "-sS -p 1-1000 -O -A -T4", "timeout": 600},
                    "stealth": {"name": "Stealth Scan", "description": "Quiet TCP SYN scan with minimal footprint", "arguments": "-sS -T2", "timeout": 480},
                    "service": {"name": "Service Detection", "description": "Focused on detecting services on common ports", "arguments": "-sV -p 21,22,23,25,53,80,110,111,135,139,143,443,445,993,995,1723,3306,3389,5900,8080 -T4", "timeout": 480}
                },
                "value": {
                    "quick": {"name": "Quick Scan", "description": "Fast ping scan to discover hosts (minimal network impact)", "arguments": "-sn -T4", "timeout": 120},
                    "standard": {"name": "Standard Scan", "description": "Balanced scan with basic port scanning and OS detection", "arguments": "-sn -F -O -T4", "timeout": 300},
                    "comprehensive": {"name": "Comprehensive Scan", "description": "In-depth scan with full port scanning and OS fingerprinting", "arguments": "-sS -p 1-1000 -O -A -T4", "timeout": 600},
                    "stealth": {"name": "Stealth Scan", "description": "Quiet TCP SYN scan with minimal footprint", "arguments": "-sS -T2", "timeout": 480},
                    "service": {"name": "Service Detection", "description": "Focused on detecting services on common ports", "arguments": "-sV -p 21,22,23,25,53,80,110,111,135,139,143,443,445,993,995,1723,3306,3389,5900,8080 -T4", "timeout": 480}
                }
            },
            "scan_type": {
                "name": "Default Scan Type",
                "description": "The default scan type to use",
                "type": "choice",
                "default": "quick",
                "value": "quick",
                "choices": ["quick", "standard", "comprehensive", "stealth", "service"]
            },
            "preferred_interface": {
                "name": "Preferred Interface",
                "description": "The preferred network interface to use for scanning",
                "type": "choice",
                "default": "",
                "value": "",
                "choices": []  # Will be populated during initialization
            },
            "scan_timeout": {
                "name": "Default Scan Timeout",
                "description": "Default timeout in seconds for scan operations",
                "type": "int",
                "default": 600,
                "value": 600
            },
            "use_sudo": {
                "name": "Use Elevated Permissions",
                "description": "Run scans with elevated permissions (improves accuracy but requires admin/sudo)",
                "type": "bool",
                "default": False,
                "value": False
            },
            "custom_scan_args": {
                "name": "Custom Scan Arguments",
                "description": "Advanced: Custom nmap arguments (use with caution)",
                "type": "string",
                "default": "",
                "value": ""
            },
            "auto_tag": {
                "name": "Auto Tag",
                "description": "Automatically tag discovered devices",
                "type": "bool",
                "default": True,
                "value": True
            },
            "batch_scan_threads": {
                "name": "Batch scan threads",
                "description": "Number of devices to scan in parallel during batch scans (1 = sequential)",
                "type": "int",
                "default": 1,
                "value": 1
            }
        }
        
        # Create UI components
        self._create_actions()
        self._create_widgets()
        
    def initialize(self, app, plugin_info):
        """Initialize the plugin"""
        try:
            logger.info(f"Initializing {self.name} v{self.version}")
            
            # Store app reference and set up plugin interface
            self.app = app
            self.device_manager = app.device_manager
            self.main_window = app.main_window
            self.config = app.config
            self.plugin_info = plugin_info
            
            # Initialize nmap availability flag
            self.nmap_available = False
            
            # Check if nmap module was successfully imported
            if not HAS_NMAP:
                warning_msg = (
                    "The python-nmap module is not available. Network scanning features will be disabled.\n\n"
                    "To enable scanning, install python-nmap using:\n"
                    "pip install python-nmap"
                )
                logger.warning(warning_msg)
                if hasattr(self, "main_window") and self.main_window:
                    QMessageBox.warning(
                        self.main_window,
                        "Network Scanner Warning",
                        warning_msg
                    )
                
            # Check if nmap is available
            try:
                # Check if the nmap executable is available and get its path
                nmap_path = self._check_nmap_executable()
                
                if not nmap_path:
                    warning_msg = (
                        "The nmap executable was not found on your system.\n\n"
                        "Network scanning features will be disabled until nmap is installed.\n\n"
                        "To install nmap:\n"
                        "  • Windows: Download from https://nmap.org/download.html\n"
                        "    (Typical installation: C:\\Program Files\\Nmap\\nmap.exe)\n"
                        "  • macOS: brew install nmap\n"
                        "  • Linux: sudo apt install nmap (or equivalent)\n\n"
                        "After installing, make sure nmap is accessible (either in your system PATH\n"
                        "or in a standard installation location) and restart NetWORKS."
                    )
                    logger.warning(warning_msg)
                    if hasattr(self, "main_window") and self.main_window:
                        QMessageBox.warning(
                            self.main_window,
                            "Network Scanner Warning",
                            warning_msg
                        )
                    # Don't raise - allow plugin to load but disable scanning
                    self.nmap_available = False
                    return
                
                # Store the nmap path for later use
                self.nmap_path = nmap_path
                logger.info(f"Nmap executable found at: {nmap_path}")
                
                # Ensure we have an absolute path and normalize it
                if not os.path.isabs(nmap_path):
                    nmap_path = os.path.abspath(nmap_path)
                    self.nmap_path = nmap_path
                    logger.debug(f"Converted to absolute path: {nmap_path}")
                
                # Normalize the path (handle Windows path separators, etc.)
                nmap_path = os.path.normpath(nmap_path)
                self.nmap_path = nmap_path
                
                # Verify the path still exists
                if not os.path.exists(nmap_path):
                    warning_msg = (
                        f"Nmap was found at {nmap_path} but the file no longer exists.\n\n"
                        "Network scanning features will be disabled.\n\n"
                        "Please reinstall nmap or check the installation."
                    )
                    logger.warning(warning_msg)
                    if hasattr(self, "main_window") and self.main_window:
                        QMessageBox.warning(
                            self.main_window,
                            "Network Scanner Warning",
                            warning_msg
                        )
                    self.nmap_available = False
                    return
                
                # Log additional diagnostic information and add to PATH if needed
                import platform
                nmap_dir = os.path.dirname(nmap_path)
                # Normalize the directory path as well
                nmap_dir = os.path.normpath(nmap_dir)
                current_path = os.environ.get("PATH", "")
                
                # CRITICAL: Add nmap directory to PATH BEFORE creating PortScanner
                # python-nmap looks for nmap in PATH when it initializes
                # Normalize PATH entries for comparison
                path_entries = [os.path.normpath(p) for p in current_path.split(os.pathsep) if p.strip()]
                
                if nmap_dir and nmap_dir not in path_entries:
                    logger.info(f"Nmap directory ({nmap_dir}) is not in system PATH - adding it now")
                    # Add to the beginning of PATH so it's found first
                    os.environ["PATH"] = nmap_dir + os.pathsep + current_path
                    logger.debug(f"Updated PATH to include nmap directory. New PATH starts with: {nmap_dir}")
                    # Verify it was added
                    updated_path = os.environ.get("PATH", "")
                    if nmap_dir in updated_path:
                        logger.debug("Successfully verified nmap directory is now in PATH")
                    else:
                        logger.warning(f"Warning: nmap directory may not have been added to PATH correctly")
                else:
                    logger.info(f"Nmap directory ({nmap_dir}) is already in system PATH")
                
                # Now try to create a scanner - nmap should be in PATH now
                # This is especially important on Windows where nmap might not be in PATH
                logger.debug("Creating nmap.PortScanner() instance...")
                try:
                    test_scanner = nmap.PortScanner()
                    logger.debug("nmap.PortScanner() created successfully")
                    
                    # Try to set the nmap path directly if python-nmap supports it
                    if hasattr(test_scanner, 'nmap_path'):
                        test_scanner.nmap_path = nmap_path
                        logger.debug(f"Set python-nmap path attribute to: {nmap_path}")
                except Exception as port_scanner_error:
                    # If PortScanner creation fails, it might be because python-nmap
                    # checked PATH before we modified it. Try to work around this.
                    error_msg = str(port_scanner_error).lower()
                    if 'not found' in error_msg or 'path' in error_msg:
                        logger.warning(f"PortScanner creation failed: {port_scanner_error}")
                        logger.info("Attempting to work around PATH issue...")
                        
                        # Try creating PortScanner again - PATH should be updated now
                        # Sometimes python-nmap caches PATH, so we need to force it
                        try:
                            test_scanner = nmap.PortScanner()
                            logger.info("Successfully created PortScanner on retry")
                        except Exception as retry_error:
                            # If it still fails, re-raise the original error
                            logger.error(f"PortScanner creation failed even after PATH update: {retry_error}")
                            raise port_scanner_error
                    else:
                        # Some other error, re-raise it
                        raise
                
                # Actually test if python-nmap can use nmap by trying to get version
                try:
                    # Try a simple operation to verify python-nmap can use nmap
                    # We'll use the scanner's command_line method or try a minimal scan
                    # But first, let's just verify the scanner was created successfully
                    logger.debug("Nmap Python module initialized successfully")
                    
                    # Try to verify python-nmap can actually execute nmap
                    # This is a more reliable test than just checking if the file exists
                    test_result = self._test_python_nmap_works(nmap_path)
                    if not test_result:
                        warning_msg = (
                            f"Nmap was found at {nmap_path}, but python-nmap cannot execute it.\n\n"
                            "This may be due to:\n"
                            "  • Permission issues\n"
                            "  • Missing dependencies\n"
                            "  • Corrupted nmap installation\n\n"
                            "Try reinstalling nmap or check the logs for more details."
                        )
                        logger.warning(warning_msg)
                        if hasattr(self, "main_window") and self.main_window:
                            QMessageBox.warning(
                                self.main_window,
                                "Network Scanner Warning",
                                warning_msg
                            )
                        self.nmap_available = False
                        return
                    
                    logger.info("Nmap is available and ready to use")
                    self.nmap_available = True
                    
                except Exception as test_error:
                    logger.error(f"Failed to verify python-nmap can use nmap: {test_error}")
                    warning_msg = (
                        f"Nmap was found but cannot be used by python-nmap: {str(test_error)}\n\n"
                        "Network scanning features will be disabled.\n\n"
                        "Try reinstalling nmap or check the logs for more details."
                    )
                    logger.warning(warning_msg)
                    if hasattr(self, "main_window") and self.main_window:
                        QMessageBox.warning(
                            self.main_window,
                            "Network Scanner Warning",
                            warning_msg
                        )
                    self.nmap_available = False
                    return
                    
            except Exception as e:
                # Provide more helpful error message
                error_str = str(e)
                nmap_path_info = ""
                if hasattr(self, 'nmap_path') and self.nmap_path:
                    nmap_path_info = f"\n\nNmap was found at: {self.nmap_path}\n"
                    nmap_dir = os.path.dirname(self.nmap_path)
                    current_path = os.environ.get("PATH", "")
                    if nmap_dir not in current_path.split(os.pathsep):
                        nmap_path_info += f"However, the nmap directory ({nmap_dir}) is not in PATH.\n"
                        nmap_path_info += "The plugin attempted to add it, but python-nmap may have already initialized.\n"
                        nmap_path_info += "Try restarting NetWORKS after ensuring nmap is installed."
                
                warning_msg = (
                    f"Nmap initialization failed: {error_str}{nmap_path_info}\n\n"
                    "Network scanning features will be disabled.\n\n"
                    "To fix this:\n"
                    "1. Install the nmap executable (see https://nmap.org/download.html)\n"
                    "2. Make sure nmap is in your system PATH, or install it in a standard location:\n"
                    "   • Windows: C:\\Program Files\\Nmap\\nmap.exe\n"
                    "3. Restart NetWORKS"
                )
                logger.warning(warning_msg)
                logger.debug(f"Current PATH: {os.environ.get('PATH', '')}")
                if hasattr(self, 'nmap_path'):
                    logger.debug(f"Found nmap at: {self.nmap_path}")
                self.nmap_available = False
                if hasattr(self, "main_window") and self.main_window:
                    QMessageBox.warning(
                        self.main_window,
                        "Network Scanner Warning",
                        warning_msg
                    )
            
            # Update network interfaces
            self._update_interface_choices()
            
            # Update the interface dropdown if it exists already
            if hasattr(self, "interface_combo") and self.interface_combo is not None:
                self.interface_combo.clear()
                self.interface_combo.addItems(self.settings["preferred_interface"]["choices"])
                if self.settings["preferred_interface"]["value"] in self.settings["preferred_interface"]["choices"]:
                    self.interface_combo.setCurrentText(self.settings["preferred_interface"]["value"])
                # Set a default network range based on the selected interface
                selected_if_text = self.interface_combo.currentText()
                if selected_if_text and selected_if_text != "Any (default)" and hasattr(self, "network_range_edit"):
                    self._update_network_range_from_interface(0)  # 0 is dummy index

            # Refresh group choices if available
            if hasattr(self, "group_combo") and self.group_combo is not None:
                self._refresh_group_choices()
                self._update_group_scan_ui_state()
            
            # Initialize threading system
            self._initialize_scanner()
            
            # We're going to defer UI setup a bit to allow the main window to fully initialize
            QTimer.singleShot(300, self._setup_device_context_menu)
            
            # Connect to application signals
            QTimer.singleShot(500, self._connect_signals)
            
            # Mark plugin as initialized
            self._initialized = True
            
            logger.info(f"{self.name} initialization complete")
            return True
        except Exception as e:
            error_msg = f"Plugin initialization failed: {e}"
            logger.error(error_msg, exc_info=True)
            # Try to show a message box if we have a main window
            try:
                if hasattr(self, "main_window") and self.main_window:
                    QMessageBox.critical(
                        self.main_window,
                        f"{self.name} Initialization Failed",
                        f"The plugin could not be initialized.\n\nError: {str(e)}"
                    )
            except Exception:
                pass  # If we can't show a message box, just continue
                
            # Re-raise the exception to signal failure
            raise
        
    def _connect_to_signal(self, signal, slot, signal_name):
        """Connect to a signal and track the connection"""
        if signal and slot:
            try:
                signal.connect(slot)
                self._connected_signals.add((signal, slot, signal_name))
                logger.debug(f"Connected to signal: {signal_name}")
                return True
            except Exception as e:
                logger.error(f"Error connecting to signal {signal_name}: {e}")
                return False
        return False
    
    def _connect_signals(self):
        """Connect to application signals"""
        # Connect to device manager signals
        self._connect_to_signal(
            self.device_manager.device_added, 
            self.on_device_added,
            "device_added"
        )
        
        self._connect_to_signal(
            self.device_manager.device_removed,
            self.on_device_removed,
            "device_removed"
        )
        
        self._connect_to_signal(
            self.device_manager.device_changed,
            self.on_device_changed,
            "device_changed"
        )

        self._connect_to_signal(
            self.device_manager.group_added,
            self._refresh_group_choices,
            "group_added"
        )
        
        self._connect_to_signal(
            self.device_manager.group_removed,
            self._refresh_group_choices,
            "group_removed"
        )
        
        self._connect_to_signal(
            self.device_manager.group_changed,
            self._refresh_group_choices,
            "group_changed"
        )
        
    def cleanup(self):
        """Clean up the plugin"""
        logger.info(f"Cleaning up {self.name}")
        
        # Stop any running scan first
        self.stop_scan()
        
        # Safe disconnection function
        def safe_disconnect(signal, handler=None, signal_name=""):
            """Safely disconnect a signal handler"""
            if not signal:
                logger.debug(f"Signal object is None for {signal_name}, skipping disconnect")
                return False
                
            try:
                if handler:
                    # Try with handler
                    signal.disconnect(handler)
                else:
                    # Try to disconnect all connections
                    try:
                        signal.disconnect()
                    except TypeError:
                        # If disconnect() fails, the signal might require a handler
                        pass
                return True
            except Exception as e:
                # This is expected sometimes due to how Qt handles signals
                logger.debug(f"Non-critical: Failed to disconnect {signal_name}: {e}")
                return False
        
        # Disconnect all tracked signals
        for signal, slot, signal_name in list(self._connected_signals):
            safe_disconnect(signal, slot, signal_name)
            
        # Clear the tracked signals
        self._connected_signals.clear()
        
        # Clean up any running scan threads
        self._cleanup_previous_scan()
        
        # Null out references that might cause reference cycles
        self.app = None
        self.device_manager = None
        self.main_window = None
        self.config = None
                
        logger.info(f"{self.name} cleanup complete")
        
    def _create_actions(self):
        """Create plugin actions"""
        self.scan_action = QAction("Scan Network")
        self.scan_action.triggered.connect(self.on_scan_action)
        
        self.scan_selected_action = QAction("Scan from Selected Device")
        self.scan_selected_action.triggered.connect(self.on_scan_selected_action)
        
        # Add a scan type manager action for toolbar
        self.scan_type_manager_action = QAction("Scan Type Manager")
        self.scan_type_manager_action.setToolTip("Manage scan profiles and types")
        self.scan_type_manager_action.triggered.connect(self.on_scan_type_manager_action)
        if self.main_window:
            self.scan_action.setIcon(material_icon("refresh", self.main_window, QStyle.SP_BrowserReload))
            self.scan_selected_action.setIcon(material_icon("play_arrow", self.main_window, QStyle.SP_ArrowRight))
            self.scan_type_manager_action.setIcon(material_icon("tune", self.main_window, QStyle.SP_FileDialogDetailedView))
        
    def _create_widgets(self):
        """Create plugin widgets"""
        # Main widget
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(8, 8, 8, 8)  # Add proper margins
        self.main_layout.setSpacing(10)  # Increase spacing between main sections
        
        # Create a top section for controls
        top_section = QWidget()
        top_layout = QVBoxLayout(top_section)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)
        
        # Single control group with simplified layout
        self.control_group = QGroupBox("Network Scan")
        control_layout = QVBoxLayout(self.control_group)
        control_layout.setContentsMargins(10, 15, 10, 10)
        control_layout.setSpacing(10)
        
        # Network interface selection
        interface_layout = QHBoxLayout()
        interface_layout.setSpacing(8)
        interface_layout.addWidget(QLabel("Interface:"))
        
        self.interface_combo = QComboBox()
        self.interface_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # First make sure we have interface choices
        if not self.settings["preferred_interface"]["choices"]:
            self._update_interface_choices()
            
        self.interface_combo.addItems(self.settings["preferred_interface"]["choices"])
        current_interface = self.settings["preferred_interface"]["value"]
        if current_interface and current_interface in self.settings["preferred_interface"]["choices"]:
            self.interface_combo.setCurrentText(current_interface)
            
        self.refresh_interfaces_button = QPushButton("Refresh")
        self.refresh_interfaces_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.refresh_interfaces_button.setToolTip("Refresh network interface list")
        self.refresh_interfaces_button.clicked.connect(self._update_interface_choices_and_refresh_ui)
        interface_layout.addWidget(self.interface_combo, 1)
        interface_layout.addWidget(self.refresh_interfaces_button)
        control_layout.addLayout(interface_layout)
        
        # Scan target - single dropdown (Interface Subnet, Custom Range, Selected Devices when applicable)
        target_layout = QHBoxLayout()
        target_layout.setSpacing(8)
        target_layout.addWidget(QLabel("Target:"))
        
        self.target_combo = QComboBox()
        self.target_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.target_combo.addItem("Interface Subnet", "interface")
        self.target_combo.addItem("Custom Range", "custom")
        # "Selected Devices (N)" added/updated by _update_selected_devices_ui when devices are selected
        target_layout.addWidget(self.target_combo, 1)
        control_layout.addLayout(target_layout)
        
        # Selected devices info label
        self.selected_devices_label = QLabel("No devices selected")
        self.selected_devices_label.setStyleSheet("color: gray; font-style: italic;")
        self.selected_devices_label.setVisible(False)
        control_layout.addWidget(self.selected_devices_label)
        
        # Network range input
        range_layout = QHBoxLayout()
        range_layout.setSpacing(8)
        range_layout.addWidget(QLabel("Range:"))
        
        self.network_range_edit = QLineEdit()
        self.network_range_edit.setPlaceholderText("e.g., 192.168.1.0/24 or 10.0.0.1-10.0.0.254")
        self.network_range_edit.setEnabled(False)  # Disabled by default (interface subnet selected)
        range_layout.addWidget(self.network_range_edit, 1)
        control_layout.addLayout(range_layout)
        
        # Drive enable/visibility from target dropdown
        def update_target_ui_state():
            target = self.target_combo.currentData() if self.target_combo.currentData() is not None else "interface"
            self.network_range_edit.setEnabled(target == "custom")
            self.selected_devices_label.setVisible(target == "devices")
            
        self.target_combo.currentIndexChanged.connect(update_target_ui_state)
        
        # Initial UI state
        update_target_ui_state()
        
        # Initial update of selected devices UI
        # The on_device_selected method will be called by the plugin manager when devices are selected
        QTimer.singleShot(100, self._update_selected_devices_ui)
        
        # Connect interface change to update network range
        self.interface_combo.currentIndexChanged.connect(self._update_network_range_from_interface)
        
        # Initialize network range from currently selected interface
        self._update_network_range_from_interface(self.interface_combo.currentIndex())
        
        # Scan type
        scan_type_layout = QHBoxLayout()
        scan_type_layout.setSpacing(8)
        scan_type_layout.addWidget(QLabel("Scan Type:"))
        
        self.scan_type_combo = QComboBox()
        self.scan_type_combo.addItems(self.settings["scan_type"]["choices"])
        self.scan_type_combo.setCurrentText(self.settings["scan_type"]["value"])
        scan_type_layout.addWidget(self.scan_type_combo, 1)
        
        self.scan_type_manager_button = QPushButton("Manage")
        self.scan_type_manager_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.scan_type_manager_button.setToolTip("Manage scan profiles and types")
        self.scan_type_manager_button.clicked.connect(self.on_scan_type_manager_action)
        scan_type_layout.addWidget(self.scan_type_manager_button)
        control_layout.addLayout(scan_type_layout)
        
        # Scan buttons: one Start/Stop button (shows "Stop" when scanning) plus Advanced
        button_grid = QGridLayout()
        button_grid.setSpacing(4)
        button_grid.setHorizontalSpacing(4)
        button_grid.setVerticalSpacing(4)
        
        self.scan_button = QPushButton("Start Scan")
        self.scan_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.scan_button.clicked.connect(self.on_scan_stop_button_clicked)
        self.scan_button.setToolTip("Start a scan, or stop the current scan")
        button_grid.addWidget(self.scan_button, 0, 0)
        
        self.advanced_scan_button = QPushButton("Advanced...")
        self.advanced_scan_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.advanced_scan_button.clicked.connect(self.on_advanced_scan_button_clicked)
        self.advanced_scan_button.setToolTip("Open the advanced scan configuration dialog")
        button_grid.addWidget(self.advanced_scan_button, 0, 1)
        
        control_layout.addLayout(button_grid)
        
        # Add control group to top section
        top_layout.addWidget(self.control_group)
        
        # Progress section
        progress_widget = QWidget()
        self.progress_layout = QVBoxLayout(progress_widget)
        self.progress_layout.setContentsMargins(4, 4, 4, 4)
        self.progress_layout.setSpacing(4)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.progress_layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_layout.addWidget(self.progress_bar)
        
        # Add progress widget to top section
        top_layout.addWidget(progress_widget)
        
        # Results section
        self.results_group = QGroupBox("Scan Results")
        self.results_layout = QVBoxLayout(self.results_group)
        self.results_layout.setContentsMargins(8, 12, 8, 8)  # Add internal margins for better readability
        
        # Results list
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_layout.addWidget(self.results_text)
        
        # Create a splitter to allow resizing between controls and results
        self.main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.addWidget(top_section)
        self.main_splitter.addWidget(self.results_group)
        self.main_splitter.setStretchFactor(0, 0)  # Don't stretch the top section
        self.main_splitter.setStretchFactor(1, 1)  # Let the results section take extra space
        self.main_splitter.setSizes([200, 400])  # Set initial sizes
        
        # Add the splitter to the main layout
        self.main_layout.addWidget(self.main_splitter)
        
    def _initialize_scanner(self):
        """Initialize the scanner thread and worker"""
        # We don't create the worker or thread here
        # These will be created on-demand when a scan is started
        self._scanner_thread = None
        self._scanner_worker = None
        
        # Just note that we're ready for scanning
        logger.debug("Scanner thread system initialized")
        
    def _setup_device_context_menu(self):
        """Set up context menu integration with device table"""
        # Defer context menu setup to a point when UI components are fully initialized
        # Use a QTimer to schedule this after the UI is fully loaded
        QTimer.singleShot(500, self._register_context_menu_actions)
        
    def _register_context_menu_actions(self):
        """Register context menu actions for device table"""
        try:
            # First try to get the device table directly from the main window
            if not hasattr(self.main_window, 'device_table'):
                logger.warning("Device table not found, cannot register context menu actions")
                return
                
            device_table = self.main_window.device_table
            
            # Check if table has register_context_menu_action method
            if not hasattr(device_table, 'register_context_menu_action'):
                logger.warning("Device table does not support context menu action registration")
                return
                
            # Register our scan actions with the device table
            device_table.register_context_menu_action(
                "Scan Network...", 
                self._on_scan_network_action, 
                priority=151
            )
            
            device_table.register_context_menu_action(
                "Scan Interface Subnet...", 
                self._on_scan_subnet_action, 
                priority=152
            )
            
            device_table.register_context_menu_action(
                "Scan Device's Network...", 
                self._on_scan_from_device_action, 
                priority=153
            )
            
            device_table.register_context_menu_action(
                "Rescan Selected Device(s)...", 
                self._on_rescan_device_action, 
                priority=154
            )
            
            logger.debug("Successfully registered context menu actions")
            
        except Exception as e:
            logger.error(f"Error registering context menu actions: {e}", exc_info=True)
            
    def log_message(self, message):
        """Add a message to the scan log"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self._scan_log.append(log_entry)
        
        if hasattr(self, "results_text"):
            self.results_text.append(log_entry)
            
        logger.info(message)
        
    def get_dock_widgets(self):
        """Get plugin dock widgets"""
        # Panel title should match the plugin name for easy identification
        dock = QDockWidget("Network Scanner")
        dock.setWidget(self.main_widget)
        dock.setObjectName("NetworkScannerDock")
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        # Set minimum width to prevent controls from being too cramped
        self.main_widget.setMinimumWidth(300)
        
        # Return a list of tuples: (widget_name, widget, area)
        return [("Network Scanner", dock, Qt.RightDockWidgetArea)]
        
    def get_toolbar_actions(self):
        """Get actions for the toolbar"""
        return [self.scan_action, self.scan_type_manager_action]
        
    def get_menu_actions(self):
        """Get plugin menu actions"""
        return {"Network": [self.scan_action, self.scan_selected_action, self.scan_type_manager_action]}
        
    def scan_network(self, network_range, scan_type="quick"):
        """
        Start a network scan of the specified range
        
        Args:
            network_range: The network range to scan (e.g., 192.168.1.0/24)
            scan_type: The type of scan to perform (quick, standard, comprehensive, etc.)
            
        Returns:
            bool: True if scan started successfully, False otherwise
        """
        # Check if nmap is available
        if not hasattr(self, 'nmap_available') or not self.nmap_available:
            logger.error("Cannot start scan: nmap is not available")
            if hasattr(self, "main_window") and self.main_window:
                QMessageBox.warning(
                    self.main_window,
                    "Nmap Not Available",
                    "Nmap is not available. Network scanning features are disabled.\n\n"
                    "To enable scanning:\n"
                    "1. Install the nmap executable (see https://nmap.org/download.html)\n"
                    "2. Make sure nmap is in your system PATH\n"
                    "3. Restart NetWORKS"
                )
            return False
            
        # Check if already scanning
        if self._is_scanning:
            logger.warning("Scan already in progress")
            return False
            
        # Clean up any previous scan
        self._cleanup_previous_scan()
        
        # Update scan type in settings
        self.settings["scan_type"]["value"] = scan_type
        
        # Get scan profile settings if available
        scan_profiles = self.settings["scan_profiles"]["value"]
        custom_args = self.settings["custom_scan_args"]["value"]
        use_sudo = self.settings["use_sudo"]["value"]
        timeout = self.settings["scan_timeout"]["value"]
        
        # If the scan type has a profile, use those settings unless overridden
        if scan_type in scan_profiles:
            profile = scan_profiles[scan_type]
            
            # Only use profile settings if not explicitly set by the user
            if not custom_args:
                custom_args = profile.get("arguments", "")
            
            if timeout == self.settings["scan_timeout"]["default"]:
                timeout = profile.get("timeout", timeout)
        
        # Create a new worker thread
        try:
            # Log start of scan
            logger.info(f"Starting {scan_type} scan of {network_range}")
            
            # Create a new thread
            self._scanner_thread = QThread()
            
            # Create a worker and move it to the thread
            nmap_path = getattr(self, 'nmap_path', None)
            self._scanner_worker = ScannerWorker(
                network_range=network_range,
                scan_type=scan_type,
                timeout=timeout,
                use_sudo=use_sudo,
                custom_scan_args=custom_args,
                nmap_path=nmap_path
            )
            self._scanner_worker.moveToThread(self._scanner_thread)
            
            # Connect signals
            self._scanner_thread.started.connect(self._scanner_worker.run)
            self._scanner_worker.progress.connect(self._on_scan_progress)
            self._scanner_worker.device_found.connect(self._on_device_found)
            self._scanner_worker.scan_complete.connect(self._on_scan_complete)
            self._scanner_worker.scan_error.connect(self._on_scan_error)
            self._scanner_thread.finished.connect(self._thread_finished)
            
            # Set scanning flag
            self._is_scanning = True
            
            # Start the thread
            self._scanner_thread.start()
            
            # Update UI
            self.scan_started.emit(network_range)
            
            # Clear the scan log and reset progress
            self._scan_log = []
            self.log_message(f"Starting {scan_type} scan of {network_range}")
            self._scan_results = {}
            self._update_scan_button_state()
            if hasattr(self, "progress_bar") and self.progress_bar:
                self.progress_bar.setValue(0)
                self.progress_bar.setVisible(True)
                
            return True
        except Exception as e:
            logger.error(f"Error starting scan: {e}", exc_info=True)
            self._is_scanning = False
            self._cleanup_previous_scan()
            self.scan_error.emit(f"Error starting scan: {e}")
            return False

    def _start_batch_device_scan(self, devices, scan_type):
        """Start a batch scan for a list of devices sequentially"""
        if self._is_scanning:
            QMessageBox.information(
                self.main_window,
                "Scan in Progress",
                "A scan is already in progress. Please wait for it to complete before starting a batch scan."
            )
            return False

        batch_targets = []
        for device in devices:
            if isinstance(device, dict):
                ip = device.get("ip", "")
                label = device.get("label", "").strip() or ip
                if not ip and device.get("device") is not None:
                    ip = device["device"].get_property("ip_address", "")
                    alias = device["device"].get_property("alias", "").strip()
                    label = label or alias or ip
                if not ip:
                    continue
                batch_targets.append({"ip": ip, "label": label})
                continue

            ip = device.get_property("ip_address", "")
            if not ip:
                continue
            alias = device.get_property("alias", "").strip() if hasattr(device, "get_property") else ""
            label = alias if alias else ip
            batch_targets.append({"ip": ip, "label": label})

        if not batch_targets:
            QMessageBox.warning(
                self.main_window,
                "No Valid Devices",
                "None of the selected devices have valid IP addresses."
            )
            return False

        self._batch_scan_queue = batch_targets
        self._batch_scan_total = len(batch_targets)
        self._batch_scan_index = 0
        self._batch_scan_current = None
        self._batch_scan_active = True
        threads = max(1, min(8, int(self.settings.get("batch_scan_threads", {}).get("value", 1) or 1)))

        self.log_message(f"Starting batch scan for {self._batch_scan_total} device(s)" + (f" ({threads} parallel)" if threads > 1 else ""))

        if threads > 1:
            self._is_scanning = True
            self._update_scan_button_state()
            if hasattr(self, "progress_bar") and self.progress_bar:
                self.progress_bar.setValue(0)
                self.progress_bar.setVisible(True)
            self._refill_batch_slots(scan_type)
            return True
        return self._start_next_batch_scan(scan_type)

    def _start_next_batch_scan(self, scan_type):
        """Start the next scan in the batch queue"""
        if not self._batch_scan_active or not self._batch_scan_queue:
            self._clear_batch_scan()
            return False

        if self._is_scanning:
            return False

        self._batch_scan_index += 1
        self._batch_scan_current = self._batch_scan_queue.pop(0)
        current_ip = self._batch_scan_current["ip"]
        current_label = self._batch_scan_current["label"]

        if hasattr(self, "status_label"):
            self.status_label.setText(
                f"Scanning device {self._batch_scan_index}/{self._batch_scan_total}: {current_label}"
            )

        self.log_message(
            f"Starting device {self._batch_scan_index}/{self._batch_scan_total} scan: {current_label}"
        )

        return self.scan_network(current_ip, scan_type)

    def _clear_batch_scan(self):
        """Reset batch scan state"""
        for slot in list(self._batch_scan_slots):
            try:
                if slot.get("worker"):
                    slot["worker"].stop()
                if slot.get("thread") and slot["thread"].isRunning():
                    slot["thread"].quit()
                    slot["thread"].wait(500)
            except Exception as e:
                logger.debug(f"Error clearing batch slot: {e}")
        self._batch_scan_slots = []
        self._batch_scan_queue = []
        self._batch_scan_total = 0
        self._batch_scan_index = 0
        self._batch_scan_current = None
        self._batch_scan_active = False
        
    def _create_worker_for_target(self, ip, scan_type):
        """Create (thread, worker) for a single target. Caller connects signals and starts thread."""
        scan_profiles = self.settings["scan_profiles"]["value"]
        custom_args = self.settings["custom_scan_args"]["value"]
        use_sudo = self.settings["use_sudo"]["value"]
        timeout = self.settings["scan_timeout"]["value"]
        if scan_type in scan_profiles:
            profile = scan_profiles[scan_type]
            if not custom_args:
                custom_args = profile.get("arguments", "")
            if timeout == self.settings["scan_timeout"]["default"]:
                timeout = profile.get("timeout", timeout)
        nmap_path = getattr(self, "nmap_path", None)
        thread = QThread()
        worker = ScannerWorker(
            network_range=ip,
            scan_type=scan_type,
            timeout=timeout,
            use_sudo=use_sudo,
            custom_scan_args=custom_args,
            nmap_path=nmap_path
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        return thread, worker
        
    def _refill_batch_slots(self, scan_type):
        """Start up to batch_scan_threads workers for queued targets."""
        max_n = max(1, min(8, int(self.settings.get("batch_scan_threads", {}).get("value", 1) or 1)))
        while self._batch_scan_active and self._batch_scan_queue and len(self._batch_scan_slots) < max_n:
            target = self._batch_scan_queue.pop(0)
            self._batch_scan_index += 1
            self._batch_scan_current = target
            current_ip = target["ip"]
            current_label = target["label"]
            if hasattr(self, "status_label"):
                self.status_label.setText(
                    f"Scanning device {self._batch_scan_index}/{self._batch_scan_total}: {current_label}"
                )
            self.log_message(
                f"Starting device {self._batch_scan_index}/{self._batch_scan_total} scan: {current_label}"
            )
            thread, worker = self._create_worker_for_target(current_ip, scan_type)
            slot = {"thread": thread, "worker": worker, "target": target, "index": self._batch_scan_index}
            worker.progress.connect(self._on_scan_progress)
            worker.device_found.connect(self._on_device_found)
            worker.scan_complete.connect(
                lambda results, s=slot, st=scan_type: self._on_batch_slot_complete(s, results, st)
            )
            worker.scan_error.connect(
                lambda msg, s=slot, st=scan_type: self._on_batch_slot_error(s, msg, st)
            )
            self._batch_scan_slots.append(slot)
            thread.start()
        if self._batch_scan_active and not self._batch_scan_queue and not self._batch_scan_slots:
            self._batch_scan_done()
        
    def _on_batch_slot_complete(self, slot, results, scan_type):
        """Handle completion of one batch slot (parallel batch)."""
        try:
            if slot.get("worker"):
                slot["worker"].stop()
            if slot.get("thread") and slot["thread"].isRunning():
                slot["thread"].quit()
                slot["thread"].wait(1000)
        except Exception as e:
            logger.debug(f"Error cleaning batch slot: {e}")
        if slot in self._batch_scan_slots:
            self._batch_scan_slots.remove(slot)
        # Merge results
        if isinstance(results, dict) and results.get("devices"):
            self._scan_results.update({d.get("ip_address", str(i)): d for i, d in enumerate(results["devices"])})
        if hasattr(self, "progress_bar") and self.progress_bar:
            self.progress_bar.setValue(min(100, int(100 * (self._batch_scan_total - len(self._batch_scan_queue) - len(self._batch_scan_slots)) / max(1, self._batch_scan_total))))
        self._refill_batch_slots(scan_type)
        
    def _on_batch_slot_error(self, slot, error_message, scan_type):
        """Handle error from one batch slot (parallel batch)."""
        try:
            if slot.get("worker"):
                slot["worker"].stop()
            if slot.get("thread") and slot["thread"].isRunning():
                slot["thread"].quit()
                slot["thread"].wait(1000)
        except Exception as e:
            logger.debug(f"Error cleaning batch slot: {e}")
        if slot in self._batch_scan_slots:
            self._batch_scan_slots.remove(slot)
        label = slot.get("target", {}).get("label", "device")
        self.log_message(f"Batch scan error: {label} - {error_message}")
        self._refill_batch_slots(scan_type)
        
    def _batch_scan_done(self):
        """Called when all parallel batch slots and queue are empty."""
        self._clear_batch_scan()
        self._is_scanning = False
        self._update_scan_button_state()
        if hasattr(self, "status_label"):
            self.status_label.setText("Batch scan complete")
        if hasattr(self, "progress_bar") and self.progress_bar:
            self.progress_bar.setValue(100)
        self.scan_completed.emit({"devices_found": len(self._scan_results), "scan_time": 0, "devices": list(self._scan_results.values())})
        
    def _cleanup_previous_scan(self):
        """Clean up any previous scan thread and worker"""
        # Stop thread if running
        if self._scanner_thread and self._scanner_thread.isRunning():
            logger.debug("Cleaning up previous thread")
            try:
                # Try to stop the worker if it exists
                if self._scanner_worker:
                    self._scanner_worker.stop()
                
                # Quit and wait for the thread
                self._scanner_thread.quit()
                success = self._scanner_thread.wait(1000)  # 1 second timeout
                
                if not success:
                    logger.warning("Thread did not exit cleanly, forcing termination")
                    self._scanner_thread.terminate()
                    self._scanner_thread.wait(1000)
            except Exception as e:
                logger.error(f"Error cleaning up previous scan: {e}")
                
        # Reset references
        self._scanner_thread = None
        self._scanner_worker = None
        self._is_scanning = False
        
    def _thread_finished(self):
        """Handle thread finished signal"""
        logger.debug("Scanner thread finished")
        
        # The actual scan results are handled by the _on_scan_complete or _on_scan_error callbacks
        # This is just an extra safeguard to ensure thread resources are cleaned up
        if self._is_scanning:
            # If we get here and still think we're scanning, something went wrong
            logger.warning("Thread finished while still scanning - cleanup needed")
            self._is_scanning = False
            
            # Update UI
            self._update_scan_button_state()
            if hasattr(self, "status_label"):
                self.status_label.setText("Scan interrupted unexpectedly")
                
            self.log_message("Scan interrupted unexpectedly")
        
    def is_scanning(self):
        """
        Check if a scan is currently in progress
        
        Returns:
            bool: True if a scan is in progress, False otherwise
        """
        return self._is_scanning
        
    def stop_scan(self):
        """
        Stop any currently running scan
        
        Returns:
            bool: True if scan was stopped, False if no scan was running
        """
        if not self.is_scanning():
            logger.debug("No scan running to stop")
            if self._batch_scan_active:
                self._clear_batch_scan()
            return False
            
        logger.info("Stopping scan...")
        
        # Update UI first to give immediate feedback
        if hasattr(self, "status_label"):
            self.status_label.setText("Stopping scan...")
            
        # Try to stop ping scan if it's running
        stopped_ping = self.stop_ping_scan()
        
        # Signal the worker to stop
        try:
            if self._scanner_worker:
                self._scanner_worker.stop()
                logger.debug("Worker stop signal sent")
                
                # Force nmap to terminate if possible
                try:
                    # The python-nmap library sometimes doesn't properly terminate the nmap process
                    # We attempt to directly terminate it by accessing the internal scanner object
                    if hasattr(self._scanner_worker, 'scanner') and self._scanner_worker.scanner:
                        # Try to terminate the nmap process directly
                        if hasattr(self._scanner_worker.scanner, '_nmap_last_proc') and self._scanner_worker.scanner._nmap_last_proc:
                            try:
                                process = self._scanner_worker.scanner._nmap_last_proc
                                if process.poll() is None:  # Check if still running
                                    logger.info("Forcibly terminating nmap process")
                                    process.terminate()
                                    # Wait briefly for termination
                                    import time
                                    time.sleep(0.5)
                                    # If still running, kill it
                                    if process.poll() is None:
                                        process.kill()
                                        logger.info("Killed nmap process")
                            except Exception as e:
                                logger.error(f"Error terminating nmap process: {e}")
                except Exception as e:
                    logger.error(f"Error accessing nmap process: {e}")
                
        except Exception as e:
            logger.error(f"Error signaling worker to stop: {e}")
        
        # Wait a bit before trying to terminate the thread
        try:
            if self._scanner_thread and self._scanner_thread.isRunning():
                # Try to quit gracefully first
                self._scanner_thread.quit()
                logger.debug("Thread quit signal sent")
                
                # Wait for the thread to finish with timeout
                if not self._scanner_thread.wait(3000):  # 3 second timeout
                    logger.warning("Thread did not exit within timeout, forcing termination")
                    try:
                        self._scanner_thread.terminate()
                        logger.debug("Thread terminate signal sent")
                        # Short wait for termination to take effect
                        self._scanner_thread.wait(1000)
                    except Exception as term_error:
                        logger.error(f"Error terminating thread: {term_error}")
        except Exception as e:
            logger.error(f"Error stopping thread: {e}")
                
        # Mark as not scanning
        self._is_scanning = False
        self._update_scan_button_state()
        if hasattr(self, "status_label"):
            self.status_label.setText("Scan stopped by user")
            
        self.log_message("Scan stopped by user")

        if self._batch_scan_active:
            self._clear_batch_scan()
        
        return True
        
    def get_scan_results(self):
        """
        Get the results of the most recent scan
        
        Returns:
            dict: Dictionary containing scan results with statistics
        """
        return self._scan_results
        
    def _on_scan_progress(self, current, total):
        """Handle scan progress updates"""
        # Calculate percentage
        if total > 0:
            percentage = int((current / total) * 100)
        else:
            percentage = 0
            
        # Update progress bar
        if hasattr(self, "progress_bar"):
            self.progress_bar.setValue(percentage)
            self.progress_bar.setTextVisible(True)
            if self._batch_scan_active and self._batch_scan_current:
                current_label = self._batch_scan_current.get("label", self._batch_scan_current.get("ip", "device"))
                remaining = max(0, self._batch_scan_total - self._batch_scan_index)
                self.progress_bar.setFormat(
                    f"Device {self._batch_scan_index}/{self._batch_scan_total} "
                    f"({remaining} remaining): {current_label} - %p%"
                )
            else:
                self.progress_bar.setFormat("Scanning - %p%")
            
        # Update status label
        if hasattr(self, "status_label"):
            if self._batch_scan_active and self._batch_scan_current:
                current_label = self._batch_scan_current.get("label", self._batch_scan_current.get("ip", "device"))
                self.status_label.setText(
                    f"Scanning device {self._batch_scan_index}/{self._batch_scan_total}: "
                    f"{current_label} ({current}/{total} hosts, {percentage}%)"
                )
            else:
                self.status_label.setText(f"Scanning: {current}/{total} hosts processed ({percentage}%)")
            
        # Emit the scan progress signal
        self.scan_progress.emit(current, total)
        
    def _on_device_found(self, host_data):
        """
        Handle a device found during scanning
        
        This method is called when the scanner worker finds a device.
        It creates a new device or updates an existing one.
        """
        try:
            # Check if this is a status update rather than a device
            if "status_update" in host_data:
                # Update the status label with the status message
                if hasattr(self, "status_label"):
                    self.status_label.setText(host_data["status_update"])
                
                # Log the status update
                self.log_message(host_data["status_update"])
                return None
                
            # Use a local copy of host_data to avoid memory corruption
            device_data = host_data.copy()
            
            # Verify we have an IP address at minimum - if not, this isn't a valid device
            if not device_data.get("ip_address"):
                logger.debug("Received device data without IP address, ignoring")
                return None
                
            # For non-ping scans, ensure the device has some meaningful data
            if device_data.get("scan_source") != "ping":
                # Check if this device has any meaningful properties to add
                has_meaningful_data = False
                # Look for properties that would make this device worth adding
                for key in ["hostname", "mac_address", "open_ports", "services", "os"]:
                    if key in device_data and device_data[key]:
                        has_meaningful_data = True
                        break
                        
                # If a device is up but has no additional data, it's still worth adding
                # But we should log this situation for debugging
                if not has_meaningful_data:
                    logger.debug(f"Device at {device_data['ip_address']} is up but has no additional data")
            
            # Check if this device already exists based on IP or MAC
            existing_device = None
            if "ip_address" in device_data and device_data["ip_address"]:
                # Try to find by IP address
                for device in self.device_manager.get_devices():
                    if device.get_property("ip_address") == device_data["ip_address"]:
                        existing_device = device
                        break
                        
            if not existing_device and "mac_address" in device_data and device_data["mac_address"]:
                # Try to find by MAC address
                for device in self.device_manager.get_devices():
                    if device.get_property("mac_address") == device_data["mac_address"]:
                        existing_device = device
                        break
            
            if existing_device:
                # Update existing device (one property at a time to prevent race conditions)
                for key, value in device_data.items():
                    if key == "tags":
                        # Merge tags rather than replace
                        current_tags = existing_device.get_property("tags", [])
                        new_tags = []
                        for tag in value:
                            if tag not in current_tags and tag not in new_tags:
                                new_tags.append(tag)
                        
                        # Only update if there are new tags to add
                        if new_tags:
                            updated_tags = current_tags.copy()  # Make a copy to avoid modifying original
                            updated_tags.extend(new_tags)
                            existing_device.set_property("tags", updated_tags)
                    else:
                        # Only update if value is different to minimize device_changed events
                        current_value = existing_device.get_property(key, None)
                        if current_value != value:
                            existing_device.set_property(key, value)
                
                # Log the update
                self.log_message(f"Updated existing device: {existing_device.get_property('alias')}")
                
                # Emit the device found signal
                self.scan_device_found.emit(existing_device)
                
                return existing_device
            else:
                # Create a new device
                new_device = self.device_manager.create_device(
                    device_type="scanned",
                    **device_data
                )
                
                # Add it to the device manager
                self.device_manager.add_device(new_device)
                
                # Allow table to repaint when devices are added during nmap/chunked scan
                if device_data.get("scan_source") == "nmap":
                    QApplication.processEvents()
                
                # Log the addition
                self.log_message(f"Added new device: {new_device.get_property('alias')}")
                
                # Emit the device found signal
                self.scan_device_found.emit(new_device)
                
                return new_device
                
        except Exception as e:
            logger.error(f"Error adding/updating device: {e}", exc_info=True)
            self.log_message(f"Error adding/updating device: {e}")
            return None
            
    def _on_scan_complete(self, results):
        """Handle scan completion"""
        self._is_scanning = False
        # Store the results
        self._scan_results = results
        self._update_scan_button_state()
        # Update status
        if hasattr(self, "status_label"):
            if self._batch_scan_active and self._batch_scan_current:
                current_label = self._batch_scan_current.get("label", self._batch_scan_current.get("ip", "device"))
                if self._batch_scan_queue:
                    self.status_label.setText(
                        f"Completed device {self._batch_scan_index}/{self._batch_scan_total}: {current_label}"
                    )
                else:
                    self.status_label.setText("Batch scan complete")
            else:
                self.status_label.setText("Scan complete")
            
        # Set progress to 100%
        if hasattr(self, "progress_bar"):
            self.progress_bar.setValue(100)
            
        # Log results
        scan_time = round(results["scan_time"], 1)
        self.log_message(f"Scan complete: Found {results['devices_found']} devices in {scan_time} seconds")
        
        # Stop the thread and ensure proper cleanup
        if self._scanner_thread and self._scanner_thread.isRunning():
            self._scanner_thread.quit()
            success = self._scanner_thread.wait(1000)  # 1 second timeout
            
            if not success:
                logger.warning("Thread did not exit cleanly after scan completion, forcing termination")
                self._scanner_thread.terminate()
                self._scanner_thread.wait(1000)
            
            # Reset references to help garbage collection
            self._scanner_worker = None
            self._scanner_thread = None
        
        # Force a garbage collection cycle to clean up lingering objects
        try:
            import gc
            gc.collect()
        except Exception as e:
            logger.warning(f"Error during garbage collection: {e}")
        
        # Emit the scan completed signal
        self.scan_completed.emit(results)

        if self._batch_scan_active:
            if self._batch_scan_queue:
                scan_type = self.settings["scan_type"]["value"]
                QTimer.singleShot(200, lambda: self._start_next_batch_scan(scan_type))
            else:
                self._clear_batch_scan()
        
    def _on_scan_error(self, error_message):
        """Handle scan errors"""
        self._is_scanning = False
        self._update_scan_button_state()
        # Update status
        if hasattr(self, "status_label"):
            if self._batch_scan_active and self._batch_scan_current:
                current_label = self._batch_scan_current.get("label", self._batch_scan_current.get("ip", "device"))
                self.status_label.setText(
                    f"Error on device {self._batch_scan_index}/{self._batch_scan_total}: {current_label}"
                )
            else:
                self.status_label.setText(f"Error: {error_message}")
            
        # Log the error
        self.log_message(f"Scan error: {error_message}")

        if self._batch_scan_active and self._batch_scan_current:
            current_label = self._batch_scan_current.get("label", self._batch_scan_current.get("ip", "device"))
            self.log_message(
                f"Batch scan error on device {self._batch_scan_index}/{self._batch_scan_total}: "
                f"{current_label} - {error_message}"
            )
        
        # Stop the thread
        if self._scanner_thread and self._scanner_thread.isRunning():
            self._scanner_thread.quit()
            self._scanner_thread.wait()
            
        # Emit the scan error signal
        self.scan_error.emit(error_message) 

        if self._batch_scan_active:
            if self._batch_scan_queue:
                scan_type = self.settings["scan_type"]["value"]
                QTimer.singleShot(200, lambda: self._start_next_batch_scan(scan_type))
            else:
                self._clear_batch_scan()

    @safe_action_wrapper
    def on_scan_action(self):
        """Handle main scan action"""
        # Update network interfaces before showing dialog
        self._update_interface_choices()
        
        # Show scan dialog
        dialog_result = self._show_scan_dialog()
        
        if dialog_result:
            # Get scan type from settings
            scan_type = self.settings["scan_type"]["value"]
            
            # Start the scan
            self._handle_scan_target(dialog_result, scan_type)
            
    @safe_action_wrapper
    def on_scan_selected_action(self):
        """Handle scanning selected devices"""
        # Find the device table
        from src.ui.device_table import DeviceTableView
        device_table = self.main_window.findChild(DeviceTableView)
        
        if not device_table:
            QMessageBox.warning(
                self.main_window,
                "Device Table Not Found",
                "Could not find the device table view."
            )
            return
            
        # Get selected devices
        selected_devices = device_table.get_selected_devices()
        
        if not selected_devices:
            QMessageBox.warning(
                self.main_window,
                "No Devices Selected",
                "Please select one or more devices to scan."
            )
            return

        # Update network interfaces before showing dialog
        self._update_interface_choices()

        dialog_result = self._show_scan_dialog(selected_devices)
        if not dialog_result:
            return

        # Get scan type from settings
        scan_type = self.settings["scan_type"]["value"]

        self._handle_scan_target(dialog_result, scan_type)
        
    def _update_scan_button_state(self):
        """Update scan button label and state: 'Stop' when scanning, 'Start Scan' when idle."""
        if hasattr(self, "scan_button") and self.scan_button:
            if self._is_scanning:
                self.scan_button.setText("Stop")
            else:
                self.scan_button.setText("Start Scan")
            self.scan_button.setEnabled(True)

    def on_scan_stop_button_clicked(self):
        """Single handler: start scan when idle, stop scan when running."""
        if self._is_scanning:
            self.stop_scan()
            return
        self._do_start_scan_from_panel()

    def _do_start_scan_from_panel(self):
        """Start a scan using current panel target/range/type (called when Start Scan is clicked)."""
        # Check if nmap is available
        if not hasattr(self, 'nmap_available') or not self.nmap_available:
            QMessageBox.warning(
                self.main_window,
                "Nmap Not Available",
                "Nmap is not available. Network scanning features are disabled.\n\n"
                "To enable scanning:\n"
                "1. Install the nmap executable (see https://nmap.org/download.html)\n"
                "2. Make sure nmap is in your system PATH\n"
                "3. Restart NetWORKS"
            )
            return
            
        # Get network range from the UI based on target dropdown
        target = self.target_combo.currentData() if hasattr(self, "target_combo") and self.target_combo.currentData() is not None else "interface"
        if target == "devices":
            # Scan selected devices
            from src.ui.device_table import DeviceTableView
            device_table = self.main_window.findChild(DeviceTableView)
            if device_table:
                selected_devices = device_table.get_selected_devices()
            else:
                selected_devices = self.device_manager.get_selected_devices()
            if not selected_devices:
                QMessageBox.warning(
                    self.main_window,
                    "No Devices Selected",
                    "Please select one or more devices to scan."
                )
                return
            
            # Filter devices with IP addresses
            devices_with_ips = [
                d for d in selected_devices
                if hasattr(d, "get_property") and d.get_property("ip_address", "")
            ]
            if not devices_with_ips:
                QMessageBox.warning(
                    self.main_window,
                    "No Valid IP Addresses",
                    "None of the selected devices have valid IP addresses."
                )
                return
            
            scan_type = self.scan_type_combo.currentText()
            self._start_batch_device_scan(devices_with_ips, scan_type)
            return
        elif target == "interface":
            # Use interface subnet
            network_range = self._get_interface_subnet(self.interface_combo.currentText())
            if not network_range:
                QMessageBox.warning(
                    self.main_window,
                    "Missing Network Range",
                    "Could not determine subnet for the selected interface. Please select a different interface or use Custom Network Range."
                )
                return
        elif target == "custom":
            # Use custom range from text field
            network_range = self.network_range_edit.text().strip()
            if not network_range:
                QMessageBox.warning(
                    self.main_window,
                    "Missing Network Range",
                    "Please enter a network range (e.g., 192.168.1.0/24 or 10.0.0.1-10.0.0.254)."
                )
                return
        else:
            # Fallback
            network_range = self.network_range_edit.text().strip()
            if not network_range:
                network_range = self._get_interface_subnet(self.interface_combo.currentText())
                if not network_range:
                    QMessageBox.warning(
                        self.main_window,
                        "Missing Network Range",
                        "Please enter a network range or select a valid interface."
                    )
                    return
        
        # Get scan type from UI
        scan_type = self.scan_type_combo.currentText()
        
        # Start the scan directly with the current panel settings
        self.scan_network(network_range, scan_type)

    @safe_action_wrapper
    def on_advanced_scan_button_clicked(self):
        """Handle advanced scan button click - opens the full scan dialog"""
        # Check if scan already in progress
        if self._is_scanning:
            QMessageBox.information(
                self.main_window,
                "Scan in Progress",
                "A scan is already in progress. Please wait for it to complete or click Stop to cancel it."
            )
            return
            
        # Update network interfaces before showing dialog
        self._update_interface_choices()
        
        # Show scan dialog
        dialog_result = self._show_scan_dialog()
        
        if dialog_result:
            # Get scan type from settings
            scan_type = self.settings["scan_type"]["value"]
            
            # Start the scan
            self._handle_scan_target(dialog_result, scan_type)
        
    @safe_action_wrapper
    def on_stop_button_clicked(self):
        """Handle stop button click"""
        self.stop_scan()
        
    def _show_scan_dialog(self, selected_devices=None):
        """Show a dialog to get scan parameters"""
        if selected_devices and not isinstance(selected_devices, list):
            selected_devices = [selected_devices]

        dialog = QDialog(self.main_window)
        mark_plugin_ui(dialog)
        dialog.setWindowTitle("Network Scan")
        dialog.setMinimumWidth(550)  # Slightly wider to accommodate content
        dialog.setMinimumHeight(450)  # Set minimum height
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)  # Add proper margins
        layout.setSpacing(12)  # Increase spacing
        
        # Create tabs for basic and advanced settings
        tab_widget = QTabWidget()
        mark_plugin_ui(tab_widget)
        mark_plugin_ui(tab_widget.tabBar())
        basic_tab = QWidget()
        advanced_tab = QWidget()
        profiles_tab = QWidget()
        
        tab_widget.addTab(basic_tab, "Basic")
        tab_widget.addTab(advanced_tab, "Advanced")
        tab_widget.addTab(profiles_tab, "Scan Profiles")
        
        # ==== Basic Tab ====
        basic_layout = QVBoxLayout(basic_tab)
        basic_layout.setContentsMargins(10, 10, 10, 10)  # Add margins
        basic_layout.setSpacing(12)  # Increase spacing
        
        # Network interface selection
        interface_group = QGroupBox("Network Interface")
        interface_layout = QVBoxLayout(interface_group)
        interface_layout.setContentsMargins(10, 15, 10, 10)
        interface_layout.setSpacing(8)
        
        interface_combo = QComboBox()
        # Add interfaces from settings
        interface_combo.addItems(self.settings["preferred_interface"]["choices"])
        current_interface = self.settings["preferred_interface"]["value"]
        if current_interface and current_interface in self.settings["preferred_interface"]["choices"]:
            interface_combo.setCurrentText(current_interface)
            
        interface_layout.addWidget(interface_combo)
        basic_layout.addWidget(interface_group)
        
        # Scan target options - single dropdown
        target_group = QGroupBox("Scan Target")
        target_layout = QVBoxLayout(target_group)
        target_layout.setContentsMargins(10, 15, 10, 10)
        target_layout.setSpacing(10)
        
        target_combo = QComboBox()
        target_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        target_combo.setToolTip("Select what to scan")
        
        selected_devices_list = None
        list_container = None
        add_device_button = None
        remove_device_button = None
        if selected_devices:
            target_combo.addItem(f"Selected Devices ({len(selected_devices)})", "devices")
            list_container = QGroupBox("Devices to Scan")
            list_layout = QVBoxLayout(list_container)
            list_layout.setContentsMargins(10, 10, 10, 10)
            list_layout.setSpacing(6)
            selected_devices_list = QListWidget()
            for device in selected_devices:
                ip_address = device.get_property("ip_address", "") if hasattr(device, "get_property") else ""
                alias = device.get_property("alias", "") if hasattr(device, "get_property") else ""
                if alias and ip_address:
                    label = f"{alias} ({ip_address})"
                elif ip_address:
                    label = ip_address
                else:
                    label = alias or "Device"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, {"device": device, "ip": ip_address, "label": label})
                selected_devices_list.addItem(item)
            list_layout.addWidget(selected_devices_list)
            list_button_layout = QHBoxLayout()
            add_device_button = QPushButton("Add by IP...")
            remove_device_button = QPushButton("Remove Selected")
            list_button_layout.addWidget(add_device_button)
            list_button_layout.addWidget(remove_device_button)
            list_layout.addLayout(list_button_layout)
            target_layout.addWidget(list_container)

        group_combo = None
        available_groups = [g for g in self.device_manager.get_groups() if g != self.device_manager.root_group]
        if available_groups:
            target_combo.addItem("Group Devices", "group")
            group_combo = QComboBox()
            group_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            group_combo.setToolTip("Select a group to scan")
            available_groups.sort(key=lambda g: self._format_group_path(g).lower())
            for group in available_groups:
                group_combo.addItem(self._format_group_path(group), group)
            target_layout.addWidget(group_combo)
        
        target_combo.addItem("Interface Subnet", "interface")
        target_combo.addItem("Custom Network Range", "custom")
        
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Target:"))
        target_row.addWidget(target_combo, 1)
        target_layout.insertLayout(0, target_row)
        
        custom_range_container = QWidget()
        custom_range_layout = QHBoxLayout(custom_range_container)
        custom_range_layout.setContentsMargins(0, 0, 0, 0)
        custom_range_layout.setSpacing(8)
        network_range_edit = QLineEdit()
        network_range_edit.setPlaceholderText("e.g., 192.168.1.0/24 or 10.0.0.1-10.0.0.254")
        custom_range_layout.addWidget(network_range_edit)
        target_layout.addWidget(custom_range_container)
        
        if not selected_devices:
            target_combo.setCurrentIndex(target_combo.findData("interface"))
        else:
            target_combo.setCurrentIndex(0)
        
        def update_ui_state():
            t = target_combo.currentData() if target_combo.currentData() is not None else "interface"
            network_range_edit.setEnabled(t == "custom")
            custom_range_container.setVisible(t == "custom")
            if list_container and selected_devices_list:
                list_container.setVisible(t == "devices")
            if group_combo:
                group_combo.setVisible(t == "group")
            interface_group.setEnabled(t == "interface")
        
        target_combo.currentIndexChanged.connect(update_ui_state)

        if selected_devices_list and add_device_button is not None and remove_device_button is not None:
            def add_device_by_ip():
                ip, ok = QInputDialog.getText(
                    dialog,
                    "Add Device by IP",
                    "Enter IP address or range:"
                )
                if not ok:
                    return
                ip = ip.strip()
                if not ip:
                    return
                label = ip
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, {"device": None, "ip": ip, "label": label})
                selected_devices_list.addItem(item)
                idx = target_combo.findData("devices")
                if idx >= 0:
                    target_combo.setItemText(idx, f"Selected Devices ({selected_devices_list.count()})")

            def remove_selected_devices():
                for item in selected_devices_list.selectedItems():
                    row = selected_devices_list.row(item)
                    selected_devices_list.takeItem(row)
                idx = target_combo.findData("devices")
                if idx >= 0:
                    target_combo.setItemText(idx, f"Selected Devices ({selected_devices_list.count()})")

            add_device_button.clicked.connect(add_device_by_ip)
            remove_device_button.clicked.connect(remove_selected_devices)
            
        update_ui_state()
        
        basic_layout.addWidget(target_group)
        
        # Scan profile
        profile_group = QGroupBox("Scan Profile")
        profile_layout = QVBoxLayout(profile_group)
        profile_layout.setContentsMargins(10, 15, 10, 10)
        profile_layout.setSpacing(8)
        
        # Scan type with label in layout
        scan_type_layout = QHBoxLayout()
        scan_type_layout.addWidget(QLabel("Scan Type:"))
        scan_type_combo = QComboBox()
        scan_type_combo.addItems(self.settings["scan_type"]["choices"])
        scan_type_combo.setCurrentText(self.settings["scan_type"]["value"])
        scan_type_layout.addWidget(scan_type_combo, 1)  # Give combo box more space
        
        profile_layout.addLayout(scan_type_layout)
        
        # Create a label to show scan description with proper styling
        scan_description_label = QLabel()
        scan_description_label.setWordWrap(True)
        scan_description_label.setStyleSheet("padding: 5px; background-color: rgba(240, 240, 240, 100); border-radius: 4px;")
        scan_description_label.setMinimumHeight(60)  # Ensure enough height for multi-line descriptions
        
        # Function to update description when scan type changes
        def update_scan_description(index):
            scan_type = scan_type_combo.currentText()
            profiles = self.settings["scan_profiles"]["value"]
            if scan_type in profiles:
                description = profiles[scan_type].get("description", "")
                scan_description_label.setText(description)
                
        # Connect the signal
        scan_type_combo.currentIndexChanged.connect(update_scan_description)
        
        # Call initially to set the description
        update_scan_description(0)
        
        profile_layout.addWidget(scan_description_label)
        
        basic_layout.addWidget(profile_group)
        basic_layout.addStretch(1)  # Add stretch to keep widgets at the top
        
        # ==== Advanced Tab ====
        advanced_layout = QVBoxLayout(advanced_tab)
        advanced_layout.setContentsMargins(10, 10, 10, 10)
        advanced_layout.setSpacing(12)
        
        # Scan options
        options_group = QGroupBox("Scan Options")
        options_layout = QFormLayout(options_group)
        options_layout.setContentsMargins(10, 15, 10, 10)
        options_layout.setSpacing(10)
        options_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)  # Allow fields to grow
        
        # Elevated permissions
        elevated_check = QCheckBox()
        elevated_check.setChecked(self.settings["use_sudo"]["value"])
        options_layout.addRow("Use Elevated Permissions:", elevated_check)
        
        # Timeout
        timeout_edit = QLineEdit(str(self.settings["scan_timeout"]["value"]))
        timeout_edit.setValidator(QIntValidator(10, 1000))
        options_layout.addRow("Timeout (seconds):", timeout_edit)
        
        # Custom arguments
        custom_args_edit = QLineEdit(self.settings["custom_scan_args"]["value"])
        custom_args_edit.setPlaceholderText("e.g., -p 80,443 -sV")
        options_layout.addRow("Custom nmap arguments:", custom_args_edit)
        
        advanced_layout.addWidget(options_group)
        advanced_layout.addStretch(1)  # Add stretch to keep widgets at the top
        
        # ==== Profiles Tab ====
        profiles_layout = QVBoxLayout(profiles_tab)
        profiles_layout.setContentsMargins(10, 10, 10, 10)
        profiles_layout.setSpacing(12)
        
        # Profile selector
        profiles_label = QLabel("Profile Editor")
        profiles_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        profiles_layout.addWidget(profiles_label)

        profile_select_layout = QHBoxLayout()
        profile_select_layout.addWidget(QLabel("Profile:"))
        profile_select_combo = QComboBox()
        profile_keys = list(self.settings["scan_profiles"]["value"].keys())
        profile_select_combo.addItems(profile_keys)
        profile_select_layout.addWidget(profile_select_combo, 1)
        profiles_layout.addLayout(profile_select_layout)

        profile_description_display = QLabel()
        profile_description_display.setWordWrap(True)
        profile_description_display.setStyleSheet(
            "padding: 5px; background-color: rgba(240, 240, 240, 100); border-radius: 4px;"
        )
        profile_description_display.setMinimumHeight(50)
        profiles_layout.addWidget(profile_description_display)

        editor_group = QGroupBox("Edit Profile")
        editor_layout = QFormLayout(editor_group)
        editor_layout.setContentsMargins(10, 15, 10, 10)
        editor_layout.setSpacing(10)

        profile_name_edit = QLineEdit()
        editor_layout.addRow("Name:", profile_name_edit)

        profile_description_edit = QTextEdit()
        profile_description_edit.setFixedHeight(80)
        editor_layout.addRow("Description:", profile_description_edit)

        profile_arguments_edit = QLineEdit()
        editor_layout.addRow("Arguments:", profile_arguments_edit)

        profile_timeout_edit = QLineEdit()
        profile_timeout_edit.setValidator(QIntValidator(10, 2000))
        editor_layout.addRow("Timeout (seconds):", profile_timeout_edit)

        profiles_layout.addWidget(editor_group)

        profile_button_layout = QHBoxLayout()
        profile_save_button = QPushButton("Save Profile")
        profile_delete_button = QPushButton("Delete Profile")
        profile_button_layout.addWidget(profile_save_button)
        profile_button_layout.addWidget(profile_delete_button)
        profiles_layout.addLayout(profile_button_layout)

        profiles_layout.addStretch(1)

        profiles = self.settings["scan_profiles"]["value"]

        def refresh_profile_choices(preferred_key=None):
            keys = list(self.settings["scan_profiles"]["value"].keys())
            if not keys:
                return
            current_scan_key = scan_type_combo.currentText()
            current_profile_key = profile_select_combo.currentText()

            scan_type_combo.blockSignals(True)
            scan_type_combo.clear()
            scan_type_combo.addItems(keys)
            if preferred_key and preferred_key in keys:
                scan_type_combo.setCurrentText(preferred_key)
            elif current_scan_key in keys:
                scan_type_combo.setCurrentText(current_scan_key)
            else:
                scan_type_combo.setCurrentText(keys[0])
            scan_type_combo.blockSignals(False)

            profile_select_combo.blockSignals(True)
            profile_select_combo.clear()
            profile_select_combo.addItems(keys)
            if preferred_key and preferred_key in keys:
                profile_select_combo.setCurrentText(preferred_key)
            elif current_profile_key in keys:
                profile_select_combo.setCurrentText(current_profile_key)
            else:
                profile_select_combo.setCurrentText(keys[0])
            profile_select_combo.blockSignals(False)

            self.settings["scan_type"]["choices"] = keys

        def load_profile(profile_key):
            profile = profiles.get(profile_key, {})
            profile_name_edit.setText(profile.get("name", profile_key))
            profile_description_edit.setPlainText(profile.get("description", ""))
            profile_arguments_edit.setText(profile.get("arguments", ""))
            profile_timeout_edit.setText(str(profile.get("timeout", 300)))
            profile_description_display.setText(profile.get("description", ""))

        def save_profile():
            profile_key = profile_select_combo.currentText().strip()
            if not profile_key:
                return
            profiles[profile_key] = {
                "name": profile_name_edit.text().strip() or profile_key,
                "description": profile_description_edit.toPlainText().strip(),
                "arguments": profile_arguments_edit.text().strip(),
                "timeout": int(profile_timeout_edit.text() or 300),
            }
            self.settings["scan_profiles"]["value"] = profiles
            refresh_profile_choices(preferred_key=profile_key)
            load_profile(profile_key)
            if scan_type_combo.currentText() == profile_key:
                update_scan_description(0)

        def delete_profile():
            profile_key = profile_select_combo.currentText().strip()
            if not profile_key or profile_key not in profiles:
                return
            if len(profiles) <= 1:
                QMessageBox.warning(
                    self.main_window,
                    "Cannot Delete Profile",
                    "At least one scan profile must remain."
                )
                return
            result = QMessageBox.question(
                self.main_window,
                "Delete Profile",
                f"Delete the scan profile '{profile_key}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if result != QMessageBox.Yes:
                return
            del profiles[profile_key]
            self.settings["scan_profiles"]["value"] = profiles
            refresh_profile_choices()
            load_profile(profile_select_combo.currentText())
            update_scan_description(0)

        def on_profile_selection_changed(index):
            profile_key = profile_select_combo.currentText()
            if profile_key:
                load_profile(profile_key)
                if profile_key in self.settings["scan_type"]["choices"]:
                    scan_type_combo.setCurrentText(profile_key)
                    update_scan_description(0)

        def sync_profile_from_scan_type(index):
            profile_key = scan_type_combo.currentText()
            if profile_key in self.settings["scan_profiles"]["value"]:
                profile_select_combo.setCurrentText(profile_key)
                load_profile(profile_key)
                profile_description_display.setText(
                    self.settings["scan_profiles"]["value"][profile_key].get("description", "")
                )

        profile_select_combo.currentIndexChanged.connect(on_profile_selection_changed)
        scan_type_combo.currentIndexChanged.connect(sync_profile_from_scan_type)
        profile_save_button.clicked.connect(save_profile)
        profile_delete_button.clicked.connect(delete_profile)

        # Initialize the editor selection
        if scan_type_combo.currentText() in profile_keys:
            profile_select_combo.setCurrentText(scan_type_combo.currentText())
        elif profile_keys:
            profile_select_combo.setCurrentText(profile_keys[0])
        load_profile(profile_select_combo.currentText())
        sync_profile_from_scan_type(0)
        
        # Try to get a default value for network range based on the local network
        try:
            if current_interface and current_interface != "Any (default)":
                selected_if = current_interface.split(":")[0].strip()
                subnet = self._get_interface_subnet(selected_if)
                if subnet:
                    network_range_edit.setText(subnet)
                    logger.debug(f"Using subnet {subnet} from interface {selected_if}")
            
            # If no subnet from interface, try to get one from local IP
            if not network_range_edit.text():
                import socket
                hostname = socket.gethostname()
                ip_address = socket.gethostbyname(hostname)
                network = ipaddress.IPv4Network(f"{ip_address}/24", strict=False)
                network_range_edit.setText(str(network))
                logger.debug(f"Using subnet {network} from local IP {ip_address}")
        except Exception as e:
            logger.debug(f"Error determining default network range: {e}")
            # If we can't determine the local network, leave it blank
            
        # Connect interface combo to update network range when Interface Subnet target is selected
        def update_network_range(index):
            if target_combo.currentData() == "interface":
                selected_if_text = interface_combo.currentText()
                if selected_if_text and selected_if_text != "Any (default)":
                    subnet = self._get_interface_subnet(selected_if_text)
                    if subnet:
                        network_range_edit.setText(subnet)
                        
        interface_combo.currentIndexChanged.connect(update_network_range)
            
        # Add tabs to layout
        layout.addWidget(tab_widget)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec() == QDialog.Accepted:
            # Get the selected scan type and its profile settings
            selected_scan_type = scan_type_combo.currentText()
            profiles = self.settings["scan_profiles"]["value"]
            
            # Update settings from dialog
            self.settings["scan_type"]["value"] = selected_scan_type
            
            # Use values from the profile as a base, but let user override with advanced settings
            if selected_scan_type in profiles:
                profile = profiles[selected_scan_type]
                self.settings["use_sudo"]["value"] = elevated_check.isChecked()
                self.settings["scan_timeout"]["value"] = int(timeout_edit.text())
                
                # Only use custom args if provided, otherwise use from profile
                custom_args = custom_args_edit.text().strip()
                if custom_args:
                    self.settings["custom_scan_args"]["value"] = custom_args
                else:
                    self.settings["custom_scan_args"]["value"] = profile.get("arguments", "")
            else:
                # If scan type is not in profiles (shouldn't happen), use form values
                self.settings["use_sudo"]["value"] = elevated_check.isChecked()
                self.settings["scan_timeout"]["value"] = int(timeout_edit.text())
                self.settings["custom_scan_args"]["value"] = custom_args_edit.text()
                
            self.settings["preferred_interface"]["value"] = interface_combo.currentText()
            
            # Determine the target to scan from dropdown
            t = target_combo.currentData() if target_combo.currentData() is not None else "interface"
            if t == "devices" and selected_devices_list:
                selected_targets = []
                for index in range(selected_devices_list.count()):
                    item = selected_devices_list.item(index)
                    data = item.data(Qt.UserRole) or {}
                    if not data.get("ip") and data.get("device") is None:
                        continue
                    selected_targets.append(data)
                return {"target_type": "devices", "selected_devices": selected_targets}
            if t == "group" and group_combo:
                selected_group = group_combo.currentData()
                return {"target_type": "group", "group": selected_group}
            if t == "interface":
                selected_if_text = interface_combo.currentText()
                if selected_if_text and selected_if_text != "Any (default)":
                    subnet = self._get_interface_subnet(selected_if_text)
                    if subnet:
                        return {"target_type": "interface", "interface": selected_if_text, "network_range": subnet}
                return {"target_type": "interface", "interface": interface_combo.currentText(), "network_range": network_range_edit.text().strip()}
            # t == "custom"
            return network_range_edit.text().strip()
        
        return None

    def _handle_scan_target(self, dialog_result, scan_type):
        """Handle scan dialog results for various target types"""
        if not dialog_result:
            return False
            
        if isinstance(dialog_result, dict):
            target_type = dialog_result.get("target_type")
            if target_type == "devices":
                selected_devices = dialog_result.get("selected_devices", [])
                return self._start_batch_device_scan(selected_devices, scan_type)
            if target_type == "group":
                group = dialog_result.get("group")
                devices = self._get_group_devices(group)
                if not devices:
                    QMessageBox.warning(
                        self.main_window,
                        "No Devices in Group",
                        "The selected group has no devices to scan."
                    )
                    return False
                return self._start_batch_device_scan(devices, scan_type)
            if target_type == "interface":
                network_range = dialog_result.get("network_range", "").strip()
                if not network_range:
                    QMessageBox.warning(
                        self.main_window,
                        "Missing Network Range",
                        "Please select a valid interface with a subnet."
                    )
                    return False
                return self.scan_network(network_range, scan_type)
            
        if isinstance(dialog_result, str):
            network_range = dialog_result.strip()
            if not network_range:
                QMessageBox.warning(
                    self.main_window,
                    "Missing Network Range",
                    "Please enter a valid network range."
                )
                return False
            return self.scan_network(network_range, scan_type)
            
        return False

    @safe_action_wrapper
    def _on_scan_subnet_action(self, device_or_devices=None):
        """Handle Scan Interface Subnet action from context menu"""
        # Update the interface list
        self._update_interface_choices()
        
        selected_if_text = self.settings["preferred_interface"]["value"]
        
        # If no interface is selected or it's the "Any" option, show the dialog
        if not selected_if_text or selected_if_text == "Any (default)":
            dialog_result = self._show_scan_dialog()
        else:
            # Get the interface name
            selected_if = selected_if_text.split(":")[0].strip()
            subnet = self._get_interface_subnet(selected_if)
            
            if not subnet:
                # If we couldn't determine the subnet, show the dialog
                dialog_result = self._show_scan_dialog()
            else:
                # Show confirmation dialog
                result = QMessageBox.question(
                    self.main_window,
                    "Confirm Subnet Scan",
                    f"Do you want to scan the subnet {subnet} from interface {selected_if}?",
                    QMessageBox.Yes | QMessageBox.No
                )
                
                if result == QMessageBox.Yes:
                    dialog_result = subnet
                else:
                    dialog_result = None
        
        if dialog_result:
            # Get scan type from settings
            scan_type = self.settings["scan_type"]["value"]
            
            # Start the scan
            self._handle_scan_target(dialog_result, scan_type)
            
    @safe_action_wrapper
    def _on_rescan_device_action(self, device_or_devices):
        """Handle Rescan Selected Device action from context menu"""
        # Get the device(s)
        devices = []
        if isinstance(device_or_devices, list):
            devices = device_or_devices
        elif device_or_devices is not None:
            devices = [device_or_devices]
        else:
            # If no devices were passed, try to get selected devices from device manager
            devices = self.device_manager.get_selected_devices()
            
        # Check if we have any devices
        if not devices:
            QMessageBox.warning(
                self.main_window,
                "No Devices Selected",
                "Please select one or more devices to rescan."
            )
            return
            
        # Show scan dialog for selected devices
        dialog_result = self._show_scan_dialog(devices)

        if dialog_result:
            # Get scan type from settings
            scan_type = self.settings["scan_type"]["value"]
            self._handle_scan_target(dialog_result, scan_type)
                    
    @safe_action_wrapper
    def _on_scan_network_action(self, device_or_devices):
        """Handle Scan Network action from context menu"""
        # This action doesn't need the selected device, just show the scan dialog
        dialog_result = self._show_scan_dialog()
        
        if dialog_result:
            # Get scan type from settings
            scan_type = self.settings["scan_type"]["value"]
            
            # Start the scan
            self._handle_scan_target(dialog_result, scan_type)
            
    @safe_action_wrapper
    def _on_scan_from_device_action(self, device_or_devices):
        """Handle Scan from Selected Device action from context menu"""
        # Get the device(s)
        if isinstance(device_or_devices, list):
            if not device_or_devices:
                QMessageBox.warning(
                    self.main_window,
                    "No Device Selected",
                    "Please select a device to scan its network."
                )
                return
            device = device_or_devices[0]  # Use the first device
        else:
            device = device_or_devices
            
        if not device:
            QMessageBox.warning(
                self.main_window,
                "No Device Selected",
                "Please select a device to scan its network."
            )
            return
            
        # Get the IP address
        ip_address = device.get_property("ip_address", "")
        
        if not ip_address:
            QMessageBox.warning(
                self.main_window,
                "No IP Address",
                "The selected device does not have an IP address."
            )
            return
            
        try:
            # Parse the IP address to get the network
            ip = ipaddress.ip_address(ip_address)
            
            # For IPv4, assume /24 subnet
            if isinstance(ip, ipaddress.IPv4Address):
                network = ipaddress.IPv4Network(f"{ip_address}/24", strict=False)
                network_range = str(network)
            else:
                # For IPv6, assume /64 subnet
                network = ipaddress.IPv6Network(f"{ip_address}/64", strict=False)
                network_range = str(network)
                
            # Show the scan dialog with the device's network pre-filled
            dialog_result = self._show_scan_dialog()
            if dialog_result:
                # Get scan type from settings
                scan_type = self.settings["scan_type"]["value"]
                
                # Start the scan
                self._handle_scan_target(dialog_result, scan_type)
                
        except Exception as e:
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"Error determining network range: {e}"
            )

    def on_device_added(self, device):
        """Handle device added signal"""
        # Check if this device was added by this plugin
        if device.get_property("scan_source", "") == "nmap":
            logger.debug(f"Device added by this plugin: {device.get_property('alias')}")
            
    def on_device_removed(self, device):
        """Handle device removed signal"""
        # Nothing specific to do for removed devices
        pass
        
    def on_device_changed(self, device):
        """Handle device changed signal"""
        # Nothing specific to do for changed devices
        pass
        
    def get_settings(self):
        """Get plugin settings"""
        return self.settings
        
    def update_setting(self, setting_id, value):
        """Update a plugin setting"""
        if setting_id in self.settings:
            self.settings[setting_id]["value"] = value
            logger.debug(f"Updated setting {setting_id} to {value}")
            
            # Special handling for certain settings
            if setting_id == "scan_profiles":
                # Update the scan type choices if profiles changed
                scan_types = list(value.keys())
                self.settings["scan_type"]["choices"] = scan_types
                
            return True
        return False

    def _check_nmap_executable(self):
        """Check if the nmap executable is available in the system PATH or common installation locations
        
        Returns:
            str or None: Path to nmap executable if found, None otherwise
        """
        import subprocess
        import shutil
        import platform
        
        # List of possible nmap executable names (Windows needs .exe)
        nmap_names = ["nmap", "nmap.exe"]
        
        # Common Windows installation paths
        windows_paths = []
        if platform.system() == "Windows":
            program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
            program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
            windows_paths = [
                os.path.join(program_files, "Nmap", "nmap.exe"),
                os.path.join(program_files_x86, "Nmap", "nmap.exe"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Nmap", "nmap.exe"),
            ]
        
        # Method 1: Try shutil.which for each executable name
        for nmap_name in nmap_names:
            try:
                nmap_path = shutil.which(nmap_name)
                if nmap_path:
                    # Verify it actually works by running --version
                    if self._verify_nmap_executable(nmap_path):
                        logger.info(f"Nmap executable found at: {nmap_path}")
                        return nmap_path
            except Exception as e:
                logger.debug(f"shutil.which({nmap_name}) failed: {e}")
                continue
        
        # Method 2: Check common Windows installation paths
        for nmap_path in windows_paths:
            if os.path.exists(nmap_path) and os.path.isfile(nmap_path):
                if self._verify_nmap_executable(nmap_path):
                    logger.info(f"Nmap executable found at: {nmap_path}")
                    return nmap_path
        
        # Method 3: Try running nmap directly (fallback for PATH issues)
        # Prepare subprocess kwargs (Windows-specific flags)
        subprocess_kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "timeout": 5,  # Increased timeout
            "text": True
        }
        if platform.system() == "Windows":
            # Suppress console window on Windows
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                subprocess_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        
        for nmap_name in nmap_names:
            try:
                result = subprocess.run(
                    [nmap_name, "--version"],
                    **subprocess_kwargs
                )
                
                if result.returncode == 0:
                    version_info = result.stdout.strip().split('\n')[0] if result.stdout else "Unknown version"
                    logger.info(f"Nmap executable available: {version_info}")
                    # Try to get the full path
                    found_path = shutil.which(nmap_name)
                    if found_path:
                        return found_path
                    # If we can't get the path but it works, return the name
                    return nmap_name
            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired:
                logger.warning(f"Nmap version check timed out for {nmap_name}")
                continue
            except Exception as e:
                logger.debug(f"Error checking nmap version for {nmap_name}: {e}")
                continue
        
        logger.warning("Nmap executable not found in PATH or common installation locations")
        return None
    
    def _verify_nmap_executable(self, nmap_path):
        """Verify that an nmap executable actually works by running --version"""
        import subprocess
        import platform
        
        # Prepare subprocess kwargs (Windows-specific flags)
        subprocess_kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "timeout": 5,
            "text": True
        }
        if platform.system() == "Windows":
            # Suppress console window on Windows
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                subprocess_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        
        try:
            result = subprocess.run(
                [nmap_path, "--version"],
                **subprocess_kwargs
            )
            if result.returncode == 0:
                version_info = result.stdout.strip().split('\n')[0] if result.stdout else "Unknown"
                logger.debug(f"Verified nmap at {nmap_path}: {version_info}")
                return True
            else:
                logger.debug(f"Nmap at {nmap_path} returned non-zero exit code: {result.returncode}")
                return False
        except Exception as e:
            logger.debug(f"Failed to verify nmap at {nmap_path}: {e}")
            return False
    
    def _test_python_nmap_works(self, nmap_path):
        """Test if python-nmap can actually use nmap by trying to execute a minimal command"""
        try:
            if not HAS_NMAP:
                return False
            
            # If nmap is not in PATH, temporarily add it
            nmap_dir = os.path.dirname(nmap_path) if nmap_path else None
            original_path = None
            
            if nmap_dir and os.path.exists(nmap_dir):
                current_path = os.environ.get("PATH", "")
                if nmap_dir not in current_path.split(os.pathsep):
                    original_path = os.environ.get("PATH", "")
                    os.environ["PATH"] = nmap_dir + os.pathsep + original_path
                    logger.debug(f"Temporarily added nmap directory to PATH for testing: {nmap_dir}")
            
            try:
                # Create a test scanner
                test_scanner = nmap.PortScanner()
                
                # Try to set the nmap path if the scanner supports it
                if nmap_path and hasattr(test_scanner, 'nmap_path'):
                    test_scanner.nmap_path = nmap_path
                    logger.debug(f"Set python-nmap path to: {nmap_path}")
                
                # Try to do a minimal test - scan localhost with a very short timeout
                # This will fail fast if nmap isn't accessible, but won't take long
                # We use -sn (ping scan) on localhost which should be very fast
                try:
                    # Use a very short timeout and scan localhost only
                    # This is a minimal test that will fail quickly if nmap doesn't work
                    test_scanner.scan('127.0.0.1', arguments='-sn --max-rtt-timeout 100ms', timeout=2)
                    logger.debug("Python-nmap test scan completed successfully")
                    return True
                except nmap.PortScannerError as e:
                    # PortScannerError usually means nmap executable wasn't found or can't be executed
                    error_msg = str(e).lower()
                    if 'nmap' in error_msg and ('not found' in error_msg or 'not installed' in error_msg):
                        logger.warning(f"Python-nmap cannot find nmap executable: {e}")
                        return False
                    # Other errors might be okay (like permission issues on localhost)
                    logger.debug(f"Python-nmap test scan returned error (may be expected): {e}")
                    # If we got here, nmap was found and executed, even if the scan had issues
                    return True
                except Exception as e:
                    # Any other exception suggests nmap might not be working
                    logger.debug(f"Python-nmap test scan failed with exception: {e}")
                    # But if the scanner was created, nmap might still work for real scans
                    # Return True optimistically - the real test will be when we actually scan
                    return True
                    
            finally:
                # Restore original PATH if we modified it
                if original_path is not None:
                    os.environ["PATH"] = original_path
                    logger.debug("Restored original PATH")
                
        except Exception as e:
            logger.error(f"Failed to test python-nmap: {e}")
            return False
            
    def _get_network_interfaces(self):
        """Get a list of available network interfaces with their details"""
        interfaces = []

        # Preferred path: use psutil (pure Python interface, wheels available on most platforms)
        if not HAS_PSUTIL:
            logger.warning("psutil is not available; cannot enumerate network interfaces")
            return interfaces

        try:
            for iface, addrs in psutil.net_if_addrs().items():
                try:
                    # Skip loopback and common virtual interfaces
                    if iface == "lo" or iface.startswith("vbox") or iface.startswith("docker"):
                        continue

                    for addr in addrs:
                        # AF_INET == IPv4; use numeric literal to avoid importing socket here
                        if addr.family == 2 and addr.address and not addr.address.startswith("127."):
                            ip = addr.address
                            netmask = addr.netmask

                            # Try to get a friendly name/alias for the interface
                            interface_alias = self._get_interface_friendly_name(iface)

                            # Create interface info
                            interface_info = {
                                "name": iface,
                                "alias": interface_alias,
                                "ip": ip,
                                "netmask": netmask,
                                "display": f"{interface_alias}: {ip}",
                            }

                            # Try to get subnet in CIDR format
                            try:
                                if netmask:
                                    network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                                    interface_info["network"] = str(network)
                                    interface_info["display"] = f"{interface_alias}: {ip} ({network})"
                            except Exception as e:
                                logger.debug(f"Error calculating network for {iface}: {e}")

                            interfaces.append(interface_info)
                except Exception as e:
                    logger.debug(f"Error processing interface {iface} via psutil: {e}")
                    continue
            return interfaces
        except Exception as e:
            logger.error(f"Error getting network interfaces via psutil: {e}")

        return interfaces

    def _get_interface_friendly_name(self, interface_name):
        """Get a friendly name for the interface"""
        # This is a platform-dependent function
        try:
            import platform
            
            if platform.system() == "Windows":
                # On Windows, try to get friendly name using WMI
                try:
                    import wmi
                    c = wmi.WMI()
                    for adapter in c.Win32_NetworkAdapter():
                        if adapter.NetConnectionID and interface_name.lower() in adapter.NetConnectionID.lower():
                            return adapter.NetConnectionID
                        # Sometimes we need to match on the GUID
                        elif adapter.GUID and interface_name.lower() in adapter.GUID.lower():
                            return adapter.NetConnectionID or adapter.Name
                except Exception as e:
                    logger.debug(f"Error getting Windows interface name: {e}")
                    
                # If we couldn't get it from WMI, try some heuristics
                if "Local Area Connection" in interface_name:
                    return "Ethernet"
                elif "Wireless" in interface_name:
                    return "Wi-Fi"
                
            elif platform.system() == "Linux":
                # On Linux, try to get interface type
                if interface_name.startswith("eth"):
                    return "Ethernet"
                elif interface_name.startswith("wlan") or interface_name.startswith("wifi"):
                    return "Wi-Fi"
                elif interface_name.startswith("en"):
                    return "Ethernet"  # Modern naming scheme
                elif interface_name.startswith("wl"):
                    return "Wi-Fi"  # Modern naming scheme
            
            # If we got here, use the interface name as the alias
            return interface_name
            
        except Exception as e:
            logger.debug(f"Error getting interface friendly name: {e}")
            return interface_name
        
    def _update_interface_choices(self):
        """Update the interface choices in settings"""
        interfaces = self._get_network_interfaces()
        
        # Update the choices in settings
        if "preferred_interface" in self.settings:
            choices = [f"{iface['display']}" for iface in interfaces]
            self.settings["preferred_interface"]["choices"] = choices
            
            # Add a blank option for "any interface"
            self.settings["preferred_interface"]["choices"].insert(0, "Any (default)")
            
            # Store the interface data for later use
            self._network_interfaces = interfaces
            
        return interfaces
        
    def _get_interface_subnet(self, interface_name=None):
        """Get the subnet for the specified interface or the preferred interface"""
        # If no interface specified, use the preferred interface from settings
        if not interface_name:
            preferred = self.settings.get("preferred_interface", {}).get("value", "")
            if preferred and preferred != "Any (default)":
                # Extract interface info from the display string format: "Alias: IP (Network)"
                try:
                    # First check if we have stored interface data
                    if hasattr(self, "_network_interfaces") and self._network_interfaces:
                        # Find the interface with matching display string
                        for iface in self._network_interfaces:
                            if iface["display"] == preferred:
                                interface_name = iface["name"]
                                # If we found a match, we can return the network directly
                                if "network" in iface:
                                    return iface["network"]
                                break
                    
                    # If we didn't find it, try to extract from the display string
                    if not interface_name:
                        # Parse the interface name from the display string
                        parts = preferred.split(": ")
                        if len(parts) >= 2:
                            # Extract IP address from second part
                            ip_part = parts[1].split(" ")[0]
                            # Look for interface with this IP
                            if hasattr(self, "_network_interfaces") and self._network_interfaces:
                                for iface in self._network_interfaces:
                                    if iface["ip"] == ip_part:
                                        interface_name = iface["name"]
                                        # If we found a match, we can return the network directly
                                        if "network" in iface:
                                            return iface["network"]
                                        break
                except Exception as e:
                    logger.error(f"Error extracting interface name from {preferred}: {e}")
                    return None
        
        # If we have an interface name, find its subnet
        if interface_name:
            try:
                # Make sure we have network interface data
                if not hasattr(self, "_network_interfaces") or not self._network_interfaces:
                    # Try to update interfaces
                    logger.debug("Network interfaces not loaded, attempting to load them now")
                    self._update_interface_choices()
                
                # Search for the interface in our stored data (match by display or name;
                # interface_name is often the combo's currentText, i.e. the display string)
                for iface in getattr(self, "_network_interfaces", []):
                    if iface.get("display") == interface_name or iface.get("name") == interface_name:
                        network = iface.get('network', None)
                        if network:
                            logger.debug(f"Found subnet {network} for interface {interface_name}")
                            return network
                        else:
                            logger.debug(f"Interface {interface_name} found but has no subnet information")
                            # Try to calculate it if we have IP and netmask
                            if 'ip' in iface and 'netmask' in iface:
                                try:
                                    network = ipaddress.IPv4Network(f"{iface['ip']}/{iface['netmask']}", strict=False)
                                    logger.debug(f"Calculated subnet {network} for interface {interface_name}")
                                    return str(network)
                                except Exception as e:
                                    logger.debug(f"Error calculating network for {interface_name}: {e}")
                
                logger.debug(f"No matching interface found for {interface_name}")
            except Exception as e:
                logger.error(f"Error getting subnet for interface {interface_name}: {e}")
        
        return None

    def get_settings_pages(self):
        """Get plugin settings pages"""
        # Create main settings page (General)
        main_settings = QWidget()
        main_layout = QVBoxLayout(main_settings)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)  # Increase spacing between widgets
        
        # General settings group
        general_group = QGroupBox("General Settings")
        general_layout = QFormLayout(general_group)
        general_layout.setContentsMargins(12, 15, 12, 12)
        general_layout.setSpacing(10)  # Increase spacing between form rows
        general_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)  # Allow fields to expand
        
        # Refresh interfaces button
        refresh_interfaces_layout = QHBoxLayout()
        refresh_interfaces_layout.setSpacing(8)  # Add spacing between elements
        interface_combo = QComboBox()
        interface_combo.addItems(self.settings["preferred_interface"]["choices"])
        interface_combo.setCurrentText(self.settings["preferred_interface"]["value"])
        refresh_interfaces_button = QPushButton("Refresh")
        refresh_interfaces_button.clicked.connect(self._update_interface_choices_and_refresh_ui)
        refresh_interfaces_layout.addWidget(interface_combo, 1)  # Give the combo box more space
        refresh_interfaces_layout.addWidget(refresh_interfaces_button)
        general_layout.addRow("Preferred Interface:", refresh_interfaces_layout)
        
        # Default scan type
        scan_type_combo = QComboBox()
        scan_type_combo.addItems(self.settings["scan_type"]["choices"])
        scan_type_combo.setCurrentText(self.settings["scan_type"]["value"])
        general_layout.addRow("Default Scan Type:", scan_type_combo)
        
        # Connect changes to update settings
        interface_combo.currentTextChanged.connect(
            lambda text: self.update_setting("preferred_interface", text)
        )
        scan_type_combo.currentTextChanged.connect(
            lambda text: self.update_setting("scan_type", text)
        )
        
        main_layout.addWidget(general_group)
        
        # Advanced settings group
        advanced_group = QGroupBox("Advanced Settings")
        advanced_layout = QFormLayout(advanced_group)
        advanced_layout.setContentsMargins(12, 15, 12, 12)
        advanced_layout.setSpacing(10)  # Increase spacing between form rows
        advanced_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)  # Allow fields to expand
        
        # Elevated Permissions
        elevated_check = QCheckBox()
        elevated_check.setChecked(self.settings["use_sudo"]["value"])
        elevated_check.toggled.connect(
            lambda state: self.update_setting("use_sudo", state)
        )
        advanced_layout.addRow("Use Elevated Permissions:", elevated_check)

        # Custom Scan Arguments
        custom_args_edit = QLineEdit(self.settings["custom_scan_args"]["value"])
        custom_args_edit.textChanged.connect(
            lambda text: self.update_setting("custom_scan_args", text)
        )
        advanced_layout.addRow("Custom Arguments:", custom_args_edit)
        
        # Auto Tag
        auto_tag_check = QCheckBox()
        auto_tag_check.setChecked(self.settings["auto_tag"]["value"])
        auto_tag_check.toggled.connect(
            lambda state: self.update_setting("auto_tag", state)
        )
        advanced_layout.addRow("Auto Tag Devices:", auto_tag_check)
        
        # Batch scan threads (parallel batch scans)
        batch_threads_spin = QSpinBox()
        batch_threads_spin.setRange(1, 8)
        batch_threads_spin.setValue(max(1, min(8, int(self.settings["batch_scan_threads"]["value"] or 1))))
        batch_threads_spin.setToolTip("Number of devices to scan in parallel during batch scans. 1 = sequential.")
        batch_threads_spin.valueChanged.connect(
            lambda v: self.update_setting("batch_scan_threads", v)
        )
        advanced_layout.addRow("Batch scan threads:", batch_threads_spin)
        
        main_layout.addWidget(advanced_group)
        
        # Add a spacer at the bottom to push everything up
        main_layout.addStretch(1)
        
        # =======================================================
        # Create a separate profiles settings page
        # =======================================================
        profiles_page = QWidget()
        profiles_page_layout = QVBoxLayout(profiles_page)
        profiles_page_layout.setContentsMargins(10, 10, 10, 10)
        profiles_page_layout.setSpacing(15)  # Increase spacing between widgets
        
        # Function to refresh UI with updated interfaces
        def _update_interface_choices_and_refresh_ui():
            self._update_interface_choices()
            interface_combo.clear()
            interface_combo.addItems(self.settings["preferred_interface"]["choices"])
            interface_combo.setCurrentText(self.settings["preferred_interface"]["value"])
        
        # Explanation label with better styling
        explanation_label = QLabel(
            "Scan profiles define different scanning configurations. "
            "Select a profile to view or edit its settings, or create a new profile."
        )
        explanation_label.setWordWrap(True)
        explanation_label.setStyleSheet("padding: 8px; background-color: #f0f0f0; border-radius: 4px;")
        profiles_page_layout.addWidget(explanation_label)
        
        # Profiles management section
        profiles_section = QWidget()
        profiles_section_layout = QVBoxLayout(profiles_section)
        profiles_section_layout.setContentsMargins(0, 0, 0, 0)
        profiles_section_layout.setSpacing(12)
        
        # Profiles list with Add New option
        profiles_list_layout = QHBoxLayout()
        profiles_list_layout.setSpacing(10)
        profiles_list = QComboBox()
        
        # Add all profiles plus a special "Add New..." option
        profile_keys = list(self.settings["scan_profiles"]["value"].keys())
        profiles_list.addItems(profile_keys)
        profiles_list.addItem("--- Add New Profile ---")
        
        profiles_list_layout.addWidget(QLabel("Select Profile:"))
        profiles_list_layout.addWidget(profiles_list, 1)  # Give it stretch factor
        profiles_section_layout.addLayout(profiles_list_layout)
        
        # Profile details form
        profile_details_group = QGroupBox("Profile Details")
        profile_form = QFormLayout(profile_details_group)
        profile_form.setContentsMargins(12, 15, 12, 12)
        profile_form.setSpacing(10)  # Increase spacing between form rows
        profile_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)  # Allow fields to expand
        
        profile_name = QLineEdit()
        profile_form.addRow("Display Name:", profile_name)
        
        profile_desc = QLineEdit()
        profile_desc.setPlaceholderText("Description of the scan profile")
        profile_form.addRow("Description:", profile_desc)
        
        profile_args = QLineEdit()
        profile_args.setPlaceholderText("nmap arguments, e.g. -sn -F")
        profile_form.addRow("Arguments:", profile_args)
        
        profile_timeout = QLineEdit()
        profile_timeout.setValidator(QIntValidator(30, 600))
        profile_form.addRow("Timeout (seconds):", profile_timeout)
        
        profiles_section_layout.addWidget(profile_details_group)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        save_button = QPushButton("Save Profile")
        delete_button = QPushButton("Delete Profile")
        
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(delete_button)
        
        profiles_section_layout.addLayout(buttons_layout)
        
        # Add the profiles section to the profiles page
        profiles_page_layout.addWidget(profiles_section)
        profiles_page_layout.addStretch()
        
        # Function to load profile data
        def load_profile_data():
            profile_id = profiles_list.currentText()
            
            # Handle special "Add New Profile" option
            if profile_id == "--- Add New Profile ---":
                # Clear the form for a new profile
                profile_name.setText("")
                profile_desc.setText("")
                profile_args.setText("-sn")  # Default args for new profile
                profile_timeout.setText("300")
                
                # Disable delete button, enable other fields
                delete_button.setEnabled(False)
                profile_name.setEnabled(True)
                profile_desc.setEnabled(True)
                profile_args.setEnabled(True)
                profile_timeout.setEnabled(True)
                save_button.setText("Create Profile")
                profile_details_group.setTitle("New Profile Details")
                return
                
            # Regular profile selected    
            if profile_id in self.settings["scan_profiles"]["value"]:
                profile = self.settings["scan_profiles"]["value"][profile_id]
                
                profile_name.setText(profile.get("name", profile_id))
                profile_desc.setText(profile.get("description", ""))
                profile_args.setText(profile.get("arguments", ""))
                profile_timeout.setText(str(profile.get("timeout", 300)))
                
                # Disable delete for built-in profiles
                is_builtin = profile_id in ["quick", "standard", "comprehensive", "stealth", "service"]
                delete_button.setEnabled(not is_builtin)
                
                # Enable all fields
                profile_name.setEnabled(True)
                profile_desc.setEnabled(True)
                profile_args.setEnabled(True)
                profile_timeout.setEnabled(True)
                save_button.setText("Update Profile")
                profile_details_group.setTitle("Edit Profile Details")
                
        # Connect profile selection to load data
        profiles_list.currentTextChanged.connect(load_profile_data)
        
        # Initial load
        load_profile_data()
        
        # Function to save profile (both update and create)
        def save_profile():
            profile_id = profiles_list.currentText()
            
            if profile_id == "--- Add New Profile ---":
                # This is a new profile, ask for an ID
                new_id, ok = QInputDialog.getText(
                    profiles_page,
                    "New Profile",
                    "Enter a unique profile ID (lowercase, no spaces):",
                    text="custom_scan"  # Default suggestion
                )
                
                if not ok or not new_id:
                    return
                
                # Validate ID (lowercase, no spaces, etc.)
                new_id = new_id.lower().strip().replace(" ", "_")
                
                # Check if ID already exists
                if new_id in self.settings["scan_profiles"]["value"]:
                    QMessageBox.warning(
                        profiles_page,
                        "Profile Exists",
                        f"A profile with ID '{new_id}' already exists. Please choose a different ID."
                    )
                    return
                
                profile_id = new_id
            
            # Get values from form
            name = profile_name.text()
            description = profile_desc.text()
            arguments = profile_args.text()
            
            # Validate timeout
            try:
                timeout = int(profile_timeout.text())
                if timeout < 30:
                    timeout = 30
                elif timeout > 600:
                    timeout = 600
            except ValueError:
                timeout = 300
            
            # Prepare updated/new profile
            updated_profile = {
                "name": name,
                "description": description,
                "arguments": arguments,
                "timeout": timeout
            }
            
            # Update or add the profile in settings
            profiles = self.settings["scan_profiles"]["value"].copy()
            profiles[profile_id] = updated_profile
            self.update_setting("scan_profiles", profiles)
            
            # Update scan type choices if needed
            if profile_id not in self.settings["scan_type"]["choices"]:
                choices = list(self.settings["scan_type"]["choices"])
                choices.append(profile_id)
                self.settings["scan_type"]["choices"] = choices
                scan_type_combo.clear()
                scan_type_combo.addItems(choices)
                
            # Update UI
            current_index = profiles_list.findText(profile_id)
            if current_index == -1:  # Not found
                # This was a new profile, refresh the list
                profiles_list.clear()
                all_profiles = list(self.settings["scan_profiles"]["value"].keys())
                profiles_list.addItems(all_profiles)
                profiles_list.addItem("--- Add New Profile ---")
                profiles_list.setCurrentText(profile_id)
            
            # Show confirmation
            action = "created" if profile_id != profiles_list.currentText() else "updated"
            QMessageBox.information(
                profiles_page,
                "Profile Saved",
                f"The profile '{profile_id}' has been {action}."
            )
            
        # Function to delete profile
        def delete_profile():
            profile_id = profiles_list.currentText()
            
            # Prevent deletion of built-in profiles
            if profile_id in ["quick", "standard", "comprehensive", "stealth", "service"]:
                QMessageBox.warning(
                    profiles_page,
                    "Cannot Delete",
                    "Built-in profiles cannot be deleted."
                )
                return
                
            # Don't try to delete "Add New Profile" option
            if profile_id == "--- Add New Profile ---":
                return
                
            # Confirm deletion
            result = QMessageBox.question(
                profiles_page,
                "Confirm Deletion",
                f"Are you sure you want to delete the profile '{profile_id}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if result == QMessageBox.Yes:
                # Remove from settings
                profiles = self.settings["scan_profiles"]["value"].copy()
                if profile_id in profiles:
                    del profiles[profile_id]
                    self.update_setting("scan_profiles", profiles)
                    
                    # Remove from choices if present
                    if profile_id in self.settings["scan_type"]["choices"]:
                        choices = list(self.settings["scan_type"]["choices"])
                        choices.remove(profile_id)
                        self.settings["scan_type"]["choices"] = choices
                        scan_type_combo.clear()
                        scan_type_combo.addItems(choices)
                    
                    # Update UI
                    profiles_list.clear()
                    all_profiles = list(self.settings["scan_profiles"]["value"].keys())
                    profiles_list.addItems(all_profiles)
                    profiles_list.addItem("--- Add New Profile ---")
                    
                    # Show confirmation
                    QMessageBox.information(
                        profiles_page,
                        "Profile Deleted",
                        f"The profile '{profile_id}' has been deleted."
                    )
        
        # Connect button actions
        save_button.clicked.connect(save_profile)
        delete_button.clicked.connect(delete_profile)
        
        # Return both settings pages
        return [("General", main_settings), ("Scan Profiles", profiles_page)]

    def _update_interface_choices_and_refresh_ui(self):
        """Update interface choices and refresh the UI"""
        try:
            # Update the interface choices
            interfaces = self._update_interface_choices()
            
            # Update the UI combobox if it exists
            if hasattr(self, "interface_combo") and self.interface_combo is not None:
                # Remember current selection to restore it if possible
                current_selection = self.interface_combo.currentText()
                
                # Clear and repopulate
                self.interface_combo.clear()
                self.interface_combo.addItems(self.settings["preferred_interface"]["choices"])
                
                # Try to restore previous selection, otherwise use the default
                if current_selection and current_selection in self.settings["preferred_interface"]["choices"]:
                    self.interface_combo.setCurrentText(current_selection)
                elif self.settings["preferred_interface"]["value"] in self.settings["preferred_interface"]["choices"]:
                    self.interface_combo.setCurrentText(self.settings["preferred_interface"]["value"])
                
                # Log the update
                logger.debug(f"Updated interface list, found {len(interfaces)} interfaces")
                
                # Update network range based on selected interface
                self._update_network_range_from_interface(self.interface_combo.currentIndex())
                
            return True
        except Exception as e:
            logger.error(f"Error updating interface choices: {e}")
            return False

    def _update_network_range_from_interface(self, index):
        """Update network range based on selected interface"""
        try:
            # Check if the UI elements exist
            if not hasattr(self, "interface_combo") or not hasattr(self, "network_range_edit"):
                logger.debug("UI elements not yet created, skipping network range update")
                return
            
            selected_if_text = self.interface_combo.currentText()
            
            # Skip "Any (default)" option
            if not selected_if_text or selected_if_text == "Any (default)":
                logger.debug("No specific interface selected, not updating network range")
                return
            
            # Log the selected interface for debugging
            logger.debug(f"Updating network range from selected interface: {selected_if_text}")
                
            # Try to directly find the network from stored interface data
            if hasattr(self, "_network_interfaces") and self._network_interfaces:
                for iface in self._network_interfaces:
                    if iface["display"] == selected_if_text:
                        # Check if network information is available
                        if "network" in iface:
                            network = iface["network"]
                            self.network_range_edit.setText(network)
                            logger.debug(f"Updated network range to {network} from interface {iface['alias']}")
                            return True
                        # Try IP with netmask
                        elif "ip" in iface and "netmask" in iface:
                            try:
                                network = ipaddress.IPv4Network(f"{iface['ip']}/{iface['netmask']}", strict=False)
                                network_str = str(network)
                                self.network_range_edit.setText(network_str)
                                logger.debug(f"Updated network range to {network_str} from interface {iface['alias']}")
                                return True
                            except Exception as e:
                                logger.debug(f"Error calculating network for {iface['alias']}: {e}")

            # If we get here, try getting the subnet using the standard method as fallback
            subnet = self._get_interface_subnet(selected_if_text)
            
            if subnet:
                # Set the network range text field and log it
                self.network_range_edit.setText(subnet)
                logger.debug(f"Updated network range to {subnet} from interface")
                return True
            else:
                logger.warning(f"Could not determine subnet for interface {selected_if_text}")
        
            # If no subnet was found from interface, try to get one from local IP
            try:
                import socket
                hostname = socket.gethostname()
                ip_address = socket.gethostbyname(hostname)
                network = ipaddress.IPv4Network(f"{ip_address}/24", strict=False)
                self.network_range_edit.setText(str(network))
                logger.debug(f"Used default network {network} from local IP {ip_address}")
                return True
            except Exception as e:
                logger.debug(f"Error determining default network range: {e}")
        except Exception as e:
            logger.error(f"Error updating network range from interface: {e}")
            
        return False

    def _refresh_group_choices(self):
        """Refresh the group selection dropdown"""
        if not hasattr(self, "device_manager") or not self.device_manager:
            return
        if not hasattr(self, "group_combo") or self.group_combo is None:
            return
            
        current_group = self.group_combo.currentData() if self.group_combo.count() else None
        current_name = current_group.name if current_group else None
        
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        
        root_group = self.device_manager.root_group
        self.group_combo.addItem("All Devices", root_group)
        
        groups = [g for g in self.device_manager.get_groups() if g != root_group]
        groups.sort(key=lambda g: self._format_group_path(g).lower())
        for group in groups:
            label = self._format_group_path(group)
            self.group_combo.addItem(label, group)
        
        # Restore previous selection if possible
        if current_name:
            for index in range(self.group_combo.count()):
                group = self.group_combo.itemData(index)
                if group and group.name == current_name:
                    self.group_combo.setCurrentIndex(index)
                    break
        
        self.group_combo.blockSignals(False)

    def _format_group_path(self, group):
        """Return a display path for a group"""
        parts = [group.name]
        parent = group.parent
        while parent and parent != self.device_manager.root_group:
            parts.append(parent.name)
            parent = parent.parent
        parts.reverse()
        return " / ".join(parts)

    def _update_group_scan_ui_state(self):
        """Toggle UI state when group scan is enabled (deprecated - now handled by radio buttons)"""
        # This method is kept for backward compatibility but functionality
        # is now handled by the update_target_ui_state function in _create_widgets
        pass

    def _get_selected_group(self):
        """Return the selected group from the UI"""
        if not hasattr(self, "group_combo") or self.group_combo.count() == 0:
            return None
        return self.group_combo.currentData()

    def _get_group_devices(self, group):
        """Return devices for a group including subgroups"""
        if not group:
            return []
        try:
            return group.get_all_devices()
        except Exception:
            return []

    def _get_group_ip_list(self, group):
        """Return a list of IPs for devices in the group"""
        devices = self._get_group_devices(group)
        ip_list = []
        for device in devices:
            ip = device.get_property("ip_address", "") if hasattr(device, "get_property") else ""
            if ip:
                ip_list.append(ip)
        # De-duplicate while preserving order
        seen = set()
        unique_ips = []
        for ip in ip_list:
            if ip in seen:
                continue
            seen.add(ip)
            unique_ips.append(ip)
        return unique_ips
    
    def _update_selected_devices_ui(self):
        """Update the selected devices UI when device selection changes. Adds/removes/updates
        the 'Selected Devices (N)' item in target_combo and keeps the label in sync."""
        if not hasattr(self, "target_combo") or not hasattr(self, "selected_devices_label"):
            return
        
        if not getattr(self, "device_manager", None):
            self._remove_target_combo_devices_item()
            self.selected_devices_label.setText("Device manager unavailable")
            self.selected_devices_label.setStyleSheet("color: gray; font-style: italic;")
            self.selected_devices_label.setVisible(False)
            return
        
        selected_devices = self.device_manager.get_selected_devices()
        
        if selected_devices:
            # Filter devices with IP addresses
            devices_with_ips = [d for d in selected_devices 
                              if (d.get_property("ip_address", "") if hasattr(d, "get_property") else "")]
            count = len(devices_with_ips)
            
            if count > 0:
                self._set_target_combo_devices_item(count)
                device_names = []
                for device in devices_with_ips[:5]:  # Show first 5
                    name = device.get_property("alias", "") if hasattr(device, "get_property") else ""
                    ip = device.get_property("ip_address", "") if hasattr(device, "get_property") else ""
                    if name and ip:
                        device_names.append(f"{name} ({ip})")
                    elif ip:
                        device_names.append(ip)
                    elif name:
                        device_names.append(name)
                
                if count > 5:
                    device_names.append(f"... and {count - 5} more")
                
                self.selected_devices_label.setText(f"Selected: {', '.join(device_names)}")
                self.selected_devices_label.setStyleSheet("color: black; font-style: normal;")
                target = self.target_combo.currentData() if self.target_combo.currentData() is not None else "interface"
                self.selected_devices_label.setVisible(target == "devices")
            else:
                self._remove_target_combo_devices_item()
                self.selected_devices_label.setText("Selected devices have no IP addresses")
                self.selected_devices_label.setStyleSheet("color: orange; font-style: italic;")
                self.selected_devices_label.setVisible(True)
        else:
            self._remove_target_combo_devices_item()
            self.selected_devices_label.setText("No devices selected")
            self.selected_devices_label.setStyleSheet("color: gray; font-style: italic;")
            self.selected_devices_label.setVisible(False)
    
    def _target_combo_devices_index(self):
        """Return the index of the 'Selected Devices' item in target_combo, or -1."""
        for i in range(self.target_combo.count()):
            if self.target_combo.itemData(i) == "devices":
                return i
        return -1
    
    def _set_target_combo_devices_item(self, count):
        """Add or update the 'Selected Devices (N)' item; if current selection was devices, keep it selected."""
        idx = self._target_combo_devices_index()
        text = f"Selected Devices ({count})"
        if idx >= 0:
            self.target_combo.setItemText(idx, text)
        else:
            self.target_combo.addItem(text, "devices")
    
    def _remove_target_combo_devices_item(self):
        """Remove the 'Selected Devices' item; if it was selected, switch to Interface Subnet."""
        idx = self._target_combo_devices_index()
        if idx < 0:
            return
        was_current = (self.target_combo.currentIndex() == idx)
        self.target_combo.removeItem(idx)
        if was_current:
            self.target_combo.setCurrentIndex(0)  # Interface Subnet
        # Refresh visibility/enable from new selection
        target = self.target_combo.currentData() if self.target_combo.currentData() is not None else "interface"
        self.network_range_edit.setEnabled(target == "custom")
        self.selected_devices_label.setVisible(target == "devices")
    
    def on_device_selected(self, devices):
        """Handle device selection changed signal"""
        self._update_selected_devices_ui()

    @safe_action_wrapper
    def on_scan_type_manager_action(self):
        """Handle scan type manager action"""
        self._show_scan_type_manager_dialog()
        
    def _show_scan_type_manager_dialog(self):
        """Show the scan type manager dialog"""
        dialog = QDialog(self.main_window)
        mark_plugin_ui(dialog)
        dialog.setWindowTitle("Scan Type Manager")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(500)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        
        # Add description
        description_label = QLabel(
            "Manage your scan profiles. You can create new profiles, edit existing ones, or delete custom profiles."
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet("padding: 8px; background-color: #f0f0f0; border-radius: 4px;")
        layout.addWidget(description_label)
        
        # Create a table to display profiles
        profile_table = QTableWidget()
        profile_table.setColumnCount(3)
        profile_table.setHorizontalHeaderLabels(["Name", "Description", "Arguments"])
        profile_table.horizontalHeader().setStretchLastSection(True)
        profile_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        profile_table.setSelectionBehavior(QTableWidget.SelectRows)
        profile_table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(profile_table)
        
        # Function to refresh the table
        def refresh_table():
            profile_table.setRowCount(0)
            profiles = self.settings["scan_profiles"]["value"]
            
            for i, (profile_id, profile) in enumerate(profiles.items()):
                is_builtin = profile_id in ["quick", "standard", "comprehensive", "stealth", "service"]
                
                profile_table.insertRow(i)
                
                # Name column
                name_item = QTableWidgetItem(profile.get("name", profile_id))
                if is_builtin:
                    name_item.setToolTip("Built-in profile (can't be deleted)")
                    # Set a background color for built-in profiles
                    name_item.setBackground(QColor("#f0f0f0"))
                name_item.setData(Qt.UserRole, profile_id)  # Store profile ID
                profile_table.setItem(i, 0, name_item)
                
                # Description column
                profile_table.setItem(i, 1, QTableWidgetItem(profile.get("description", "")))
                
                # Arguments column
                profile_table.setItem(i, 2, QTableWidgetItem(profile.get("arguments", "")))
                
            profile_table.resizeColumnsToContents()
            # Ensure description column gets some minimum width
            if profile_table.columnWidth(1) < 150:
                profile_table.setColumnWidth(1, 150)
        
        # First populate the table
        refresh_table()
        
        # Button layout
        button_layout = QHBoxLayout()
        new_button = QPushButton("New Profile")
        edit_button = QPushButton("Edit Profile")
        delete_button = QPushButton("Delete Profile")
        # Initially disable edit/delete until a row is selected
        edit_button.setEnabled(False)
        delete_button.setEnabled(False)
        
        button_layout.addWidget(new_button)
        button_layout.addWidget(edit_button)
        button_layout.addWidget(delete_button)
        button_layout.addStretch(1)
        
        layout.addLayout(button_layout)
        
        # Add dialog buttons
        dialog_buttons = QDialogButtonBox(QDialogButtonBox.Close)
        dialog_buttons.rejected.connect(dialog.reject)
        layout.addWidget(dialog_buttons)
        
        # Handle selection change
        def on_selection_changed():
            selected_indexes = profile_table.selectedIndexes()
            if selected_indexes:
                row = selected_indexes[0].row()
                profile_id = profile_table.item(row, 0).data(Qt.UserRole)
                is_builtin = profile_id in ["quick", "standard", "comprehensive", "stealth", "service"]
                
                edit_button.setEnabled(True)
                delete_button.setEnabled(not is_builtin)
            else:
                edit_button.setEnabled(False)
                delete_button.setEnabled(False)
        
        profile_table.itemSelectionChanged.connect(on_selection_changed)
        
        # Show edit dialog for a profile
        def edit_profile_dialog(profile_id=None, is_new=False):
            edit_dialog = QDialog(dialog)
            mark_plugin_ui(edit_dialog)
            edit_dialog.setWindowTitle("New Scan Profile" if is_new else "Edit Scan Profile")
            edit_dialog.setMinimumWidth(450)
            
            edit_layout = QVBoxLayout(edit_dialog)
            
            # Form layout
            form_layout = QFormLayout()
            form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
            
            # Profile ID (for new profiles only)
            profile_id_edit = QLineEdit()
            if is_new:
                form_layout.addRow("Profile ID:", profile_id_edit)
                profile_id_edit.setPlaceholderText("e.g., custom_scan (no spaces, lowercase)")
            
            # Name
            profile_name_edit = QLineEdit()
            form_layout.addRow("Display Name:", profile_name_edit)
            
            # Description
            profile_desc_edit = QLineEdit()
            form_layout.addRow("Description:", profile_desc_edit)
            
            # Arguments
            profile_args_edit = QLineEdit()
            form_layout.addRow("Arguments:", profile_args_edit)
            profile_args_edit.setPlaceholderText("e.g., -sn -F")
            
            # Timeout
            profile_timeout_edit = QLineEdit()
            profile_timeout_edit.setValidator(QIntValidator(30, 600))
            form_layout.addRow("Timeout (seconds):", profile_timeout_edit)
            
            # If editing, populate with existing values
            if not is_new and profile_id:
                profile = self.settings["scan_profiles"]["value"].get(profile_id, {})
                profile_name_edit.setText(profile.get("name", ""))
                profile_desc_edit.setText(profile.get("description", ""))
                profile_args_edit.setText(profile.get("arguments", ""))
                profile_timeout_edit.setText(str(profile.get("timeout", 300)))
            
            edit_layout.addLayout(form_layout)
            
            # Add dialog buttons
            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            button_box.accepted.connect(edit_dialog.accept)
            button_box.rejected.connect(edit_dialog.reject)
            edit_layout.addWidget(button_box)
            
            # Show dialog and handle result
            if edit_dialog.exec() == QDialog.Accepted:
                # Get values from form
                if is_new:
                    new_id = profile_id_edit.text().strip().lower().replace(" ", "_")
                    if not new_id:
                        QMessageBox.warning(dialog, "Invalid ID", "Profile ID cannot be empty.")
                        return
                    
                    # Check if ID exists
                    if new_id in self.settings["scan_profiles"]["value"]:
                        QMessageBox.warning(dialog, "Profile Exists", f"A profile with ID '{new_id}' already exists.")
                        return
                    
                    profile_id = new_id
                
                # Create updated profile
                updated_profile = {
                    "name": profile_name_edit.text(),
                    "description": profile_desc_edit.text(),
                    "arguments": profile_args_edit.text(),
                    "timeout": int(profile_timeout_edit.text() or "300")
                }
                
                # Update settings
                profiles = self.settings["scan_profiles"]["value"].copy()
                profiles[profile_id] = updated_profile
                self.settings["scan_profiles"]["value"] = profiles
                
                # Update scan type choices if needed
                if profile_id not in self.settings["scan_type"]["choices"]:
                    choices = list(self.settings["scan_type"]["choices"])
                    choices.append(profile_id)
                    self.settings["scan_type"]["choices"] = choices
                    
                    # Update the scan type combo box
                    if hasattr(self, "scan_type_combo") and self.scan_type_combo is not None:
                        current_text = self.scan_type_combo.currentText()
                        self.scan_type_combo.clear()
                        self.scan_type_combo.addItems(choices)
                        # Restore selection if possible
                        if current_text in choices:
                            self.scan_type_combo.setCurrentText(current_text)
                
                # Refresh the table
                refresh_table()
                
                return True
            
            return False
            
        # Handle new profile button
        def on_new_profile():
            edit_profile_dialog(is_new=True)
            
        # Handle edit profile button
        def on_edit_profile():
            selected_indexes = profile_table.selectedIndexes()
            if not selected_indexes:
                return
                
            row = selected_indexes[0].row()
            profile_id = profile_table.item(row, 0).data(Qt.UserRole)
            
            edit_profile_dialog(profile_id, is_new=False)
            
        # Handle delete profile button
        def on_delete_profile():
            selected_indexes = profile_table.selectedIndexes()
            if not selected_indexes:
                return
                
            row = selected_indexes[0].row()
            profile_id = profile_table.item(row, 0).data(Qt.UserRole)
            
            # Check if built-in
            if profile_id in ["quick", "standard", "comprehensive", "stealth", "service"]:
                QMessageBox.warning(dialog, "Cannot Delete", "Built-in profiles cannot be deleted.")
                return
                
            # Confirm deletion
            result = QMessageBox.question(
                dialog, 
                "Confirm Deletion",
                f"Are you sure you want to delete the profile '{profile_id}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if result == QMessageBox.Yes:
                # Delete the profile
                profiles = self.settings["scan_profiles"]["value"].copy()
                if profile_id in profiles:
                    del profiles[profile_id]
                
                # Update settings
                self.settings["scan_profiles"]["value"] = profiles
                
                # Remove from choices if present
                if profile_id in self.settings["scan_type"]["choices"]:
                    choices = list(self.settings["scan_type"]["choices"])
                    choices.remove(profile_id)
                    self.settings["scan_type"]["choices"] = choices
                    
                    # Update the scan type combo box
                    if hasattr(self, "scan_type_combo") and self.scan_type_combo is not None:
                        current_text = self.scan_type_combo.currentText()
                        self.scan_type_combo.clear()
                        self.scan_type_combo.addItems(choices)
                        # Restore selection if possible, otherwise select first
                        if current_text in choices:
                            self.scan_type_combo.setCurrentText(current_text)
                        elif choices:
                            self.scan_type_combo.setCurrentIndex(0)
                        # Trigger description update
                        if self.scan_type_combo.count() > 0:
                            self.scan_type_combo.currentIndexChanged.emit(self.scan_type_combo.currentIndex())
                
                # Refresh the table
                refresh_table()
        
        # Connect button signals
        new_button.clicked.connect(on_new_profile)
        edit_button.clicked.connect(on_edit_profile)
        delete_button.clicked.connect(on_delete_profile)
        
        # Allow double-click to edit
        def on_double_click(item):
            row = item.row()
            profile_id = profile_table.item(row, 0).data(Qt.UserRole)
            edit_profile_dialog(profile_id, is_new=False)
            
        profile_table.itemDoubleClicked.connect(on_double_click)
        
        # Show the dialog
        dialog.exec_()

    def quick_ping_scan(self, network_range, display_label=None):
        """
        Perform a quick ping scan using system commands
        
        This provides an alternative to nmap for fast scanning, especially
        when just checking if hosts are alive.
        
        Args:
            network_range: Network range or list of IPs to scan
            display_label: Optional label for logging/status
            
        Returns:
            bool: True if scan started successfully, False otherwise
        """
        # Check if already scanning
        if self._is_scanning:
            logger.warning("Scan already in progress")
            return False
            
        # Clean up any previous scan
        self._cleanup_previous_scan()
        
        # Convert network range to list of IPs to ping
        try:
            import ipaddress
            import subprocess
            import threading
            import platform
            from PySide6.QtCore import QObject, Signal, QThread
            
            # Create a worker object with signals for thread-safe UI updates
            class PingScanWorker(QObject):
                progress_updated = Signal(int, int)  # current, total
                status_updated = Signal(str)  # status message
                device_found = Signal(dict)  # device data
                scan_complete = Signal(dict)  # scan results
                
                def __init__(self, ip_list, network_range):
                    super().__init__()
                    self.ip_list = ip_list
                    self.network_range = network_range
                    self.should_stop = False
                    
                def stop(self):
                    self.should_stop = True
                    
                def run(self):
                    self._run_scan()
                    
                def _ping_host(self, ip, index):
                    if self.should_stop:
                        return
                        
                    # Determine ping command based on OS
                    system = platform.system().lower()
                    if system == "windows":
                        ping_cmd = ["ping", "-n", "1", "-w", "500", str(ip)]
                        ping_success = lambda proc: proc.returncode == 0
                    else:  # Linux and macOS
                        ping_cmd = ["ping", "-c", "1", "-W", "1", str(ip)]
                        ping_success = lambda proc: proc.returncode == 0
                        
                    try:
                        # Execute ping command
                        proc = subprocess.run(
                            ping_cmd, 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE,
                            timeout=1
                        )
                        
                        # Check result
                        if ping_success(proc):
                            # Log success
                            self.status_updated.emit(f"Host {ip} is up")
                            
                            # Create device data
                            host_data = {
                                "ip_address": str(ip),
                                "scan_source": "ping",
                                "alias": f"Device at {ip}",
                                "tags": ["scanned", "ping"]
                            }
                            
                            # Try to get hostname
                            try:
                                import socket
                                hostname = socket.getfqdn(str(ip))
                                if hostname and hostname != str(ip):
                                    host_data["hostname"] = hostname
                                    host_data["alias"] = hostname
                            except Exception:
                                pass
                                
                            # Emit device found signal
                            self.device_found.emit(host_data)
                        else:
                            # Host is not up, don't add it
                            logger.debug(f"Host {ip} did not respond to ping")
                            
                    except Exception as e:
                        logger.debug(f"Error pinging {ip}: {e}")
                        
                    finally:
                        # Update progress through signal
                        if not self.should_stop:
                            self.progress_updated.emit(index + 1, len(self.ip_list))
                            
                def _run_scan(self):
                    start_time = time.time()
                    alive_hosts = []
                    threads = []
                    max_concurrent = min(50, len(self.ip_list))  # Limit concurrent threads
                    
                    try:
                        for i, ip in enumerate(self.ip_list):
                            if self.should_stop:
                                break
                                
                            # Create and start thread
                            t = threading.Thread(target=self._ping_host, args=(ip, i))
                            t.daemon = True
                            threads.append(t)
                            t.start()
                            
                            # Limit concurrent threads
                            while len([t for t in threads if t.is_alive()]) >= max_concurrent:
                                time.sleep(0.01)
                                
                            # Update status periodically
                            if i % 10 == 0:
                                self.status_updated.emit(f"Scanned {i} of {len(self.ip_list)} addresses...")
                                
                        # Wait for all threads to complete
                        for t in threads:
                            if self.should_stop:
                                break
                            t.join(timeout=0.5)
                            
                        # Scan complete
                        scan_time = time.time() - start_time
                        self.status_updated.emit(f"Scan complete: Found {len(alive_hosts)} devices in {round(scan_time, 1)} seconds")
                        
                        # Store results
                        scan_results = {
                            "network_range": self.network_range,
                            "scan_type": "quick_ping",
                            "total_hosts": len(self.ip_list),
                            "devices_found": len(alive_hosts),
                            "scan_time": scan_time,
                            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        # Emit scan complete signal
                        self.scan_complete.emit(scan_results)
                        
                    except Exception as e:
                        logger.error(f"Error during ping scan: {e}")
                        self.status_updated.emit(f"Error during scan: {e}")
            
            # Set scanning flag
            self._is_scanning = True
            self._update_scan_button_state()
            if hasattr(self, "progress_bar") and self.progress_bar:
                self.progress_bar.setValue(0)
                self.progress_bar.setVisible(True)
            
            # Clear the scan log and reset progress
            self._scan_log = []
            label = display_label or (network_range if isinstance(network_range, str) else "Selected devices")
            self.log_message(f"Starting quick ping scan of {label}")
            self._scan_results = {}
            
            # Extract IP addresses from network range or list
            ip_list = []
            try:
                if isinstance(network_range, (list, tuple, set)):
                    for entry in network_range:
                        if not entry:
                            continue
                        try:
                            ip_list.append(ipaddress.ip_address(str(entry)))
                        except Exception:
                            continue
                else:
                    # For CIDR notation like 192.168.1.0/24
                    if '/' in network_range:
                        net = ipaddress.ip_network(network_range, strict=False)
                        ip_list = list(net.hosts())
                        
                    # For range notation like 192.168.1.1-10
                    elif '-' in network_range:
                        parts = network_range.split('-')
                        if len(parts) == 2:
                            start_ip = parts[0].strip()
                            
                            # Check if the second part is a full IP or just the last octet
                            if '.' in parts[1]:
                                end_ip = parts[1].strip()
                            else:
                                # Assume it's just the last octet
                                start_parts = start_ip.split('.')
                                end_ip = f"{start_parts[0]}.{start_parts[1]}.{start_parts[2]}.{parts[1].strip()}"
                                
                            # Generate IP range
                            start = int(ipaddress.IPv4Address(start_ip))
                            end = int(ipaddress.IPv4Address(end_ip))
                            
                            for i in range(start, end + 1):
                                ip_list.append(ipaddress.IPv4Address(i))
                    
                    # Single IP address
                    else:
                        ip_list = [ipaddress.ip_address(network_range)]
            except Exception as e:
                self.log_message(f"Error parsing network range: {e}")
                self._is_scanning = False
                return False
                
            if not ip_list:
                self.log_message("No valid IP addresses to scan")
                self._is_scanning = False
                return False
                
            self.log_message(f"Scanning {len(ip_list)} addresses...")
            
            # Update progress bar
            if hasattr(self, "progress_bar") and self.progress_bar:
                self.progress_bar.setRange(0, len(ip_list))
                self.progress_bar.setValue(0)
            
            # Create worker thread
            self._ping_scan_thread = QThread()
            self._ping_scan_worker = PingScanWorker(ip_list, label)
            self._ping_scan_worker.moveToThread(self._ping_scan_thread)
            
            # Connect worker signals
            self._ping_scan_worker.progress_updated.connect(self._on_ping_scan_progress)
            self._ping_scan_worker.status_updated.connect(self.log_message)
            self._ping_scan_worker.device_found.connect(self._on_device_found)
            self._ping_scan_worker.scan_complete.connect(self._on_ping_scan_complete)
            
            # Connect thread signals
            self._ping_scan_thread.started.connect(self._ping_scan_worker.run)
            
            # Start the worker thread
            self._ping_scan_thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting ping scan: {e}")
            self._is_scanning = False
            self.log_message(f"Error starting scan: {e}")
            return False
            
    def _on_ping_scan_progress(self, current, total):
        """Handle ping scan progress updates in a thread-safe way"""
        if hasattr(self, "progress_bar") and self.progress_bar:
            self.progress_bar.setValue(current)
            
        if hasattr(self, "status_label") and self.status_label:
            percentage = int((current / total) * 100) if total > 0 else 0
            self.status_label.setText(f"Scanning: {current}/{total} ({percentage}%)")
            
    def _on_ping_scan_complete(self, results):
        """Handle ping scan completion in a thread-safe way"""
        self._is_scanning = False
        self._scan_results = results
        self._update_scan_button_state()
        # Update status
        if hasattr(self, "status_label"):
            self.status_label.setText("Scan complete")
            
        # Set progress to 100%
        if hasattr(self, "progress_bar"):
            self.progress_bar.setValue(self.progress_bar.maximum())
            
        # Clean up thread
        if hasattr(self, "_ping_scan_thread") and self._ping_scan_thread.isRunning():
            self._ping_scan_thread.quit()
            self._ping_scan_thread.wait(1000)
            
        # Emit the scan completed signal
        self.scan_completed.emit(results)
            
    def stop_ping_scan(self):
        """Stop the ping scan if it's running"""
        if hasattr(self, "_ping_scan_worker"):
            self._ping_scan_worker.stop()
            self.log_message("Stopping ping scan...")
            return True
        return False

# Create plugin instance (will be loaded by the plugin manager)
logger.info("Creating Network Scanner plugin instance")
plugin_instance = NetworkScannerPlugin()
logger.info("Network Scanner plugin instance created") 