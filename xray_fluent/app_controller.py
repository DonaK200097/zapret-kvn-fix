from __future__ import annotations

import logging
from datetime import datetime, timezone
import json
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .config_builder import build_xray_config
from .connectivity_test import ConnectivityTestWorker
from .constants import APP_NAME, LOG_DIR, ROUTING_MODES, SINGBOX_CLASH_API_PORT, XRAY_STATS_API_PORT
from .diagnostics import export_diagnostics
from .link_parser import parse_links_text
from .live_metrics_worker import LiveMetricsWorker
from .models import AppSettings, AppState, Node
from .network_monitor import NetworkMonitor
from .ping_worker import PingWorker
from .proxy_manager import ProxyManager
from .security import create_password_hash, get_idle_seconds, verify_password
from .tun2socks_manager import Tun2SocksManager
from .singbox_manager import SingBoxManager, get_singbox_version
from .storage import PassphraseRequired, StateStorage
from .startup import build_startup_command, set_startup_enabled
from .xray_core_updater import XrayCoreUpdateResult, XrayCoreUpdateWorker
from .xray_manager import XrayManager, get_xray_version


class AppController(QObject):
    nodes_changed = pyqtSignal(object)
    selection_changed = pyqtSignal(object)
    connection_changed = pyqtSignal(bool)
    routing_changed = pyqtSignal(object)
    settings_changed = pyqtSignal(object)
    log_line = pyqtSignal(str)
    status = pyqtSignal(str, str)
    ping_updated = pyqtSignal(str, object)
    connectivity_test_done = pyqtSignal(bool, str, object)
    live_metrics_updated = pyqtSignal(object)
    xray_update_result = pyqtSignal(object)
    lock_state_changed = pyqtSignal(bool)
    passphrase_required = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.storage = StateStorage()
        self.xray = XrayManager(self)
        self.singbox = SingBoxManager(self)
        self.tun2socks = Tun2SocksManager(self)
        self.proxy = ProxyManager()
        self.network_monitor = NetworkMonitor(parent=self)

        self.state = AppState()
        self.recent_logs: list[str] = []
        self.connected = False
        self.locked = False

        # --- File logger (5 MB × 3 rotated files in data/logs/) ---
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger("xray_fluent")
        self._logger.setLevel(logging.DEBUG)
        if not self._logger.handlers:
            handler = RotatingFileHandler(
                LOG_DIR / "app.log",
                maxBytes=5 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
            self._logger.addHandler(handler)

        self._ping_worker: PingWorker | None = None
        self._connectivity_worker: ConnectivityTestWorker | None = None
        self._metrics_worker: LiveMetricsWorker | None = None
        self._xray_update_worker: XrayCoreUpdateWorker | None = None
        self._xray_update_silent = False
        self._reconnect_after_xray_update = False
        self._reconnecting = False
        self._active_core: str = "xray"  # "xray" or "singbox"

        self.xray.log_received.connect(self._on_xray_log)
        self.xray.error.connect(self._on_xray_error)
        self.xray.state_changed.connect(self._on_core_state_changed)

        self.singbox.log_received.connect(self._on_xray_log)
        self.singbox.error.connect(self._on_singbox_error)
        self.singbox.state_changed.connect(self._on_core_state_changed)

        self.tun2socks.log_received.connect(self._on_xray_log)
        self.tun2socks.error.connect(self._on_singbox_error)
        self.tun2socks.state_changed.connect(self._on_core_state_changed)

        self.network_monitor.network_changed.connect(self._on_network_changed)

        self._lock_timer = QTimer(self)
        self._lock_timer.setInterval(15_000)
        self._lock_timer.timeout.connect(self._check_auto_lock)

    def load(self) -> bool:
        try:
            self.state = self.storage.load()
        except PassphraseRequired:
            self.passphrase_required.emit()
            return False

        self.nodes_changed.emit(self.state.nodes)
        self.selection_changed.emit(self.selected_node)
        self.routing_changed.emit(self.state.routing)
        self.settings_changed.emit(self.state.settings)

        version = get_xray_version(self.state.settings.xray_path)
        if version:
            self._log(f"[core] {version}")
        else:
            self.status.emit("warning", "Cannot read Xray core version")

        sb_version = get_singbox_version(self.state.settings.singbox_path)
        if sb_version:
            self._log(f"[core] sing-box: {sb_version}")

        self.network_monitor.start()
        self._lock_timer.start()
        return True

    def set_data_passphrase(self, passphrase: str) -> None:
        self.storage.passphrase = passphrase
        self.save()
        self.status.emit("success", "Data encryption enabled")

    def clear_data_passphrase(self) -> None:
        self.storage.passphrase = ""
        self.save()
        self.status.emit("info", "Data encryption disabled (portable mode)")

    def is_data_encrypted(self) -> bool:
        return self.storage.is_encrypted()

    def save(self) -> None:
        self.storage.save(self.state)

    def shutdown(self) -> None:
        if self._ping_worker and self._ping_worker.isRunning():
            self._ping_worker.cancel()
            self._ping_worker.wait(500)
        if self._connectivity_worker and self._connectivity_worker.isRunning():
            self._connectivity_worker.wait(1000)
        self._stop_metrics_worker()
        if self._xray_update_worker and self._xray_update_worker.isRunning():
            self._xray_update_worker.wait(1000)

        self.disconnect_current()
        # Ensure all cores are stopped
        if self.tun2socks.is_running:
            self.tun2socks.stop()
        if self.singbox.is_running:
            self.singbox.stop()
        if self.xray.is_running:
            self.xray.stop()
        # Always disable system proxy on exit to prevent leaked proxy
        if self.proxy.is_enabled():
            self.proxy.disable(restore_previous=True)
        # Remove lingering TUN adapter
        self._cleanup_tun_adapter()
        self.network_monitor.stop()
        self._lock_timer.stop()
        self.save()

    @staticmethod
    def _cleanup_tun_adapter() -> None:
        """Remove the wintun TUN adapter if it was left behind."""
        import subprocess as _sp
        try:
            result = _sp.run(
                ["netsh", "interface", "show", "interface"],
                capture_output=True, text=True, timeout=5,
                creationflags=0x08000000,
            )
            if "XrayFluentTUN" in (result.stdout or ""):
                _sp.run(
                    ["netsh", "interface", "set", "interface", "XrayFluentTUN", "admin=disable"],
                    capture_output=True, timeout=5,
                    creationflags=0x08000000,
                )
        except Exception:
            pass

    @property
    def selected_node(self) -> Node | None:
        return self._get_node_by_id(self.state.selected_node_id)

    def _get_node_by_id(self, node_id: str | None) -> Node | None:
        if not node_id:
            return None
        for node in self.state.nodes:
            if node.id == node_id:
                return node
        return None

    def export_node_outbound_json(self, node_id: str | None = None) -> str | None:
        node = self._get_node_by_id(node_id) if node_id else self.selected_node
        if not node:
            return None
        return json.dumps(node.outbound, ensure_ascii=True, indent=2)

    def export_runtime_config_json(self, node_id: str | None = None) -> str | None:
        node = self._get_node_by_id(node_id) if node_id else self.selected_node
        if not node:
            return None
        cfg = build_xray_config(node, self.state.routing, self.state.settings)
        return json.dumps(cfg, ensure_ascii=True, indent=2)

    def import_nodes_from_text(self, text: str) -> tuple[int, list[str]]:
        nodes, errors = parse_links_text(text)
        if not nodes:
            return 0, errors

        existing_links = {node.link for node in self.state.nodes}
        first_new_id: str | None = None
        added = 0
        for node in nodes:
            if node.link in existing_links:
                continue
            self.state.nodes.append(node)
            existing_links.add(node.link)
            if first_new_id is None:
                first_new_id = node.id
            added += 1

        if first_new_id:
            self.state.selected_node_id = first_new_id
        elif not self.state.selected_node_id and self.state.nodes:
            self.state.selected_node_id = self.state.nodes[0].id

        self.nodes_changed.emit(self.state.nodes)
        self.selection_changed.emit(self.selected_node)
        self.save()

        if added:
            # In TUN mode, hot-swap xray instead of full reconnect
            if self._active_core == "tun2socks" and self.tun2socks.is_running:
                self._hot_swap_xray("new node imported")
            else:
                self.connect_selected()

        return added, errors

    def remove_nodes(self, node_ids: set[str]) -> None:
        if not node_ids:
            return
        self.state.nodes = [node for node in self.state.nodes if node.id not in node_ids]
        if self.state.selected_node_id in node_ids:
            self.state.selected_node_id = self.state.nodes[0].id if self.state.nodes else None
        self.nodes_changed.emit(self.state.nodes)
        self.selection_changed.emit(self.selected_node)
        self.save()

    def update_node(self, node_id: str, updates: dict) -> bool:
        node = self._get_node_by_id(node_id)
        if not node:
            return False
        if "name" in updates:
            node.name = updates["name"]
        if "group" in updates:
            node.group = updates["group"]
        if "tags" in updates:
            node.tags = list(updates["tags"])
        self.nodes_changed.emit(self.state.nodes)
        self.save()
        return True

    def bulk_update_nodes(self, node_ids: set[str], operations: dict) -> int:
        group = operations.get("group", "")
        add_tags = operations.get("add_tags", [])
        remove_tags = set(operations.get("remove_tags", []))
        updated = 0
        for node in self.state.nodes:
            if node.id not in node_ids:
                continue
            if group:
                node.group = group
            if add_tags:
                existing = set(node.tags)
                for tag in add_tags:
                    if tag not in existing:
                        node.tags.append(tag)
            if remove_tags:
                node.tags = [t for t in node.tags if t not in remove_tags]
            updated += 1
        if updated:
            self.nodes_changed.emit(self.state.nodes)
            self.save()
        return updated

    def get_all_groups(self) -> list[str]:
        groups = {node.group for node in self.state.nodes if node.group}
        return sorted(groups)

    def get_all_tags(self) -> list[str]:
        tags: set[str] = set()
        for node in self.state.nodes:
            tags.update(node.tags)
        return sorted(tags)

    def set_selected_node(self, node_id: str) -> None:
        if self.state.selected_node_id == node_id:
            return
        self.state.selected_node_id = node_id
        self.selection_changed.emit(self.selected_node)
        self.save()

        # Defer connection work so the UI updates immediately
        if self.connected:
            # In TUN mode, only restart xray — keep tun2socks TUN alive
            if self._active_core == "tun2socks" and self.state.settings.tun_mode:
                QTimer.singleShot(0, lambda: self._hot_swap_xray("node switched"))
            else:
                QTimer.singleShot(0, lambda: self._reconnect("node switched"))
        else:
            QTimer.singleShot(0, self.connect_selected)

    def connect_selected(self, allow_during_reconnect: bool = False) -> bool:
        if self._reconnecting and not allow_during_reconnect:
            self.status.emit("info", "Reconnect in progress")
            return False

        if self.locked:
            self.status.emit("warning", "App is locked. Unlock to connect.")
            return False

        node = self.selected_node
        if not node:
            self.status.emit("warning", "Select a node first.")
            return False

        tun = self.state.settings.tun_mode

        if tun:
            self._log(f"[tun] attempting TUN connect, admin={_is_admin()}")
            if not _is_admin():
                self._log("[tun] NOT admin — aborting")
                self.status.emit("error", "TUN mode requires running as Administrator.")
                return False

            # TUN doesn't use system proxy — disable if it was left on
            if self.proxy.is_enabled():
                self.proxy.disable(restore_previous=True)

            # Start xray with SOCKS inbound for tun2socks
            xray_cfg = build_xray_config(node, self.state.routing, self.state.settings)
            # Suppress per-connection logging in TUN mode (xhttp creates hundreds)
            xray_cfg["log"] = {"loglevel": "error"}
            # Remove HTTP inbound (keep SOCKS and API)
            socks_port = self.state.settings.socks_port
            xray_cfg["inbounds"] = [
                ib for ib in xray_cfg.get("inbounds", [])
                if ib.get("protocol") != "http"
            ]
            # Block LAN/link-local/broadcast traffic that tun2socks floods
            routing = xray_cfg.setdefault("routing", {})
            rules = routing.setdefault("rules", [])
            rules.insert(0, {
                "type": "field",
                "ip": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "224.0.0.0/4", "255.255.255.255/32"],
                "outboundTag": "block",
            })
            xray_ok = self.xray.start(self.state.settings.xray_path, xray_cfg)
            if not xray_ok:
                self._log("[tun] xray start failed")
                return False

            # Start tun2socks pointing to xray SOCKS
            self.status.emit("info", "Creating TUN adapter...")
            self._log(f"[tun] starting tun2socks -> SOCKS 127.0.0.1:{socks_port}")
            tun_ok = self.tun2socks.start(socks_port, server_ip=node.server)
            self._log(f"[tun] tun2socks start result: {tun_ok}")
            if not tun_ok:
                self.xray.stop()
                return False
            self._active_core = "tun2socks"
        else:
            config = build_xray_config(node, self.state.routing, self.state.settings)
            ok = self.xray.start(self.state.settings.xray_path, config)
            if not ok:
                return False
            self._active_core = "xray"

            if self.state.settings.enable_system_proxy:
                self.proxy.enable(
                    self.state.settings.http_port,
                    self.state.settings.socks_port,
                    bypass_lan=self.state.routing.bypass_lan,
                )

        node.last_used_at = datetime.now(timezone.utc).isoformat()
        self.status.emit("success", f"Connected: {node.name}" + (" (TUN)" if tun else ""))
        self.save()
        return True

    def disconnect_current(self, disable_proxy: bool = True, emit_status: bool = True) -> bool:
        if self._active_core == "tun2socks":
            stopped = self.tun2socks.stop()
            if self.xray.is_running:
                self.xray.stop()
        elif self._active_core == "singbox":
            stopped = self.singbox.stop()
            if self.xray.is_running:
                self.xray.stop()
        else:
            stopped = self.xray.stop()
            if disable_proxy and self.state.settings.enable_system_proxy:
                self.proxy.disable(restore_previous=True)
        if emit_status:
            self.status.emit("info", "Disconnected")
        return stopped

    def toggle_connection(self) -> None:
        """Emergency override for tray icon."""
        if self.connected:
            self.disconnect_current()
        else:
            self.connect_selected()

    def switch_next_node(self) -> None:
        if not self.state.nodes:
            return
        current_id = self.state.selected_node_id
        index = 0
        if current_id:
            for idx, node in enumerate(self.state.nodes):
                if node.id == current_id:
                    index = idx
                    break
        index = (index + 1) % len(self.state.nodes)
        self.set_selected_node(self.state.nodes[index].id)

    def switch_prev_node(self) -> None:
        if not self.state.nodes:
            return
        current_id = self.state.selected_node_id
        index = 0
        if current_id:
            for idx, node in enumerate(self.state.nodes):
                if node.id == current_id:
                    index = idx
                    break
        index = (index - 1) % len(self.state.nodes)
        self.set_selected_node(self.state.nodes[index].id)

    def update_routing(
        self,
        mode: str,
        direct_domains: list[str],
        proxy_domains: list[str],
        block_domains: list[str],
        bypass_lan: bool,
        dns_mode: str,
    ) -> None:
        if mode not in ROUTING_MODES:
            mode = "rule"
        self.state.routing.mode = mode
        self.state.routing.direct_domains = direct_domains
        self.state.routing.proxy_domains = proxy_domains
        self.state.routing.block_domains = block_domains
        self.state.routing.bypass_lan = bypass_lan
        self.state.routing.dns_mode = dns_mode
        self.routing_changed.emit(self.state.routing)
        self.save()

        if self.connected:
            self._reconnect("routing changed")

    def update_settings(self, settings: AppSettings) -> None:
        old_launch = self.state.settings.launch_on_startup
        old_tun = self.state.settings.tun_mode
        self.state.settings = settings
        self.settings_changed.emit(self.state.settings)
        self.save()

        if old_launch != settings.launch_on_startup:
            try:
                set_startup_enabled(APP_NAME, settings.launch_on_startup, build_startup_command())
            except Exception as exc:
                self.status.emit("error", f"startup setting failed: {exc}")

        if old_tun != settings.tun_mode and self.connected:
            self._reconnect("TUN mode toggled")
            return

        if not settings.tun_mode:
            if self.connected and not settings.enable_system_proxy:
                self.proxy.disable(restore_previous=True)
            elif self.connected and settings.enable_system_proxy:
                self.proxy.enable(
                    settings.http_port,
                    settings.socks_port,
                    bypass_lan=self.state.routing.bypass_lan,
                )

    def ping_nodes(self, node_ids: set[str] | None = None) -> None:
        nodes = self.state.nodes
        if node_ids:
            nodes = [node for node in nodes if node.id in node_ids]
        if not nodes:
            return

        if self._ping_worker and self._ping_worker.isRunning():
            self._ping_worker.cancel()
            self._ping_worker.wait(500)

        self._ping_worker = PingWorker(nodes)
        self._ping_worker.result.connect(self._on_ping_result)
        self._ping_worker.completed.connect(self._on_ping_complete)
        self._ping_worker.start()

    def test_connectivity(self, url: str | None = None) -> None:
        target = (url or "https://www.gstatic.com/generate_204").strip()
        if not target:
            target = "https://www.gstatic.com/generate_204"

        if self._connectivity_worker and self._connectivity_worker.isRunning():
            self.status.emit("info", "Connection test already running")
            return

        self._connectivity_worker = ConnectivityTestWorker(
            self.state.settings.http_port, target, tun_mode=self.state.settings.tun_mode,
        )
        self._connectivity_worker.result.connect(self._on_connectivity_result)
        self._connectivity_worker.start()

    def run_xray_core_update(self, apply_update: bool, silent: bool = False) -> None:
        if self._xray_update_worker and self._xray_update_worker.isRunning():
            if not silent:
                self.status.emit("info", "Xray update task is already running")
            return

        if apply_update and self.connected:
            self._reconnect_after_xray_update = True
            self.disconnect_current()
        else:
            self._reconnect_after_xray_update = False

        self._xray_update_silent = silent
        self._xray_update_worker = XrayCoreUpdateWorker(
            self.state.settings.xray_path,
            self.state.settings.xray_release_channel,
            self.state.settings.xray_update_feed_url,
            apply_update=apply_update,
        )
        self._xray_update_worker.done.connect(self._on_xray_update_worker_done)
        self._xray_update_worker.start()

        if not silent:
            message = "Updating Xray core..." if apply_update else "Checking Xray core updates..."
            self.status.emit("info", message)

    def _start_metrics_worker(self) -> None:
        node = self.selected_node
        ping_host = node.server if node else ""
        ping_port = node.port if node else 0

        self._stop_metrics_worker()
        mode = "singbox" if self._active_core == "singbox" else "xray"
        self._metrics_worker = LiveMetricsWorker(
            self.state.settings.xray_path,
            XRAY_STATS_API_PORT,
            ping_host=ping_host,
            ping_port=ping_port,
            mode=mode,
            clash_api_port=SINGBOX_CLASH_API_PORT,
        )
        self._metrics_worker.metrics.connect(self._on_live_metrics)
        self._metrics_worker.start()

    def _stop_metrics_worker(self) -> None:
        if not self._metrics_worker:
            return
        if self._metrics_worker.isRunning():
            self._metrics_worker.stop()
            self._metrics_worker.wait(1200)
        self._metrics_worker = None

    def set_master_password(self, password: str) -> None:
        password_hash, salt = create_password_hash(password)
        self.state.security.enabled = True
        self.state.security.password_hash = password_hash
        self.state.security.salt = salt
        self.save()

    def disable_master_password(self) -> None:
        self.state.security.enabled = False
        self.state.security.password_hash = ""
        self.state.security.salt = ""
        self.locked = False
        self.lock_state_changed.emit(False)
        self.save()

    def unlock(self, password: str) -> bool:
        if not self.state.security.enabled:
            self.locked = False
            self.lock_state_changed.emit(False)
            return True

        ok = verify_password(password, self.state.security.password_hash, self.state.security.salt)
        if ok:
            self.locked = False
            self.lock_state_changed.emit(False)
        return ok

    def lock(self) -> None:
        if not self.state.security.enabled:
            return
        self.locked = True
        self.lock_state_changed.emit(True)
        self.disconnect_current()

    def build_diagnostics(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = LOG_DIR / f"diagnostics_{stamp}.zip"
        return export_diagnostics(output, self.state, self.recent_logs)

    def auto_connect_if_needed(self) -> None:
        if self.selected_node is not None and not self.locked:
            self.connect_selected()

    def _log(self, line: str) -> None:
        """Send a log line to the UI and write it to the log file."""
        self.recent_logs.append(line)
        if len(self.recent_logs) > 5000:
            self.recent_logs = self.recent_logs[-5000:]
        self._logger.info(line)
        self.log_line.emit(line)

    def _on_xray_log(self, line: str) -> None:
        # In TUN mode, throttle noisy per-connection logs to prevent UI freeze
        if self._active_core == "tun2socks" and "accepted" in line:
            self._tun_log_count = getattr(self, "_tun_log_count", 0) + 1
            # Only log to file, skip UI — emit summary every 100 lines
            self._logger.info(line)
            self.recent_logs.append(line)
            if len(self.recent_logs) > 5000:
                self.recent_logs = self.recent_logs[-5000:]
            if self._tun_log_count % 100 == 0:
                self.log_line.emit(f"[tun] {self._tun_log_count} connections routed...")
            return
        self._log(line)

    def _on_xray_error(self, message: str) -> None:
        self._log(f"[xray-error] {message}")
        self.status.emit("error", message)

    def _on_singbox_error(self, message: str) -> None:
        self._log(f"[singbox-error] {message}")
        self.status.emit("error", message)

    def _on_core_state_changed(self, running: bool) -> None:
        self.connected = running
        self.connection_changed.emit(running)
        if running:
            self._start_metrics_worker()
        else:
            self._stop_metrics_worker()
            self.live_metrics_updated.emit({"down_bps": 0.0, "up_bps": 0.0, "latency_ms": None})
        if not running and self._active_core == "xray" and self.state.settings.enable_system_proxy and not self._reconnecting:
            self.proxy.disable(restore_previous=True)

    def _on_ping_result(self, node_id: str, ping_ms: int | None) -> None:
        for node in self.state.nodes:
            if node.id == node_id:
                node.ping_ms = ping_ms
                break
        self.ping_updated.emit(node_id, ping_ms)

    def _on_ping_complete(self) -> None:
        self.nodes_changed.emit(self.state.nodes)
        self.save()

    def _on_connectivity_result(self, ok: bool, message: str, elapsed_ms: int | None) -> None:
        if ok and elapsed_ms is not None:
            text = f"Connectivity ok: {elapsed_ms} ms"
            self.status.emit("success", text)
            self._log(f"[test] {message} ({elapsed_ms} ms)")
        else:
            self.status.emit("warning", "Connectivity test failed")
            self._log(f"[test] {message}")
        self.connectivity_test_done.emit(ok, message, elapsed_ms)

    def _on_live_metrics(self, payload: dict[str, object]) -> None:
        self.live_metrics_updated.emit(payload)

    def _on_xray_update_worker_done(self, result: XrayCoreUpdateResult) -> None:
        self._xray_update_worker = None
        self.xray_update_result.emit(result)

        if result.status == "error":
            self.status.emit("error", result.message)
        elif result.status == "updated":
            if not self._xray_update_silent:
                self.status.emit("success", result.message)
            self._log(f"[core-update] {result.message}")
        elif result.status == "available":
            if not self._xray_update_silent:
                self.status.emit("warning", result.message)
            else:
                self._log(f"[core-update] {result.message}")
        elif result.status == "up_to_date":
            if not self._xray_update_silent:
                self.status.emit("info", result.message)
            else:
                self._log(f"[core-update] {result.message}")

        if self._reconnect_after_xray_update:
            self._reconnect_after_xray_update = False
            self.connect_selected()

        self._xray_update_silent = False

    def _on_network_changed(self, old: str, new: str) -> None:
        self._log(f"[network] changed: {old} -> {new}")
        # TUN mode creates a virtual adapter which triggers network change —
        # reconnecting would kill the TUN and cause an infinite loop
        if self._active_core in ("singbox", "tun2socks") and self.state.settings.tun_mode:
            self._log("[network] ignoring change in TUN mode")
            return
        if self.connected and self.state.settings.reconnect_on_network_change:
            self._reconnect("network changed")

    def _hot_swap_xray(self, reason: str) -> None:
        """Restart only xray while keeping tun2socks TUN alive."""
        node = self.selected_node
        if not node:
            return
        self._log(f"[hot-swap] {reason} — restarting xray only, TUN stays up")
        self.xray.stop()
        xray_cfg = build_xray_config(node, self.state.routing, self.state.settings)
        xray_cfg["log"] = {"loglevel": "error"}
        xray_cfg["inbounds"] = [
            ib for ib in xray_cfg.get("inbounds", [])
            if ib.get("protocol") != "http"
        ]
        routing = xray_cfg.setdefault("routing", {})
        rules = routing.setdefault("rules", [])
        rules.insert(0, {
            "type": "field",
            "ip": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "224.0.0.0/4", "255.255.255.255/32"],
            "outboundTag": "block",
        })
        ok = self.xray.start(self.state.settings.xray_path, xray_cfg)
        if ok:
            node.last_used_at = datetime.now(timezone.utc).isoformat()
            self.status.emit("success", f"Switched: {node.name} (TUN)")
            self.save()
        else:
            self._log("[hot-swap] xray restart failed")
            self.status.emit("error", "Failed to switch node")

    def _reconnect(self, reason: str) -> None:
        if self._reconnecting:
            return
        self._reconnecting = True
        try:
            self._log(f"[reconnect] {reason}")
            stopped = self.disconnect_current(disable_proxy=False, emit_status=False)
            if not stopped:
                self.status.emit("error", "Failed to stop previous Xray process")
                if self.state.settings.enable_system_proxy:
                    self.proxy.disable(restore_previous=True)
                return

            ok = self.connect_selected(allow_during_reconnect=True)
            if not ok and self.state.settings.enable_system_proxy:
                self.proxy.disable(restore_previous=True)
        finally:
            self._reconnecting = False

    def export_backup(self, path: Path, passphrase: str = "") -> None:
        self.storage.export_backup(path, passphrase)

    def import_backup(self, path: Path, passphrase: str = "") -> None:
        self.state = self.storage.import_backup(path, passphrase)
        self.save()
        self.nodes_changed.emit(self.state.nodes)
        self.selection_changed.emit(self.selected_node)
        self.routing_changed.emit(self.state.routing)
        self.settings_changed.emit(self.state.settings)

    def _check_auto_lock(self) -> None:
        if not self.state.security.enabled:
            return
        if self.locked:
            return
        minutes = max(1, self.state.security.auto_lock_minutes)
        if get_idle_seconds() >= minutes * 60:
            self.lock()


def _is_admin() -> bool:
    import ctypes
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False
