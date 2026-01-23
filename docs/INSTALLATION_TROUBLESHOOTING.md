# NetWORKS Installation Troubleshooting

This guide helps you resolve common installation and dependency issues with NetWORKS.

## Quick Fix: Repair Installation Script

For most installation issues, you can run the repair script:

1. Open a command prompt
2. Navigate to the NetWORKS directory
3. Run: `repair_installation.bat`

This script will:
- Check your Python installation
- Repair or recreate the virtual environment if needed
- Reinstall all dependencies
- Verify the installation

## Automated Full Install Test (Local-Only)

Local helper scripts are kept under `scripts/local/` and are gitignored for release builds.
If you maintain a local copy of `scripts/local/Test_Installation.bat`, run it from the repo root.

Manual alternative:
1. `python -m venv .venv_test`
2. `.\.venv_test\Scripts\activate`
3. `pip install -r requirements.txt --no-cache-dir`
4. `python networks.py --smoke-test`
5. `deactivate` and remove `.venv_test` when done

## Common Issues and Solutions

### Missing Dependencies

**Issue**: Application crashes with error about missing modules.

**Solution**:
1. Run the repair script: `repair_installation.bat`
2. Or manually install the missing dependency: 
   ```
   venv\Scripts\activate
   pip install <module_name>
   ```

### Corrupt Virtual Environment

**Issue**: Application fails to start with virtual environment errors.

**Solution**:
1. Run the repair script: `repair_installation.bat`
2. Or manually recreate the virtual environment:
   ```
   rmdir /s /q venv
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

### Python Not Found

**Issue**: Error message saying Python is not installed or not in PATH.

**Solution**:
1. Install Python 3.8 or later from [python.org](https://www.python.org/downloads/)
2. During installation, select "Add Python to PATH"
3. Restart your computer
4. Run `repair_installation.bat`

### PySide6/Qt Errors

**Issue**: Errors related to Qt or PySide6 components.

**Solution**:
1. Run the repair script to reinstall PySide6
2. Ensure you have the Microsoft Visual C++ Redistributable installed
   - Download from [Microsoft's website](https://support.microsoft.com/en-us/help/2977003/the-latest-supported-visual-c-downloads)

### File Import Features Not Working

**Issue**: Cannot import Excel, Word, or other file formats.

**Solution**:
Install the optional dependencies:
```
venv\Scripts\activate
pip install pandas openpyxl xlrd python-docx
```

Or run the repair script which will install all dependencies.

## Manual Installation

If you need to set up NetWORKS manually:

1. Ensure Python 3.8+ is installed
2. Create a virtual environment: `python -m venv venv`
3. Activate it: `venv\Scripts\activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Run the application: `python networks.py`

## Additional Help

If you still encounter issues:

1. Check the logs in the `logs` directory for detailed error messages
2. Make sure your Python version is compatible (3.8 or newer)
3. Verify you have administrator privileges when installing
4. For file encoding issues, make sure `chardet` is installed

## Specific Error Messages

### ModuleNotFoundError: No module named 'chardet'

This indicates the character detection library is missing.

**Solution**:
```
venv\Scripts\activate
pip install chardet
```

### ModuleNotFoundError: No module named 'PySide6'

The Qt library is missing.

**Solution**:
```
venv\Scripts\activate
pip install PySide6
```

### DLL Load Failed while importing PySide6

This error can have several causes:

**Cause 1: Missing Visual C++ Redistributable**

**Solution**:
Install the Microsoft Visual C++ Redistributable for Visual Studio 2019 or later.
Download from: https://aka.ms/vs/17/release/vc_redist.x64.exe

**Cause 2: Python 3.14+ DLL Path Issue**

Python 3.14 and later versions have stricter DLL loading requirements. PySide6 DLLs need to be explicitly registered.

**Solution**:
The application automatically handles this in `networks.py`. If you're still experiencing issues:
1. Ensure you're using the latest version of NetWORKS
2. The fix is automatically applied on startup for Python 3.14+
3. If problems persist, try running `scripts\fix_pyside6.bat` to reinstall PySide6 