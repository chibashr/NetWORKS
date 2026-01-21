# NetWORKS Portable EXE (Windows)

This guide explains the one-click portable build for NetWORKS.

## One-Click Build

1. Double-click `Build_Release.bat` in the project root.

What it does:
- Creates a clean build environment
- Installs required dependencies
- Builds a portable onedir EXE
- Outputs to `dist/NetWORKS/`

## Result

After a successful build, launch the app from:

`dist/NetWORKS/NetWORKS.exe`

## Notes

- The output folder is safe to copy to another Windows machine.
- Build artifacts are gitignored by default.
