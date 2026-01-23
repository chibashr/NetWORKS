#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
NetWORKS - An extensible device management application
"""

import sys
import os
import importlib.util
import subprocess
import json
from pathlib import Path
from loguru import logger

# Fix for Python 3.14+ DLL loading issue with PySide6
# Python 3.14 requires explicit DLL directory registration
if sys.version_info >= (3, 14):
    try:
        # Find PySide6 installation directory
        import site
        for site_packages in site.getsitepackages():
            pyside6_path = os.path.join(site_packages, "PySide6")
            if os.path.exists(pyside6_path):
                os.add_dll_directory(pyside6_path)
                break
        # Also check in virtual environment
        venv_pyside6 = os.path.join(os.path.dirname(sys.executable), "..", "Lib", "site-packages", "PySide6")
        venv_pyside6 = os.path.abspath(venv_pyside6)
        if os.path.exists(venv_pyside6):
            os.add_dll_directory(venv_pyside6)
    except Exception:
        # If DLL path setup fails, continue anyway - might work without it
        pass

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Load manifest to get version information
def load_manifest():
    """Load the application manifest"""
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
    
    try:
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                data = json.load(f)
                version = data.get("version_string", data.get("version", "0.1.0"))
                return data, version
        else:
            return {}, "0.1.0"
    except Exception:
        return {}, "0.1.0"

# Load manifest for version info
manifest_data, version = load_manifest()

# Temporary basic logger config until we initialize the proper logging manager
logger.remove()
startup_sink = sys.stderr if sys.stderr is not None else sys.stdout
if startup_sink is None:
    startup_sink = os.path.join("logs", "startup.log")
logger.add(
    startup_sink,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

def _is_automated_run():
    return os.environ.get("NETWORKS_AUTOMATED") == "1" or not sys.stdin.isatty()


def check_requirements():
    """Check if all required dependencies are installed"""
    try:
        requirements_file = os.path.join(os.path.dirname(__file__), "requirements.txt")
        if not os.path.exists(requirements_file):
            logger.error(f"Requirements file not found: {requirements_file}")
            return False
            
        # Read requirements file
        with open(requirements_file, 'r') as f:
            requirements = []
            optional_requirements = []
            current_list = requirements
            
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    # If line starts with "# Optional", switch to optional requirements
                    if "# Optional" in line:
                        current_list = optional_requirements
                    continue
                
                # Extract package name (remove version specification)
                package = line.split('>=')[0].split('==')[0].split('>')[0].split('<')[0].strip()
                current_list.append(package)
        
        # Function to check dependencies and return missing ones
        def check_dependencies(package_list):
            missing = []
            for package in package_list:
                try:
                    # Convert package name to module name (e.g., python-docx -> python_docx)
                    module_name = package.replace('-', '_').lower()
                    
                    # Try to directly import the module first
                    try:
                        __import__(module_name)
                        continue  # If import succeeds, package is available
                    except ImportError:
                        # If direct import fails, try some common variants or alternative module names
                        if module_name == "pyside6":
                            try:
                                __import__("PySide6")  # Case-sensitive import
                                continue
                            except ImportError:
                                pass
                        elif module_name == "pyyaml":
                            try:
                                __import__("yaml")
                                continue
                            except ImportError:
                                pass
                        elif module_name == "python_docx":
                            try:
                                __import__("docx")
                                continue
                            except ImportError:
                                pass
                    
                    # As a fallback, check if the module can be found
                    spec = importlib.util.find_spec(module_name)
                    if spec is None:
                        # Try with original case for case-sensitive modules
                        spec = importlib.util.find_spec(package)
                        if spec is None:
                            missing.append(package)
                except Exception:
                    missing.append(package)
            return missing
        
        # Check required dependencies
        missing = check_dependencies(requirements)
                
        # Check optional dependencies
        missing_optional = check_dependencies(optional_requirements)
                
        automated = _is_automated_run()

        # Handle missing required dependencies
        if missing:
            logger.error(f"Missing required dependencies: {', '.join(missing)}")
            print("\n[ERROR] The following required dependencies are missing:")
            for pkg in missing:
                print(f"  - {pkg}")
            
            # Ask if user wants to install missing required dependencies
            response = "y" if automated else input("\nDo you want to install the missing required dependencies now? (y/n): ")
            if response.lower() in ('y', 'yes'):
                try:
                    print("\nInstalling missing required dependencies...")
                    for pkg in missing:
                        print(f"Installing {pkg}...")
                        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
                    
                    # Verify installation was successful
                    print("\nVerifying installations...")
                    missing_after_install = check_dependencies(missing)
                    if missing_after_install:
                        logger.error(f"Failed to install some dependencies: {', '.join(missing_after_install)}")
                        print("\n[ERROR] Failed to install the following dependencies:")
                        for pkg in missing_after_install:
                            print(f"  - {pkg}")
                        print("\nPlease install them manually using: pip install -r requirements.txt")
                        return False
                    else:
                        print("All required dependencies successfully installed!")
                except Exception as e:
                    logger.error(f"Error installing dependencies: {e}")
                    print(f"\n[ERROR] Failed to install dependencies: {e}")
                    print("\nPlease install them manually using: pip install -r requirements.txt")
                    return False
            else:
                # User chose not to install
                print("\nPlease install the required dependencies using: pip install -r requirements.txt")
                return False
            
        # Handle missing optional dependencies
        if missing_optional:
            logger.warning(f"Missing optional dependencies: {', '.join(missing_optional)}")
            print("\n[WARNING] The following optional dependencies are missing:")
            for pkg in missing_optional:
                print(f"  - {pkg}")
            print("\nSome features may be unavailable.")
            
            # Ask if user wants to install missing optional dependencies
            response = "y" if automated else input("\nDo you want to install the missing optional dependencies now? (y/n): ")
            if response.lower() in ('y', 'yes'):
                try:
                    print("\nInstalling missing optional dependencies...")
                    for pkg in missing_optional:
                        print(f"Installing {pkg}...")
                        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
                    
                    # Verify installation was successful
                    print("\nVerifying installations...")
                    missing_after_install = check_dependencies(missing_optional)
                    if missing_after_install:
                        logger.warning(f"Failed to install some optional dependencies: {', '.join(missing_after_install)}")
                        print("\n[WARNING] Failed to install the following optional dependencies:")
                        for pkg in missing_after_install:
                            print(f"  - {pkg}")
                        print("\nSome features may still be unavailable.")
                    else:
                        print("All optional dependencies successfully installed!")
                except Exception as e:
                    logger.error(f"Error installing optional dependencies: {e}")
                    print(f"\n[WARNING] Failed to install optional dependencies: {e}")
                    print("\nSome features may be unavailable.")
            
        return True
    except Exception as e:
        logger.error(f"Error checking requirements: {e}")
        print(f"\n[ERROR] Failed to check requirements: {e}")
        return False

if __name__ == "__main__":
    try:
        if "--smoke-test" in sys.argv:
            os.environ["NETWORKS_SMOKE_TEST"] = "1"

        # Initialize the logging manager first with the application version
        from src.core import LoggingManager
        logging_manager = LoggingManager(version)
        logger = logging_manager.get_logger()
        
        # Log application startup
        logger.info(f"Starting NetWORKS v{version}")
        
        # Check requirements before starting the application
        if check_requirements():
            from src.app import Application
            
            # Create and run the application
            app = Application(sys.argv)
            exit_code = app.run()
            
            # Log application shutdown
            logger.info(f"Application exited with code {exit_code}")
            
            sys.exit(exit_code)
        else:
            logger.error("Application cannot start due to missing required dependencies")
            print("\nApplication cannot start due to missing required dependencies.")
            if not _is_automated_run():
                input("Press Enter to exit...")
            sys.exit(1)
    except Exception as e:
        # Ensure we log any startup errors
        try:
            logger.exception(f"Fatal error during application startup: {e}")
        except:
            # If logger is not available, print to console as last resort
            print(f"FATAL ERROR: {e}")
        
        # Show error to user
        print(f"\n[FATAL ERROR] An unexpected error occurred during startup: {e}")
        if not _is_automated_run():
            input("Press Enter to exit...")
        sys.exit(1) 