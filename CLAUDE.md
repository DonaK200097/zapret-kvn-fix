# XrayFluent

PyQt6 + qfluentwidgets GUI client for Xray proxy with TUN VPN support.

## Build

```bash
# Full build (clean + compile + zip):
.venv/Scripts/python build.py

# Build without zip:
.venv/Scripts/python build.py --no-zip
```

Output: `dist/XrayFluent/XrayFluent.exe`

**IMPORTANT:** Kill ALL processes before building (XrayFluent.exe, xray.exe, tun2socks.exe, sing-box.exe). Use `wmic process where "name='...'" call terminate`. Wait 5 seconds. Locked files cause silent build failures.

The `clean()` step backs up `data/` before PyInstaller and restores after.

## Default core paths

Defined in `xray_fluent/constants.py`:
- `XRAY_PATH_DEFAULT = BASE_DIR / "core" / "xray.exe"`
- `SINGBOX_PATH_DEFAULT = BASE_DIR / "core" / "sing-box.exe"`
- `tun2socks.exe` also in `core/`

`BASE_DIR` = directory of the .exe (frozen) or project root (dev mode).

## TUN mode architecture

Uses **tun2socks + xray** (not sing-box):
```
All traffic → TUN (tun2socks/wintun) → xray SOCKS:10808 → proxy server
```

- `tun2socks_manager.py` — manages tun2socks process and Windows routes
- Routes added via `netsh interface ipv4 add route` with metric=0
- Hot-swap: node switching only restarts xray, tun2socks stays alive
- LAN/broadcast blocked in xray routing rules
- xray log level set to "error" in TUN mode to prevent UI flood
- "accepted" log lines throttled (summary every 100 connections)
- TUN requires Administrator privileges

## Project structure

- `main.py` — entry point, atexit proxy/TUN cleanup
- `xray_fluent/` — core logic
  - `app_controller.py` — central controller (signals, state, connection, TUN)
  - `tun2socks_manager.py` — TUN via tun2socks + wintun + route management
  - `xray_manager.py` — QProcess wrapper for xray-core
  - `singbox_manager.py` — QProcess wrapper for sing-box (legacy, used for non-TUN)
  - `singbox_config_builder.py` — sing-box config (legacy)
  - `config_builder.py` — xray config generation
  - `models.py` — data models (Node, AppSettings, RoutingSettings)
  - `proxy_manager.py` — Windows system proxy toggle
  - `storage.py` — state persistence (encrypted/plain JSON)
  - `link_parser.py` — VLESS/Trojan/SS link parsing
- `xray_fluent/ui/` — UI pages
  - `main_window.py` — FluentWindow, navigation, tray, signal wiring
  - `dashboard_page.py` — connection status, traffic graph, metrics
  - `nodes_page.py` — server list, Ctrl+V import, copy link context menu
  - `settings_page.py` — stock qfluentwidgets cards (SpinBox, ColorPicker, etc.)
  - `traffic_graph.py` — QPainter live traffic chart
  - `routing_page.py` — routing rules editor
  - `logs_page.py` — log viewer
- `core/` — xray, sing-box, tun2socks, wintun.dll binaries
- `build.py` — PyInstaller build script with data/ backup/restore

## Key conventions

- Use stock `qfluentwidgets` components over custom card classes
- Keep page surfaces transparent for Windows 11 Mica effect
- Node switching uses deferred `QTimer.singleShot(0, ...)` to avoid UI freezes
- In TUN mode, use hot-swap (restart xray only) instead of full reconnect
- System proxy always disabled on exit (atexit handler in main.py)
- Use subagents (5+) for thorough codebase analysis
- venv is at `.venv/`, created by `setup.bat`
