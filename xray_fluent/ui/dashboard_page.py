from __future__ import annotations

from collections import deque

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    ComboBox,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    SubtitleLabel,
)

from ..models import AppSettings, Node, RoutingSettings
from .traffic_graph import TrafficGraphDialog, TrafficGraphWidget


def _format_speed(value_bps: float) -> str:
    value = max(0.0, value_bps)
    units = ["B/s", "KB/s", "MB/s", "GB/s"]
    unit_index = 0
    while value >= 1024.0 and unit_index < len(units) - 1:
        value /= 1024.0
        unit_index += 1
    if unit_index == 0:
        return f"{int(value)} {units[unit_index]}"
    return f"{value:.2f} {units[unit_index]}"


def _format_latency(value_ms: int | None) -> str:
    if value_ms is None:
        return "--"
    return f"{value_ms} ms"


def _mode_title(mode: str) -> str:
    mapping = {
        "global": "Global",
        "rule": "Rule",
        "direct": "Direct",
    }
    return mapping.get(mode, mode.title() or "Unknown")


class DashboardPage(QWidget):
    toggle_connection_requested = pyqtSignal()
    test_requested = pyqtSignal()
    node_selected = pyqtSignal(str)
    next_requested = pyqtSignal()
    prev_requested = pyqtSignal()
    mode_changed = pyqtSignal(str)
    nodes_requested = pyqtSignal()
    routing_requested = pyqtSignal()
    logs_requested = pyqtSignal()
    settings_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("dashboard")

        self._nodes: list[Node] = []
        self._node_ids: list[str] = []
        self._selected_node: Node | None = None
        self._connected = False
        self._mode = "rule"
        self._settings = AppSettings()
        self._routing = RoutingSettings()
        self._selected_latency_ms: int | None = None
        self._live_rtt_ms: int | None = None
        self._last_down_bps = 0.0
        self._last_up_bps = 0.0
        self._peak_bps = 0.0
        self._down_history: deque[float] = deque(maxlen=300)
        self._up_history: deque[float] = deque(maxlen=300)
        self._detail_dialog: TrafficGraphDialog | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        root.addWidget(SubtitleLabel("Dashboard", self))
        self.summary_label = CaptionLabel("Minimal overview of connection, profile, traffic, and routing.", self)
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self.connection_card = CardWidget(self)
        connection_layout = QVBoxLayout(self.connection_card)
        connection_layout.setContentsMargins(18, 16, 18, 16)
        connection_layout.setSpacing(6)
        connection_layout.addWidget(StrongBodyLabel("Connection", self.connection_card))
        self.connection_state_label = SubtitleLabel("Standby", self.connection_card)
        self.connection_engine_label = BodyLabel("System proxy", self.connection_card)
        self.connection_status_label = CaptionLabel("Proxy is stopped", self.connection_card)
        self.connection_target_label = CaptionLabel("No active profile selected", self.connection_card)
        self.connection_target_label.setWordWrap(True)
        connection_layout.addWidget(self.connection_state_label)
        connection_layout.addWidget(self.connection_engine_label)
        connection_layout.addStretch(1)
        connection_layout.addWidget(self.connection_status_label)
        connection_layout.addWidget(self.connection_target_label)

        self.profile_card = CardWidget(self)
        profile_layout = QVBoxLayout(self.profile_card)
        profile_layout.setContentsMargins(18, 16, 18, 16)
        profile_layout.setSpacing(8)
        profile_layout.addWidget(StrongBodyLabel("Active profile", self.profile_card))
        self.node_combo = ComboBox(self.profile_card)
        profile_layout.addWidget(self.node_combo)
        self.profile_name_label = BodyLabel("No profile selected", self.profile_card)
        self.profile_endpoint_label = CaptionLabel("Import or choose a node first", self.profile_card)
        self.profile_group_label = CaptionLabel("Group: --", self.profile_card)
        self.profile_latency_label = CaptionLabel("Latency: --", self.profile_card)
        self.profile_endpoint_label.setWordWrap(True)
        profile_layout.addWidget(self.profile_name_label)
        profile_layout.addStretch(1)
        profile_layout.addWidget(self.profile_endpoint_label)
        profile_layout.addWidget(self.profile_group_label)
        profile_layout.addWidget(self.profile_latency_label)

        self.traffic_card = CardWidget(self)
        traffic_layout = QVBoxLayout(self.traffic_card)
        traffic_layout.setContentsMargins(18, 16, 18, 16)
        traffic_layout.setSpacing(6)
        traffic_layout.addWidget(StrongBodyLabel("Traffic", self.traffic_card))
        self.traffic_down_label = BodyLabel("Download: 0 B/s", self.traffic_card)
        self.traffic_up_label = BodyLabel("Upload: 0 B/s", self.traffic_card)
        self.traffic_rtt_label = BodyLabel("RTT: --", self.traffic_card)
        self.traffic_graph = TrafficGraphWidget(self.traffic_card)
        self.traffic_graph.clicked.connect(self._show_traffic_detail)
        self.traffic_peak_label = CaptionLabel("Peak: 0 B/s", self.traffic_card)
        traffic_layout.addWidget(self.traffic_down_label)
        traffic_layout.addWidget(self.traffic_up_label)
        traffic_layout.addWidget(self.traffic_rtt_label)
        traffic_layout.addWidget(self.traffic_graph, 1)
        traffic_layout.addWidget(self.traffic_peak_label)

        self.routing_card = CardWidget(self)
        routing_layout = QVBoxLayout(self.routing_card)
        routing_layout.setContentsMargins(18, 16, 18, 16)
        routing_layout.setSpacing(8)
        routing_layout.addWidget(StrongBodyLabel("Routing", self.routing_card))
        self.mode_combo = ComboBox(self.routing_card)
        self.mode_combo.addItem("Global", userData="global")
        self.mode_combo.addItem("Rule", userData="rule")
        self.mode_combo.addItem("Direct", userData="direct")
        routing_layout.addWidget(self.mode_combo)
        self.routing_mode_label = BodyLabel("Rule", self.routing_card)
        self.routing_dns_label = CaptionLabel("DNS: System", self.routing_card)
        self.routing_rules_label = CaptionLabel("Direct: 0   Proxy: 0   Block: 0", self.routing_card)
        self.routing_bypass_label = CaptionLabel("Bypass LAN: enabled", self.routing_card)
        self.routing_bypass_label.setWordWrap(True)
        routing_layout.addWidget(self.routing_mode_label)
        routing_layout.addStretch(1)
        routing_layout.addWidget(self.routing_dns_label)
        routing_layout.addWidget(self.routing_rules_label)
        routing_layout.addWidget(self.routing_bypass_label)

        grid.addWidget(self.connection_card, 0, 0)
        grid.addWidget(self.profile_card, 0, 1)
        grid.addWidget(self.traffic_card, 1, 0)
        grid.addWidget(self.routing_card, 1, 1)
        root.addLayout(grid)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)
        self.toggle_btn = PrimaryPushButton("Start Proxy", self)
        self.test_btn = PushButton("Connection test", self)
        self.nodes_btn = PushButton("Nodes", self)
        self.routing_btn = PushButton("Routing", self)
        self.logs_btn = PushButton("Logs", self)
        self.settings_btn = PushButton("Settings", self)
        actions_row.addWidget(self.toggle_btn)
        actions_row.addWidget(self.test_btn)
        actions_row.addWidget(self.nodes_btn)
        actions_row.addWidget(self.routing_btn)
        actions_row.addWidget(self.logs_btn)
        actions_row.addWidget(self.settings_btn)
        actions_row.addStretch(1)
        root.addLayout(actions_row)
        root.addStretch(1)

        self.node_combo.currentIndexChanged.connect(self._on_node_changed)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.toggle_btn.clicked.connect(self.toggle_connection_requested)
        self.test_btn.clicked.connect(self.test_requested)
        self.nodes_btn.clicked.connect(self.nodes_requested)
        self.routing_btn.clicked.connect(self.routing_requested)
        self.logs_btn.clicked.connect(self.logs_requested)
        self.settings_btn.clicked.connect(self.settings_requested)

        self._refresh_dashboard()

    def set_nodes(self, nodes: list[Node], selected_node_id: str | None) -> None:
        self._nodes = list(nodes)
        self._node_ids = []

        self.node_combo.blockSignals(True)
        self.node_combo.clear()

        selected_index = 0
        for index, node in enumerate(self._nodes):
            self.node_combo.addItem(self._node_title(node))
            self._node_ids.append(node.id)
            if selected_node_id and selected_node_id == node.id:
                selected_index = index

        if self._nodes:
            self.node_combo.setEnabled(True)
            self.node_combo.setCurrentIndex(selected_index)
            self._selected_node = self._nodes[selected_index]
        else:
            self.node_combo.addItem("No profiles imported")
            self.node_combo.setEnabled(False)
            self._selected_node = None

        self.node_combo.blockSignals(False)
        self._refresh_dashboard()

    def set_selected_node(self, node: Node | None) -> None:
        self._selected_node = node
        if node is not None and node.id in self._node_ids:
            self.node_combo.blockSignals(True)
            self.node_combo.setCurrentIndex(self._node_ids.index(node.id))
            self.node_combo.blockSignals(False)
        self._refresh_dashboard()

    def set_connection(self, connected: bool) -> None:
        self._connected = connected
        if not connected:
            self._last_down_bps = 0.0
            self._last_up_bps = 0.0
            self._live_rtt_ms = None
            self._peak_bps = 0.0
            self._down_history.clear()
            self._up_history.clear()
            self.traffic_graph.clear_data()
        self._refresh_dashboard()

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self._routing.mode = mode
        self.mode_combo.blockSignals(True)
        for index in range(self.mode_combo.count()):
            if self.mode_combo.itemData(index) == mode:
                self.mode_combo.setCurrentIndex(index)
                break
        self.mode_combo.blockSignals(False)
        self._refresh_dashboard()

    def set_proxy_ports(self, socks_port: int, http_port: int) -> None:
        self._settings.socks_port = socks_port
        self._settings.http_port = http_port
        self._settings.tun_mode = False
        self._refresh_dashboard()

    def set_tun_mode(self, enabled: bool) -> None:
        self._settings.tun_mode = enabled
        self._refresh_dashboard()

    def set_settings_snapshot(self, settings: AppSettings) -> None:
        self._settings = settings
        self._refresh_dashboard()

    def set_routing_snapshot(self, routing: RoutingSettings) -> None:
        self._routing = routing
        self.set_mode(routing.mode)

    def set_selected_latency(self, value: int | None) -> None:
        self._selected_latency_ms = value
        if self._selected_node is not None:
            self._selected_node.ping_ms = value
        self._refresh_dashboard()

    def set_live_metrics(self, down_bps: float, up_bps: float, latency_ms: int | None) -> None:
        self._last_down_bps = max(0.0, down_bps)
        self._last_up_bps = max(0.0, up_bps)
        self._live_rtt_ms = latency_ms
        self._peak_bps = max(self._peak_bps, self._last_down_bps, self._last_up_bps)
        self._down_history.append(self._last_down_bps)
        self._up_history.append(self._last_up_bps)
        self.traffic_graph.add_point(self._last_down_bps, self._last_up_bps)
        if self._detail_dialog is not None and self._detail_dialog.isVisible():
            self._detail_dialog.add_point(self._last_down_bps, self._last_up_bps)
        self._refresh_dashboard()

    def _refresh_dashboard(self) -> None:
        self._refresh_connection_card()
        self._refresh_profile_card()
        self._refresh_traffic_card()
        self._refresh_routing_card()
        has_profiles = bool(self._nodes)
        self.toggle_btn.setEnabled(has_profiles)
        self.test_btn.setEnabled(self._selected_node is not None)

    def _refresh_connection_card(self) -> None:
        action = "VPN" if self._settings.tun_mode else "Proxy"
        self.connection_state_label.setText("Connected" if self._connected else "Standby")
        self.connection_engine_label.setText(self._route_engine_label())
        self.connection_status_label.setText(f"{action} is {'running' if self._connected else 'stopped'}")
        self.connection_target_label.setText(self._selected_node_summary())
        self.toggle_btn.setText(self._toggle_action_text())
        self.summary_label.setText(self._summary_text())

    def _refresh_profile_card(self) -> None:
        selected = self._selected_node
        if selected is None:
            self.profile_name_label.setText("No profile selected")
            self.profile_endpoint_label.setText("Import or choose a node first")
            self.profile_group_label.setText(f"Profiles: {len(self._nodes)}")
            self.profile_latency_label.setText("Latency: --")
            return

        self.profile_name_label.setText(selected.name or "Unnamed profile")
        scheme = selected.scheme.upper() if selected.scheme else "NODE"
        self.profile_endpoint_label.setText(f"{selected.server or '--'}:{selected.port or '--'}  ({scheme})")
        self.profile_group_label.setText(f"Group: {selected.group or 'Default'}")
        self.profile_latency_label.setText(f"Latency: {_format_latency(self._effective_latency())}")

    def _refresh_traffic_card(self) -> None:
        self.traffic_down_label.setText(f"Download: {_format_speed(self._last_down_bps)}")
        self.traffic_up_label.setText(f"Upload: {_format_speed(self._last_up_bps)}")
        self.traffic_rtt_label.setText(f"RTT: {_format_latency(self._effective_latency())}")
        self.traffic_peak_label.setText(f"Peak: {_format_speed(self._peak_bps)}")

    def _refresh_routing_card(self) -> None:
        self.routing_mode_label.setText(_mode_title(self._routing.mode))
        self.routing_dns_label.setText(f"DNS: {self._routing.dns_mode.title()}")
        self.routing_rules_label.setText(
            f"Direct: {len(self._routing.direct_domains)}   Proxy: {len(self._routing.proxy_domains)}   Block: {len(self._routing.block_domains)}"
        )
        bypass = "enabled" if self._routing.bypass_lan else "disabled"
        self.routing_bypass_label.setText(f"Bypass LAN: {bypass}")

    def _effective_latency(self) -> int | None:
        return self._live_rtt_ms if self._live_rtt_ms is not None else self._selected_latency_ms

    def _route_engine_label(self) -> str:
        if self._settings.tun_mode:
            return "VPN mode (TUN)"
        if self._settings.enable_system_proxy:
            return f"System proxy  HTTP {self._settings.http_port} / SOCKS {self._settings.socks_port}"
        return f"Local proxy  HTTP {self._settings.http_port} / SOCKS {self._settings.socks_port}"

    def _toggle_action_text(self) -> str:
        noun = "VPN" if self._settings.tun_mode else "Proxy"
        verb = "Stop" if self._connected else "Start"
        return f"{verb} {noun}"

    def _selected_node_summary(self) -> str:
        if self._selected_node is None:
            return "No active profile selected"
        group = self._selected_node.group or "Default"
        scheme = self._selected_node.scheme.upper() if self._selected_node.scheme else "NODE"
        server = self._selected_node.server or "unknown-host"
        port = self._selected_node.port or "--"
        return f"{group}  {scheme}  {server}:{port}"

    def _summary_text(self) -> str:
        if self._selected_node is None:
            return "Choose a node to start the proxy or VPN and review the live session state."
        if self._connected:
            return f"Active session: {self._selected_node_summary()}"
        return f"Ready to start with {self._selected_node_summary()}"

    def _node_title(self, node: Node) -> str:
        name = node.name or node.server or "Unnamed"
        scheme = node.scheme.upper() if node.scheme else "NODE"
        return f"{name} ({scheme})"

    def _show_traffic_detail(self) -> None:
        self._detail_dialog = TrafficGraphDialog(self._down_history, self._up_history, self)
        self._detail_dialog.exec()
        self._detail_dialog = None

    def _on_node_changed(self, index: int) -> None:
        if 0 <= index < len(self._node_ids):
            self.node_selected.emit(self._node_ids[index])

    def _on_mode_changed(self, index: int) -> None:
        value = self.mode_combo.itemData(index)
        if value:
            self.mode_changed.emit(str(value))
