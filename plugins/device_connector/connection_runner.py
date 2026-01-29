# -*- coding: utf-8 -*-
"""
Device Connector — open connection URLs for devices.

Resolves host/port from device properties. For SSH/Telnet supports
username/password in URL. For VNC/RDP tries to launch a detected
application when vnc:// or rdp:// URL is not handled by the system.
"""

import os
import sys
import shutil
import subprocess
import platform
from urllib.parse import quote
from typing import List, Optional, Tuple, Any
from loguru import logger

# Connection type identifiers (must match plugin settings keys / menu actions)
CONNECTION_SSH = "ssh"
CONNECTION_TELNET = "telnet"
CONNECTION_VNC = "vnc"
CONNECTION_RDP = "rdp"
CONNECTION_HTTP = "http"
CONNECTION_HTTPS = "https"
CONNECTION_FTP = "ftp"

DEFAULT_SSH_PORT = 22
DEFAULT_TELNET_PORT = 23
DEFAULT_VNC_PORT = 5900
DEFAULT_RDP_PORT = 3389
DEFAULT_HTTP_PORT = 80
DEFAULT_HTTPS_PORT = 443
DEFAULT_FTP_PORT = 21


def resolve_host(device: Any) -> Tuple[Optional[str], Optional[int]]:
    """
    Resolve connection target from device: prefer ip_address, fallback hostname.

    Args:
        device: Device instance with get_property(key, default).

    Returns:
        (host, None) where host is ip_address or hostname, or (None, None) if both empty.
    """
    if device is None:
        return (None, None)
    host = (device.get_property("ip_address") or "").strip() or (
        device.get_property("hostname") or ""
    ).strip()
    if not host:
        return (None, None)
    return (host, None)


def _open_url(url: str, plugin_id: str) -> bool:
    """Open URL in default handler (browser, registered app). Returns True on success."""
    try:
        if sys.platform == "win32":
            os.startfile(url)
        else:
            import webbrowser
            webbrowser.open(url)
        return True
    except Exception as e:
        logger.exception(f"[{plugin_id}] Failed to open {url}: {e}")
        return False


def _detect_vnc_viewer() -> Optional[str]:
    """Common VNC viewer locations on Windows; otherwise which vncviewer."""
    vnc = shutil.which("vncviewer")
    if vnc:
        return vnc
    if platform.system() == "Windows":
        for base in [
            os.environ.get("ProgramFiles", "C:\\Program Files"),
            os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
        ]:
            for name in ["RealVNC", "TigerVNC", "TightVNC", "VNC Viewer"]:
                path = os.path.join(base, name, "vncviewer.exe")
                if os.path.isfile(path):
                    return path
            for subdir in ["RealVNC", "VNC Viewer", "TightVNC", "TigerVNC"]:
                for exe in ["vncviewer.exe", "VNC Viewer.exe"]:
                    path = os.path.join(base, subdir, exe)
                    if os.path.isfile(path):
                        return path
    return None


def _detect_rdp_client() -> Optional[str]:
    """Windows: mstsc.exe; Linux: rdesktop or xfreerdp."""
    if platform.system() == "Windows":
        mstsc = shutil.which("mstsc") or os.path.join(
            os.environ.get("SystemRoot", "C:\\Windows"), "System32", "mstsc.exe"
        )
        if mstsc and os.path.isfile(mstsc):
            return mstsc
    else:
        for exe in ("rdesktop", "xfreerdp", "freerdp"):
            path = shutil.which(exe)
            if path:
                return path
    return None


