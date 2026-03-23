from __future__ import annotations

import os
import socket
from copy import deepcopy
from ipaddress import ip_network
from typing import Any

from .constants import (
    PROXY_HOST,
    ROUTING_DIRECT,
    ROUTING_GLOBAL,
    SINGBOX_CLASH_API_PORT,
    XRAY_STATS_API_PORT,
)
from .models import AppSettings, Node, RoutingSettings
from .service_presets import SERVICE_PRESETS_BY_ID


def _get_free_port() -> int:
    """Ask the OS for a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def needs_xray_hybrid(node: Node) -> bool:
    """Return True if node uses a transport that sing-box cannot handle natively."""
    stream = dict(node.outbound.get("streamSettings") or {})
    network = str(stream.get("network") or "tcp").lower()
    return network == "xhttp"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_singbox_config(
    node: Node,
    routing: RoutingSettings,
    settings: AppSettings,
) -> tuple[dict[str, Any], int | None, int | None]:
    """Build sing-box config.

    Returns (config, relay_port, protect_port).
    For native mode relay_port and protect_port are None.
    """
    if needs_xray_hybrid(node):
        relay_port = _get_free_port()
        protect_port = _get_free_port()
        cfg = _build_hybrid_config(node, routing, settings, relay_port, protect_port)
        return cfg, relay_port, protect_port
    return _build_native_config(node, routing, settings), None, None


def build_xray_relay_config(
    node: Node,
    routing: RoutingSettings,
    settings: AppSettings,
    relay_port: int,
    protect_port: int,
) -> dict[str, Any]:
    """Build xray config for hybrid TUN mode (v2rayN-style dialerProxy)."""
    from .config_builder import build_xray_config
    cfg = build_xray_config(node, routing, settings)

    # --- Inbounds: SS relay + API ---
    cfg["inbounds"] = [
        {
            "tag": "relay-in",
            "protocol": "shadowsocks",
            "listen": "127.0.0.1",
            "port": relay_port,
            "settings": {"method": "none", "password": "none", "network": "tcp,udp"},
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls", "quic"],
                "routeOnly": True,
            },
        },
        {
            "tag": "api",
            "listen": PROXY_HOST,
            "port": XRAY_STATS_API_PORT,
            "protocol": "dokodemo-door",
            "settings": {"address": PROXY_HOST},
        },
    ]

    # --- Outbounds: inject dialerProxy + add tun-protect SS ---
    _DIALER_PROXY_TAG = "tun-protect"

    # Add dialerProxy to all outbounds except block and tun-protect itself
    for ob in cfg["outbounds"]:
        tag = ob.get("tag", "")
        proto = ob.get("protocol", "")
        if proto == "blackhole" or tag == _DIALER_PROXY_TAG:
            continue
        stream = ob.setdefault("streamSettings", {})
        sockopt = stream.setdefault("sockopt", {})
        sockopt["dialerProxy"] = _DIALER_PROXY_TAG

    # Append tun-protect SS outbound (routes xray traffic back to sing-box → direct)
    cfg["outbounds"].append({
        "tag": _DIALER_PROXY_TAG,
        "protocol": "shadowsocks",
        "settings": {
            "servers": [{
                "address": "127.0.0.1",
                "port": protect_port,
                "method": "none",
                "password": "none",
            }],
        },
    })

    # Routing: no relay-in → proxy rule needed — the existing catch-all
    # ("network": "tcp,udp" → proxy) handles unmatched traffic.
    # Domain routing rules (steam → direct, youtube → proxy) apply to
    # relay-in traffic thanks to xray sniffing.

    return cfg


# ---------------------------------------------------------------------------
# Hybrid config (sing-box TUN + xray via SS bridge + dialerProxy)
# ---------------------------------------------------------------------------

def _build_hybrid_config(
    node: Node,
    routing: RoutingSettings,
    settings: AppSettings,
    relay_port: int,
    protect_port: int,
) -> dict[str, Any]:
    """sing-box TUN config with SS bridge to xray (v2rayN-style architecture)."""
    # SS outbound: sends captured traffic to xray's relay inbound
    proxy_outbound: dict[str, Any] = {
        "type": "shadowsocks",
        "tag": "proxy",
        "server": "127.0.0.1",
        "server_port": relay_port,
        "method": "none",
        "password": "none",
    }

    direct_out: dict[str, Any] = {"type": "direct", "tag": "direct"}
    block_out: dict[str, Any] = {"type": "block", "tag": "block"}

    outbounds = [proxy_outbound, direct_out, block_out]

    route_rules: list[dict[str, Any]] = []

    # Sniff + DNS hijack (sing-box 1.13 rule actions)
    route_rules.append({"action": "sniff"})
    route_rules.append({"protocol": "dns", "action": "hijack-dns"})

    # xray's dialerProxy traffic arrives on tun-protect inbound → must go direct
    route_rules.append({"inbound": ["tun-protect"], "outbound": "direct"})

    if routing.bypass_lan:
        route_rules.append({"ip_is_private": True, "outbound": "direct"})

    # Process-based routing (sing-box detects originating process via OS APIs)
    _append_process_rules(route_rules, routing)

    return {
        "log": {"level": "warn", "timestamp": True},
        "inbounds": [
            {
                "type": "tun",
                "tag": "tun-in",
                "interface_name": f"xftun{os.getpid() % 10000}",
                "address": ["172.19.0.1/30"],
                "auto_route": True,
                "strict_route": False,
                "stack": "mixed",
            },
            {
                "type": "shadowsocks",
                "tag": "tun-protect",
                "listen": "127.0.0.1",
                "listen_port": protect_port,
                "method": "none",
                "password": "none",
            },
        ],
        "outbounds": outbounds,
        "route": {
            "auto_detect_interface": True,
            "default_domain_resolver": "direct-dns",
            "rules": route_rules,
        },
        "dns": {
            "servers": [
                {"tag": "direct-dns", "type": "udp", "server": "8.8.8.8", "detour": "direct"},
            ],
            "final": "direct-dns",
        },
        "experimental": {
            "clash_api": {
                "external_controller": f"127.0.0.1:{SINGBOX_CLASH_API_PORT}",
            },
        },
    }


# ---------------------------------------------------------------------------
# Native config (sing-box handles everything, no xray needed)
# ---------------------------------------------------------------------------

def _build_native_config(
    node: Node,
    routing: RoutingSettings,
    settings: AppSettings,
) -> dict[str, Any]:
    proxy_outbound = _convert_outbound(deepcopy(node.outbound))
    proxy_outbound["tag"] = "proxy"
    proxy_outbound["domain_resolver"] = "proxy-dns"

    direct_out: dict[str, Any] = {"type": "direct", "tag": "direct", "domain_resolver": "proxy-dns"}
    block_out: dict[str, Any] = {"type": "block", "tag": "block"}

    outbounds = [proxy_outbound, direct_out, block_out]

    route_rules = _build_route_rules(routing, node)

    return {
        "log": {"level": "warn", "timestamp": True},
        "inbounds": [
            {
                "type": "tun",
                "tag": "tun-in",
                "interface_name": f"xftun{os.getpid() % 10000}",
                "address": ["172.19.0.1/30"],
                "auto_route": True,
                "strict_route": True,
                "stack": "mixed",
            },
        ],
        "outbounds": outbounds,
        "route": {
            "auto_detect_interface": True,
            "default_domain_resolver": "proxy-dns",
            "rules": route_rules,
        },
        "dns": {
            "servers": [
                {"tag": "proxy-dns", "type": "https", "server": "1.1.1.1", "detour": "proxy"},
            ],
            "final": "proxy-dns",
        },
        "experimental": {
            "clash_api": {
                "external_controller": f"127.0.0.1:{SINGBOX_CLASH_API_PORT}",
            },
        },
    }


# ---------------------------------------------------------------------------
# Outbound conversion (xray → sing-box format, for native mode)
# ---------------------------------------------------------------------------

def _convert_outbound(xray_ob: dict[str, Any]) -> dict[str, Any]:
    protocol = str(xray_ob.get("protocol") or "").lower()
    xray_settings = dict(xray_ob.get("settings") or {})
    stream = dict(xray_ob.get("streamSettings") or {})

    sb: dict[str, Any] = {"type": protocol}

    if protocol in ("vless", "vmess"):
        vnext = (xray_settings.get("vnext") or [{}])[0]
        sb["server"] = str(vnext.get("address") or "")
        sb["server_port"] = int(vnext.get("port") or 0)
        users = (vnext.get("users") or [{}])[0]
        sb["uuid"] = str(users.get("id") or "")
        if protocol == "vless":
            flow = str(users.get("flow") or "")
            if flow:
                sb["flow"] = flow
        if protocol == "vmess":
            sb["alter_id"] = int(users.get("alterId") or 0)
            sb["security"] = str(users.get("security") or "auto")

    elif protocol == "trojan":
        servers = (xray_settings.get("servers") or [{}])[0]
        sb["server"] = str(servers.get("address") or "")
        sb["server_port"] = int(servers.get("port") or 0)
        sb["password"] = str(servers.get("password") or "")

    elif protocol == "shadowsocks":
        servers = (xray_settings.get("servers") or [{}])[0]
        sb["server"] = str(servers.get("address") or "")
        sb["server_port"] = int(servers.get("port") or 0)
        sb["method"] = str(servers.get("method") or "")
        sb["password"] = str(servers.get("password") or "")

    elif protocol in ("socks", "http"):
        servers = (xray_settings.get("servers") or [{}])[0]
        sb["server"] = str(servers.get("address") or "")
        sb["server_port"] = int(servers.get("port") or 0)
        user_list = servers.get("users") or []
        if user_list:
            sb["username"] = str(user_list[0].get("user") or "")
            sb["password"] = str(user_list[0].get("pass") or "")

    _apply_tls(sb, stream)
    _apply_transport(sb, stream)

    return sb


def _apply_tls(sb: dict[str, Any], stream: dict[str, Any]) -> None:
    security = str(stream.get("security") or "").lower()
    if security not in ("tls", "reality"):
        return

    tls: dict[str, Any] = {"enabled": True}

    if security == "reality":
        reality_settings = dict(stream.get("realitySettings") or {})
        tls["server_name"] = str(reality_settings.get("serverName") or "")
        fp = str(reality_settings.get("fingerprint") or "")
        if fp:
            tls["utls"] = {"enabled": True, "fingerprint": fp}
        pub = str(reality_settings.get("publicKey") or "")
        sid = str(reality_settings.get("shortId") or "")
        tls["reality"] = {"enabled": True, "public_key": pub, "short_id": sid}
    else:
        tls_settings = dict(stream.get("tlsSettings") or {})
        sni = str(tls_settings.get("serverName") or "")
        if sni:
            tls["server_name"] = sni
        alpn = tls_settings.get("alpn")
        if alpn:
            tls["alpn"] = list(alpn)
        fp = str(tls_settings.get("fingerprint") or "")
        if fp:
            tls["utls"] = {"enabled": True, "fingerprint": fp}
        insecure = tls_settings.get("allowInsecure", False)
        if insecure:
            tls["insecure"] = True

    sb["tls"] = tls


def _apply_transport(sb: dict[str, Any], stream: dict[str, Any]) -> None:
    network = str(stream.get("network") or "tcp").lower()

    if network == "tcp":
        return

    if network == "ws":
        ws_settings = dict(stream.get("wsSettings") or {})
        transport: dict[str, Any] = {"type": "ws"}
        path = str(ws_settings.get("path") or "")
        if path:
            transport["path"] = path
        headers = dict(ws_settings.get("headers") or {})
        if headers:
            transport["headers"] = headers
        sb["transport"] = transport

    elif network in ("http", "h2"):
        h2_settings = dict(stream.get("httpSettings") or stream.get("h2Settings") or {})
        transport = {"type": "http"}
        host = h2_settings.get("host")
        if host:
            transport["host"] = list(host) if isinstance(host, list) else [str(host)]
        path = str(h2_settings.get("path") or "")
        if path:
            transport["path"] = path
        sb["transport"] = transport

    elif network == "grpc":
        grpc_settings = dict(stream.get("grpcSettings") or {})
        transport = {"type": "grpc"}
        sn = str(grpc_settings.get("serviceName") or "")
        if sn:
            transport["service_name"] = sn
        sb["transport"] = transport

    elif network == "xhttp":
        sb["_unsupported_transport"] = "xhttp"


# ---------------------------------------------------------------------------
# Routing rules (for native sing-box mode)
# ---------------------------------------------------------------------------

def _build_route_rules(routing: RoutingSettings, node: Node) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []

    rules.append({"action": "sniff"})
    rules.append({"protocol": "dns", "action": "hijack-dns"})

    bypass_ips = ["8.8.8.8/32", "8.8.4.4/32", "1.1.1.1/32"]
    if node.server:
        bypass_ips.append(f"{node.server}/32")
    rules.append({"ip_cidr": bypass_ips, "outbound": "direct"})

    if routing.bypass_lan:
        rules.append({"ip_is_private": True, "outbound": "direct"})

    _append_singbox_rules(rules, routing.direct_domains, "direct")
    _append_singbox_rules(rules, routing.block_domains, "block")
    _append_singbox_rules(rules, routing.proxy_domains, "proxy")

    _append_process_rules(rules, routing)

    mode = routing.mode
    if mode == ROUTING_DIRECT:
        rules.append({"inbound": ["tun-in"], "outbound": "direct"})

    return rules


def _append_process_rules(rules: list[dict[str, Any]], routing: RoutingSettings) -> None:
    """Group process rules by action and append as sing-box process_name rules."""
    proc_by_action: dict[str, list[str]] = {}
    for pr in routing.process_rules:
        name = pr.get("process", "").strip()
        action = pr.get("action", "proxy")
        if name and action in ("direct", "proxy", "block"):
            proc_by_action.setdefault(action, []).append(name)
    for action, names in proc_by_action.items():
        rules.append({"process_name": names, "outbound": action})


def _append_singbox_rules(
    rules: list[dict[str, Any]],
    items: list[str],
    outbound: str,
) -> None:
    domain_suffix: list[str] = []
    domain_full: list[str] = []
    domain_keyword: list[str] = []
    ip_cidr: list[str] = []

    for raw in items:
        value = raw.strip()
        if not value:
            continue

        if value.startswith("domain:"):
            domain_suffix.append(value[len("domain:"):])
        elif value.startswith("full:"):
            domain_full.append(value[len("full:"):])
        elif value.startswith("keyword:"):
            domain_keyword.append(value[len("keyword:"):])
        elif value.startswith("geosite:") or value.startswith("geoip:"):
            continue
        else:
            try:
                ip_network(value, strict=False)
                ip_cidr.append(value)
                continue
            except ValueError:
                pass
            domain_suffix.append(value)

    if domain_suffix:
        rules.append({"domain_suffix": domain_suffix, "outbound": outbound})
    if domain_full:
        rules.append({"domain": domain_full, "outbound": outbound})
    if domain_keyword:
        rules.append({"domain_keyword": domain_keyword, "outbound": outbound})
    if ip_cidr:
        rules.append({"ip_cidr": ip_cidr, "outbound": outbound})
