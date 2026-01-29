# Device Connector Plugin

Adds a **Connect** submenu to the device table context menu so you can open **SSH**, **Telnet**, **VNC**, **RDP**, **HTTP**, **HTTPS**, or **FTP** to selected devices using their IP or hostname. All options open as links (like FTP): the system decides which application handles each protocol (e.g. PuTTY for ssh://, browser for http://).

## Usage

1. In the device table, select one or more devices (checkbox or row highlight).
2. Right-click → **Connect** → choose **SSH**, **Telnet**, **VNC**, **RDP**, **HTTP**, **HTTPS**, or **FTP**.
3. The system opens the appropriate URL (e.g. `ssh://host:22`, `https://host`) and your default handler (PuTTY, browser, VNC viewer, etc.) is used. One connection per device.

If a device has no IP address or hostname, it is skipped. Authentication (SSH login, RDP credentials, etc.) is done in the application that opens, not in the plugin.

## Configuration

Configure default ports in **Settings → Plugins → Device Connector → Settings** (or Plugin Manager → Device Connector → Settings):

- **Default SSH port** — 22
- **Default Telnet port** — 23
- **Default VNC port** — 5900
- **Default RDP port** — 3389

There are no executable paths to set; the system uses whatever application is registered for each protocol (ssh://, telnet://, vnc://, rdp://, http://, https://, ftp://). Settings are saved in `config.json` in the plugin folder.

## Requirements

- NetWORKS 0.8.16 or newer.
- Your OS must have handlers registered for the protocols you use (e.g. PuTTY or OpenSSH for ssh://, browser for http:// and https://).

## Scope

- **Device table only:** The Connect submenu appears on the device table context menu. The device tree does not expose this plugin.
- **No toolbar or panels:** All configuration is via plugin settings; no dock or toolbar is added.