def _launch_protocol(
    devices: List[Any],
    scheme: str,
    default_port: int,
    plugin_id: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Tuple[int, Optional[str]]:
    """Open scheme://[user[:pass]@]host[:port] for each device. Returns (success_count, error_message)."""
    if not devices:
        return (0, None)
    success = 0
    port = default_port if default_port > 0 else None
    for device in devices:
        host, _ = resolve_host(device)
        if not host:
            continue
        if port is not None and port > 0:
            host_part = f"{host}:{port}"
        else:
            host_part = host
        if username and username.strip():
            user = quote(username.strip(), safe="")
            if password is not None and password:
                pwd = quote(password, safe="")
                url = f"{scheme}://{user}:{pwd}@{host_part}"
            else:
                url = f"{scheme}://{user}@{host_part}"
        else:
            url = f"{scheme}://{host_part}"
        if _open_url(url, plugin_id):
            success += 1
    return (success, None)


def launch_ssh(
    devices: List[Any],
    default_port: int,
    plugin_id: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Tuple[int, Optional[str]]:
    """Open ssh://[user[:pass]@]host:port for each device."""
    return _launch_protocol(
        devices, "ssh", default_port or DEFAULT_SSH_PORT, plugin_id,
        username=username, password=password,
    )


def launch_telnet(
    devices: List[Any],
    default_port: int,
    plugin_id: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Tuple[int, Optional[str]]:
    """Open telnet://[user[:pass]@]host:port for each device."""
    return _launch_protocol(
        devices, "telnet", default_port or DEFAULT_TELNET_PORT, plugin_id,
        username=username, password=password,
    )


def launch_vnc(
    devices: List[Any],
    default_port: int,
    plugin_id: str,
) -> Tuple[int, Optional[str]]:
    """Try to launch a VNC viewer app for each device; fall back to vnc:// URL."""
    if not devices:
        return (0, None)
    port = default_port if default_port > 0 else DEFAULT_VNC_PORT
    exe = _detect_vnc_viewer()
    success = 0
    for device in devices:
        host, _ = resolve_host(device)
        if not host:
            continue
        target = f"{host}:{port}"
        launched = False
        if exe:
            try:
                subprocess.Popen(
                    [exe, target],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
                launched = True
            except Exception as e:
                logger.warning(f"[{plugin_id}] VNC launch failed for {target}: {e}")
        if not launched:
            if _open_url(f"vnc://{target}", plugin_id):
                launched = True
        if launched:
            success += 1
    return (success, None)


def launch_rdp(
    devices: List[Any],
    default_port: int,
    plugin_id: str,
) -> Tuple[int, Optional[str]]:
    """Try to launch RDP client (mstsc/rdesktop) for each device; fall back to rdp:// URL."""
    if not devices:
        return (0, None)
    port = default_port if default_port > 0 else DEFAULT_RDP_PORT
    exe = _detect_rdp_client()
    success = 0
    is_mstsc = exe and "mstsc" in exe.lower()
    for device in devices:
        host, _ = resolve_host(device)
        if not host:
            continue
        launched = False
        if exe:
            try:
                if is_mstsc:
                    target = f"{host}:{port}" if port != DEFAULT_RDP_PORT else host
                    subprocess.Popen(
                        [exe, f"/v:{target}"],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                    )
                else:
                    target = f"{host}:{port}"
                    subprocess.Popen(
                        [exe, target],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                launched = True
            except Exception as e:
                logger.warning(f"[{plugin_id}] RDP launch failed for {host}: {e}")
        if not launched:
            url = f"rdp://{host}:{port}" if port != DEFAULT_RDP_PORT else f"rdp://{host}"
            if _open_url(url, plugin_id):
                launched = True
        if launched:
            success += 1
    return (success, None)


def launch_http(devices: List[Any], plugin_id: str) -> Tuple[int, Optional[str]]:
    """Open http://host for each device (default browser)."""
    if not devices:
        return (0, None)
    success = 0
    for device in devices:
        host, _ = resolve_host(device)
        if not host:
            continue
        if _open_url(f"http://{host}", plugin_id):
            success += 1
    return (success, None)


def launch_https(devices: List[Any], plugin_id: str) -> Tuple[int, Optional[str]]:
    """Open https://host for each device (default browser)."""
    if not devices:
        return (0, None)
    success = 0
    for device in devices:
        host, _ = resolve_host(device)
        if not host:
            continue
        if _open_url(f"https://{host}", plugin_id):
            success += 1
    return (success, None)


def launch_ftp(devices: List[Any], plugin_id: str) -> Tuple[int, Optional[str]]:
    """Open ftp://host for each device (default handler)."""
    if not devices:
        return (0, None)
    success = 0
    for device in devices:
        host, _ = resolve_host(device)
        if not host:
            continue
        if _open_url(f"ftp://{host}", plugin_id):
            success += 1
    return (success, None)
