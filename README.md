# Xray Fluent GUI (PyQt6 + Fluent Widgets)

Windows-focused GUI shell for `xray.exe` with a Windows 11-like Fluent interface.

## What is included in this MVP

- Fast node import from clipboard (`vless://`, `vmess://`, `trojan://`, `ss://`, `socks://`, `http://`, raw outbound JSON)
- Quick switch between nodes (Dashboard + system tray)
- Start/stop Xray core directly (`core/xray.exe`)
- System proxy mode (HTTP + SOCKS loopback)
- Routing modes: `Global`, `Rule`, `Direct`
- Basic routing editor (direct/proxy/block lists)
- TCP ping for nodes
- Real connectivity test through Xray proxy
- Live mini-metrics on Dashboard (download/upload rate + RTT)
- Export selected outbound JSON and full runtime `xray_config.json`
- Runtime logs, diagnostics export (ZIP with redacted config)
- Separate Xray core updater with channels (`stable`, `beta`, `nightly`)
- DPAPI-encrypted local state storage
- Master password + auto-lock
- Light / dark / system theme and accent color

## Project layout

- `main.py` - app entrypoint
- `xray_fluent/app_controller.py` - app orchestration
- `xray_fluent/link_parser.py` - URI parser
- `xray_fluent/config_builder.py` - Xray config generator
- `xray_fluent/xray_manager.py` - process lifecycle
- `xray_fluent/proxy_manager.py` - Windows system proxy
- `xray_fluent/ui/` - all Fluent UI pages
- `core/` - Xray core binaries

## Requirements

- Windows 10/11 x64
- Python 3.13

Install deps:

```bash
python -m pip install -r requirements.txt
```

If `qfluentwidgets` is not in your Python env, install it explicitly:

`python -m pip install PyQt6-Fluent-Widgets`

## Run

```bash
python main.py
```

Start minimized to tray:

```bash
python main.py --minimized
```

## Build portable EXE (PyInstaller)

```powershell
./build_portable.ps1
```

Output:

- `dist/XrayFluent/` - portable folder
- `dist/XrayFluent-portable.zip` - zipped portable bundle

## Notes

- No TUN mode in this version (system proxy only)
- Subscription URLs are intentionally not implemented yet
- App update feed and Xray core feed can be configured separately in Settings
