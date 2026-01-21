#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Diagnostic script to check PySide6 installation and dependencies
"""

import sys
import os
from pathlib import Path

def check_vc_redist():
    """Check if Visual C++ Redistributable is likely installed"""
    # Common locations for VC++ Redistributable
    vc_redist_paths = [
        r"C:\Windows\System32\msvcp140.dll",
        r"C:\Windows\System32\vcruntime140.dll",
        r"C:\Windows\System32\msvcp140_1.dll",
        r"C:\Windows\SysWOW64\msvcp140.dll",
        r"C:\Windows\SysWOW64\vcruntime140.dll",
    ]
    
    found = []
    missing = []
    
    for path in vc_redist_paths:
        if os.path.exists(path):
            found.append(path)
        else:
            missing.append(path)
    
    return found, missing

def check_pyside6_dlls():
    """Check if PySide6 DLLs exist"""
    try:
        import PySide6
        pyside6_path = Path(PySide6.__file__).parent
        dll_files = list(pyside6_path.glob("*.dll"))
        return True, pyside6_path, dll_files
    except ImportError as e:
        return False, None, None

def main():
    print("=" * 60)
    print("PySide6 Diagnostic Tool")
    print("=" * 60)
    print()
    
    # Check Python version
    print(f"Python Version: {sys.version}")
    print(f"Python Executable: {sys.executable}")
    print()
    
    # Check Visual C++ Redistributable
    print("Checking Visual C++ Redistributable...")
    found, missing = check_vc_redist()
    if found:
        print(f"[OK] Found {len(found)} VC++ runtime DLL(s):")
        for path in found:
            print(f"  - {path}")
    if missing:
        print(f"[WARNING] Missing {len(missing)} VC++ runtime DLL(s):")
        for path in missing:
            print(f"  - {path}")
    print()
    
    # Check PySide6 installation
    print("Checking PySide6 installation...")
    try:
        import PySide6
        try:
            version = PySide6.__version__
        except AttributeError:
            version = "unknown (module found but version unavailable)"
        print(f"[OK] PySide6 is installed: {version}")
        try:
            if PySide6.__file__:
                print(f"  Location: {Path(PySide6.__file__).parent}")
        except (AttributeError, TypeError):
            print("  Location: (unable to determine)")
        
        # Try to import QtCore
        print("\nTesting PySide6.QtCore import...")
        try:
            from PySide6.QtCore import QObject
            print("[OK] PySide6.QtCore imported successfully!")
            return 0
        except ImportError as e:
            print(f"[ERROR] Failed to import PySide6.QtCore: {e}")
            print("\nThis usually means:")
            print("  1. Visual C++ Redistributable is missing")
            print("  2. PySide6 installation is corrupted")
            print("  3. DLL dependencies are missing")
            print("\nSolution:")
            print("  Install Microsoft Visual C++ Redistributable:")
            print("  https://aka.ms/vs/17/release/vc_redist.x64.exe")
            return 1
    except ImportError:
        print("[ERROR] PySide6 is not installed")
        return 1
    
    print()
    return 0

if __name__ == "__main__":
    sys.exit(main())
