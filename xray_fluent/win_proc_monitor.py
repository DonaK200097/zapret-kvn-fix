"""Per-process proxy usage monitor via Windows API.

Uses GetExtendedTcpTable to find which processes have connections
to xray SOCKS/HTTP ports. Lightweight — no HTTP requests, < 1ms per call.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
from dataclasses import dataclass
from typing import Any

# TCP_TABLE_OWNER_PID_CONNECTIONS = 4
_TCP_TABLE_OWNER_PID_CONN = 4
_AF_INET = 2
_MIB_TCP_STATE_ESTAB = 5

_iphlpapi = ctypes.windll.iphlpapi  # type: ignore[attr-defined]
_kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class _MIB_TCPROW_OWNER_PID(ctypes.Structure):
    _fields_ = [
        ("dwState", ctypes.wintypes.DWORD),
        ("dwLocalAddr", ctypes.wintypes.DWORD),
        ("dwLocalPort", ctypes.wintypes.DWORD),
        ("dwRemoteAddr", ctypes.wintypes.DWORD),
        ("dwRemotePort", ctypes.wintypes.DWORD),
        ("dwOwningPid", ctypes.wintypes.DWORD),
    ]


class _MIB_TCPTABLE_OWNER_PID(ctypes.Structure):
    _fields_ = [
        ("dwNumEntries", ctypes.wintypes.DWORD),
        ("table", _MIB_TCPROW_OWNER_PID * 1),
    ]


# Cache PID → exe name (PIDs don't change often)
_pid_cache: dict[int, str] = {}


def _pid_to_exe(pid: int) -> str:
    """Get exe name from PID. Cached."""
    if pid in _pid_cache:
        return _pid_cache[pid]
    try:
        h = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(260)
            size = ctypes.wintypes.DWORD(260)
            if _kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                exe = os.path.basename(buf.value)
                _pid_cache[pid] = exe
                return exe
        finally:
            _kernel32.CloseHandle(h)
    except Exception:
        pass
    return ""


def _ntohs(port: int) -> int:
    """Network byte order to host byte order for port."""
    return ((port & 0xFF) << 8) | ((port >> 8) & 0xFF)


@dataclass(slots=True)
class ProxyProcessInfo:
    exe: str
    connections: int
    pids: set[int]


def get_proxy_connections(socks_port: int = 10808, http_port: int = 8080) -> list[ProxyProcessInfo]:
    """Find processes connected to xray proxy ports.

    Returns list of ProxyProcessInfo sorted by connection count desc.
    Fast: uses kernel API, no HTTP requests. < 1ms typical.
    """
    target_ports = {socks_port, http_port}
    localhost = 0x0100007F  # 127.0.0.1 in network byte order

    # Get TCP table
    size = ctypes.wintypes.DWORD(0)
    _iphlpapi.GetExtendedTcpTable(None, ctypes.byref(size), False, _AF_INET, _TCP_TABLE_OWNER_PID_CONN, 0)

    buf = (ctypes.c_byte * size.value)()
    ret = _iphlpapi.GetExtendedTcpTable(buf, ctypes.byref(size), False, _AF_INET, _TCP_TABLE_OWNER_PID_CONN, 0)
    if ret != 0:
        return []

    table = ctypes.cast(buf, ctypes.POINTER(_MIB_TCPTABLE_OWNER_PID)).contents
    n = table.dwNumEntries

    # Access rows via raw pointer arithmetic
    row_array = ctypes.cast(
        ctypes.byref(table.table),
        ctypes.POINTER(_MIB_TCPROW_OWNER_PID * n),
    ).contents

    # Find connections to proxy ports on localhost
    by_exe: dict[str, ProxyProcessInfo] = {}
    for i in range(n):
        row = row_array[i]
        if row.dwState != _MIB_TCP_STATE_ESTAB:
            continue
        remote_port = _ntohs(row.dwRemotePort)
        if remote_port not in target_ports:
            continue
        if row.dwRemoteAddr != localhost:
            continue

        pid = row.dwOwningPid
        exe = _pid_to_exe(pid)
        if not exe or exe.lower() in ("xray.exe", "sing-box.exe"):
            continue

        if exe not in by_exe:
            by_exe[exe] = ProxyProcessInfo(exe=exe, connections=0, pids=set())
        by_exe[exe].connections += 1
        by_exe[exe].pids.add(pid)

    result = sorted(by_exe.values(), key=lambda p: p.connections, reverse=True)
    return result


def clear_pid_cache() -> None:
    """Clear PID→exe cache. Call on disconnect."""
    _pid_cache.clear()
