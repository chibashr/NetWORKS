#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Nmap path detection and verification for the Network Scanner plugin.
"""

import os
import subprocess
import shutil
import platform
from loguru import logger

try:
    import nmap
    HAS_NMAP = True
except ImportError:
    nmap = None
    HAS_NMAP = False


def _verify_nmap_executable(nmap_path):
    """Verify that an nmap executable actually works by running --version."""
    subprocess_kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "timeout": 5,
        "text": True,
    }
    if platform.system() == "Windows":
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            subprocess_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        result = subprocess.run(
            [nmap_path, "--version"],
            **subprocess_kwargs
        )
        if result.returncode == 0:
            version_info = result.stdout.strip().split("\n")[0] if result.stdout else "Unknown"
            logger.debug(f"Verified nmap at {nmap_path}: {version_info}")
            return True
        logger.debug(f"Nmap at {nmap_path} returned non-zero exit code: {result.returncode}")
        return False
    except Exception as e:
        logger.debug(f"Failed to verify nmap at {nmap_path}: {e}")
        return False


def find_nmap_executable():
    """Check if the nmap executable is available in PATH or common installation locations.

    Returns:
        str or None: Path to nmap executable if found, None otherwise.
    """
    nmap_names = ["nmap", "nmap.exe"]
    windows_paths = []
    if platform.system() == "Windows":
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        windows_paths = [
            os.path.join(program_files, "Nmap", "nmap.exe"),
            os.path.join(program_files_x86, "Nmap", "nmap.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Nmap", "nmap.exe"),
        ]

    for nmap_name in nmap_names:
        try:
            nmap_path = shutil.which(nmap_name)
            if nmap_path and _verify_nmap_executable(nmap_path):
                logger.info(f"Nmap executable found at: {nmap_path}")
                return nmap_path
        except Exception as e:
            logger.debug(f"shutil.which({nmap_name}) failed: {e}")
            continue

    for nmap_path in windows_paths:
        if nmap_path and os.path.exists(nmap_path) and os.path.isfile(nmap_path):
            if _verify_nmap_executable(nmap_path):
                logger.info(f"Nmap executable found at: {nmap_path}")
                return nmap_path

    subprocess_kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "timeout": 5,
        "text": True,
    }
    if platform.system() == "Windows":
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            subprocess_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    for nmap_name in nmap_names:
        try:
            result = subprocess.run(
                [nmap_name, "--version"],
                **subprocess_kwargs
            )
            if result.returncode == 0:
                version_info = result.stdout.strip().split("\n")[0] if result.stdout else "Unknown version"
                logger.info(f"Nmap executable available: {version_info}")
                found_path = shutil.which(nmap_name)
                return found_path if found_path else nmap_name
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


def test_python_nmap_works(nmap_path):
    """Test if python-nmap can actually use nmap by trying to execute a minimal command."""
    try:
        if not HAS_NMAP or nmap is None:
            return False

        nmap_dir = os.path.dirname(nmap_path) if nmap_path else None
        original_path = None

        if nmap_dir and os.path.exists(nmap_dir):
            current_path = os.environ.get("PATH", "")
            if nmap_dir not in current_path.split(os.pathsep):
                original_path = os.environ.get("PATH", "")
                os.environ["PATH"] = nmap_dir + os.pathsep + original_path
                logger.debug(f"Temporarily added nmap directory to PATH for testing: {nmap_dir}")

        try:
            test_scanner = nmap.PortScanner()
            if nmap_path and hasattr(test_scanner, "nmap_path"):
                test_scanner.nmap_path = nmap_path
                logger.debug(f"Set python-nmap path to: {nmap_path}")

            try:
                test_scanner.scan("127.0.0.1", arguments="-sn --max-rtt-timeout 100ms", timeout=2)
                logger.debug("Python-nmap test scan completed successfully")
                return True
            except nmap.PortScannerError as e:
                error_msg = str(e).lower()
                if "nmap" in error_msg and ("not found" in error_msg or "not installed" in error_msg):
                    logger.warning(f"Python-nmap cannot find nmap executable: {e}")
                    return False
                logger.debug(f"Python-nmap test scan returned error (may be expected): {e}")
                return True
            except Exception as e:
                logger.debug(f"Python-nmap test scan failed with exception: {e}")
                return True
        finally:
            if original_path is not None:
                os.environ["PATH"] = original_path
                logger.debug("Restored original PATH")
    except Exception as e:
        logger.error(f"Failed to test python-nmap: {e}")
        return False
