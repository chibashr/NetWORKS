#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Scanner worker for the Network Scanner plugin.
Runs nmap scans in a background thread.
"""

import os
import time
import datetime
import threading
from loguru import logger

from PySide6.QtCore import QObject, Signal

from ..utils.range_utils import _split_range_into_chunks


class ScannerWorker(QObject):
    """Worker thread for network scanning."""

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
        self.scanner = None

    def stop(self):
        """Stop the scan."""
        logger.debug("Request to stop scanner received")
        self.should_stop = True

    def run(self):
        """Run the network scan."""
        self.is_running = True

        try:
            try:
                import nmap

                if self.nmap_path and os.path.exists(self.nmap_path):
                    nmap_dir = os.path.dirname(self.nmap_path)
                    current_path = os.environ.get("PATH", "")
                    if nmap_dir not in current_path.split(os.pathsep):
                        os.environ["PATH"] = nmap_dir + os.pathsep + current_path
                        logger.debug(f"Added nmap directory to PATH: {nmap_dir}")

                self.scanner = nmap.PortScanner()
                if self.nmap_path and hasattr(self.scanner, "nmap_path"):
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

            # Scan behavior is primarily defined by the arguments provided by the
            # caller (profile arguments plus any optional custom arguments). For
            # backwards compatibility, if no arguments are provided we fall back
            # to legacy per-scan-type defaults.
            arguments = (self.custom_scan_args or "").strip()

            if not arguments and self.scan_type and self.scan_type != "custom":
                if self.scan_type == "quick":
                    arguments = "-sn -T4"
                elif self.scan_type == "standard":
                    arguments = "-sn -F -O -T4"
                elif self.scan_type == "comprehensive":
                    arguments = "-sS -p 1-1000 -O -A -T4"
                elif self.scan_type == "stealth":
                    arguments = "-sS -T2"
                elif self.scan_type == "service":
                    arguments = "-sV -p 21,22,23,25,53,80,110,111,135,139,143,443,445,993,995,1723,3306,3389,5900,8080 -T4"

            arg_parts = arguments.split()
            unique_args = []
            seen_options = set()
            port_options = []
            for arg in arg_parts:
                if arg.startswith("-p"):
                    if len(arg) > 2:
                        port_options.append(arg[2:])
                    elif arg == "-p" and len(arg_parts) > arg_parts.index(arg) + 1:
                        next_idx = arg_parts.index(arg) + 1
                        next_arg = arg_parts[next_idx]
                        if not next_arg.startswith("-"):
                            port_options.append(next_arg)
                elif arg.startswith("-"):
                    option_char = arg[1:].split(" ")[0]
                    if option_char not in seen_options:
                        seen_options.add(option_char)
                        unique_args.append(arg)
                else:
                    unique_args.append(arg)

            if port_options:
                all_ports = set()
                for ports in port_options:
                    for port_spec in ports.split(","):
                        all_ports.add(port_spec.strip())
                unique_args.append(f"-p {','.join(sorted(all_ports))}")

            arguments = " ".join(unique_args)
            logger.info(f"Starting network scan of {self.network_range} with arguments: {arguments}")

            if "-v" not in arguments:
                arguments += " -v"

            scan_start_time = time.time()
            devices_found = 0
            last_progress_update = time.time()
            last_status_message = ""

            try:
                if self.should_stop:
                    logger.info("Scan stopped before starting")
                    self.is_running = False
                    return

                self.progress.emit(0, 100)
                self.device_found.emit({"status_update": "Initializing nmap scan..."})

                import ipaddress
                import re
                host_count_estimate = 256
                try:
                    target_text = self.network_range.strip()
                    if "/" in target_text:
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

                if host_count_estimate > 4096:
                    logger.warning(f"Very large network range detected ({host_count_estimate} hosts). This may cause nmap issues.")
                    self.device_found.emit({
                        "status_update": f"Warning: Large network ({host_count_estimate} hosts). Scan may take a long time or fail..."
                    })
                else:
                    self.device_found.emit({"status_update": f"Preparing to scan {host_count_estimate} potential addresses..."})

                try:
                    timeout_val = max(60, min(self.timeout, 900))
                    has_timing = any(arg in arguments for arg in ["-T1", "-T2", "-T3", "-T4", "-T5"])

                    if host_count_estimate > 1024:
                        if "-T4" in arguments or "-T5" in arguments:
                            arguments = arguments.replace("-T4", "-T3").replace("-T5", "-T3")
                            logger.debug("Replaced aggressive timing template with T3 for large network to avoid nmap assertion failures")
                        elif not has_timing:
                            arguments += " -T3"
                            logger.debug("Using T3 timing template for large network to avoid nmap assertion failures")
                    elif not has_timing:
                        arguments += " -T4"

                    if host_count_estimate > 512 and "--host-timeout" not in arguments:
                        arguments += " --host-timeout 30s"
                        logger.debug("Added --host-timeout for large network scan")

                    logger.debug(f"Starting nmap scan (estimated {host_count_estimate} hosts) with arguments: {arguments}")
                    self.device_found.emit({"status_update": f"Starting nmap scan of {host_count_estimate} hosts..."})

                    chunks = _split_range_into_chunks(self.network_range, max_hosts_per_chunk=32)
                    total_hosts_acc = 0
                    update_timer = None

                    for chunk_idx, chunk in enumerate(chunks):
                        if self.should_stop:
                            break
                        update_timer = None
                        if len(chunks) > 1:
                            self.device_found.emit({
                                "status_update": f"Scanning {chunk} ({chunk_idx + 1}/{len(chunks)})..."
                            })
                        else:
                            self.device_found.emit({"status_update": f"Scanning {chunk}..."})

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
                                if "status" not in self.scanner[host] or not self.scanner[host]["status"] or self.scanner[host]["status"].get("state") != "up":
                                    continue
                                host_data = {}
                                host_data["ip_address"] = host
                                host_data["scan_source"] = "nmap"
                                host_data["scan_type"] = self.scan_type
                                if "status" in self.scanner[host] and self.scanner[host]["status"]:
                                    host_data["status"] = self.scanner[host]["status"].get("state", "unknown")
                                    host_data["status_reason"] = self.scanner[host]["status"].get("reason", "")
                                try:
                                    if "hostnames" in self.scanner[host] and self.scanner[host]["hostnames"]:
                                        hostnames = self.scanner[host]["hostnames"]
                                        if isinstance(hostnames, list) and hostnames:
                                            for hostname_entry in hostnames:
                                                if "name" in hostname_entry and hostname_entry["name"]:
                                                    host_data["hostname"] = hostname_entry["name"]
                                                    break
                                except Exception:
                                    pass
                                try:
                                    if "addresses" in self.scanner[host]:
                                        addresses = self.scanner[host]["addresses"]
                                        if "ipv4" in addresses:
                                            host_data["ipv4_address"] = addresses["ipv4"]
                                        if "ipv6" in addresses:
                                            host_data["ipv6_address"] = addresses["ipv6"]
                                        if "mac" in addresses:
                                            host_data["mac_address"] = addresses["mac"]
                                    if "vendor" in self.scanner[host] and self.scanner[host]["vendor"] and host_data.get("mac_address") in self.scanner[host]["vendor"]:
                                        host_data["mac_vendor"] = self.scanner[host]["vendor"][host_data["mac_address"]]
                                except Exception:
                                    pass
                                try:
                                    if "osmatch" in self.scanner[host] and self.scanner[host]["osmatch"]:
                                        os_matches = self.scanner[host]["osmatch"]
                                        if isinstance(os_matches, list) and os_matches:
                                            best = max(os_matches, key=lambda x: int(x.get("accuracy", 0) or 0))
                                            if "name" in best:
                                                host_data["os"] = best["name"]
                                except Exception:
                                    pass
                                try:
                                    if "tcp" in self.scanner[host]:
                                        tcp_ports = [int(p) for p, d in self.scanner[host]["tcp"].items() if d.get("state") == "open"]
                                        tcp_services = {int(p): d.get("name", "") for p, d in self.scanner[host]["tcp"].items() if d.get("state") == "open" and d.get("name")}
                                        if tcp_ports:
                                            host_data["open_tcp_ports"] = sorted(tcp_ports)
                                        if tcp_services:
                                            host_data["tcp_services"] = tcp_services
                                    if "udp" in self.scanner[host]:
                                        udp_ports = [int(p) for p, d in self.scanner[host]["udp"].items() if d.get("state") == "open"]
                                        udp_services = {int(p): d.get("name", "") for p, d in self.scanner[host]["udp"].items() if d.get("state") == "open" and d.get("name")}
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

                    scan_time = time.time() - scan_start_time
                    scan_results = {
                        "network_range": self.network_range,
                        "scan_type": self.scan_type,
                        "total_hosts": total_hosts_acc,
                        "devices_found": devices_found,
                        "scan_time": scan_time,
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    self.scan_complete.emit(scan_results)

                except Exception as scan_error:
                    logger.error(f"Error during nmap scan: {scan_error}")
                    if update_timer:
                        try:
                            update_timer.cancel()
                        except Exception:
                            pass

                    error_msg = str(scan_error).lower()
                    error_str = str(scan_error)
                    if "assertion failed" in error_msg or "htn.toclock_running" in error_msg:
                        logger.warning("Nmap internal assertion failure detected.")
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
            try:
                logger.debug("Cleaning up scanner resources")
                if hasattr(self, "scanner") and self.scanner:
                    self.scanner = None
                import gc
                gc.collect()
            except Exception as cleanup_error:
                logger.error(f"Error during scanner cleanup: {cleanup_error}")
            self.is_running = False
            logger.debug("Scanner worker finished")
