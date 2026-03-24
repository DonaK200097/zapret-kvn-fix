from __future__ import annotations

import os
import urllib.request
import json
from dataclasses import dataclass
from typing import Any

from .constants import SINGBOX_CLASH_API_PORT

# Processes to hide (internal, not user traffic)
_HIDDEN_PROCESSES = {"xray.exe", "sing-box.exe", "tun2socks.exe"}


@dataclass(slots=True)
class ProcessTrafficSnapshot:
    exe: str            # "chrome.exe"
    upload: int         # bytes total (cumulative)
    download: int       # bytes total (cumulative)
    connections: int    # active connection count
    total_connections: int = 0  # all-time unique connections
    route: str = "direct"      # "proxy" | "direct" | "mixed"
    proxy_bytes: int = 0   # bytes through proxy
    direct_bytes: int = 0  # bytes through direct
    top_host: str = ""     # most traffic host/domain
    down_speed: float = 0.0  # bytes/sec download
    up_speed: float = 0.0    # bytes/sec upload


# Session-scoped state
_seen_connections: dict[str, set[str]] = {}
_prev_totals: dict[str, tuple[int, int]] = {}  # {exe: (upload, download)}
_prev_time: float = 0.0


def reset_connection_tracking() -> None:
    """Call on disconnect to reset session counters."""
    _seen_connections.clear()
    _prev_totals.clear()
    global _prev_time
    _prev_time = 0.0


def collect_process_stats(clash_api_port: int = SINGBOX_CLASH_API_PORT) -> list[ProcessTrafficSnapshot]:
    """Poll sing-box Clash API and aggregate traffic by process.

    Returns list of ProcessTrafficSnapshot sorted by total traffic (desc).
    Returns empty list on error.
    """
    try:
        url = f"http://127.0.0.1:{clash_api_port}/connections"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data: dict[str, Any] = json.loads(resp.read())
    except Exception:
        return []

    connections = data.get("connections") or []

    # Aggregate by process exe name
    by_proc: dict[str, dict[str, Any]] = {}
    for conn in connections:
        meta = conn.get("metadata") or {}
        process_path = meta.get("processPath") or ""
        exe = os.path.basename(process_path).lower() if process_path else "unknown"

        if exe in _HIDDEN_PROCESSES:
            continue

        if exe not in by_proc:
            by_proc[exe] = {
                "upload": 0, "download": 0, "conns": 0, "routes": set(),
                "proxy_bytes": 0, "direct_bytes": 0, "hosts": {},
                "display_exe": exe,
            }

        entry = by_proc[exe]
        conn_up = conn.get("upload", 0)
        conn_down = conn.get("download", 0)
        conn_total = conn_up + conn_down

        # Track unique connection IDs for total count
        conn_id = conn.get("id", "")
        if conn_id:
            if exe not in _seen_connections:
                _seen_connections[exe] = set()
            _seen_connections[exe].add(conn_id)
        entry["upload"] += conn_up
        entry["download"] += conn_down
        entry["conns"] += 1

        # Route + per-route bytes
        chains = conn.get("chains") or []
        is_proxy = False
        if chains:
            chain = chains[0].lower()
            if "proxy" in chain:
                entry["routes"].add("proxy")
                entry["proxy_bytes"] += conn_total
                is_proxy = True
            else:
                entry["routes"].add("direct")
                entry["direct_bytes"] += conn_total

        # Track hosts (domain or IP)
        host = meta.get("host") or meta.get("destinationIP") or ""
        if host:
            entry["hosts"][host] = entry["hosts"].get(host, 0) + conn_total

        # Original case display name
        if entry["display_exe"] == exe:
            pp = meta.get("processPath") or ""
            if pp:
                entry["display_exe"] = os.path.basename(pp)

    # Calculate per-process speed from delta
    import time as _time
    global _prev_time
    now = _time.monotonic()
    dt = max(0.5, now - _prev_time) if _prev_time > 0 else 2.0
    _prev_time = now

    # Build snapshots
    result: list[ProcessTrafficSnapshot] = []
    for exe, stats in by_proc.items():
        routes = stats["routes"]
        if len(routes) > 1:
            route = "mixed"
        elif routes:
            route = next(iter(routes))
        else:
            route = "direct"

        top_host = ""
        if stats["hosts"]:
            top_host = max(stats["hosts"], key=stats["hosts"].get)

        total_conns = len(_seen_connections.get(exe, set()))

        # Speed from delta
        cur_up, cur_down = stats["upload"], stats["download"]
        prev_up, prev_down = _prev_totals.get(exe, (0, 0))
        up_speed = max(0.0, (cur_up - prev_up) / dt)
        down_speed = max(0.0, (cur_down - prev_down) / dt)
        _prev_totals[exe] = (cur_up, cur_down)

        result.append(ProcessTrafficSnapshot(
            exe=stats["display_exe"],
            upload=cur_up,
            download=cur_down,
            connections=stats["conns"],
            total_connections=total_conns,
            route=route,
            proxy_bytes=stats["proxy_bytes"],
            direct_bytes=stats["direct_bytes"],
            top_host=top_host,
            down_speed=down_speed,
            up_speed=up_speed,
        ))

    # Sort by total traffic descending
    result.sort(key=lambda s: s.upload + s.download, reverse=True)
    return result
