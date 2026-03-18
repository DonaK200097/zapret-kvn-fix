from __future__ import annotations

from datetime import datetime
from typing import cast

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QKeyEvent, QKeySequence, QShortcut
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QAbstractItemView, QApplication, QHBoxLayout, QHeaderView, QTableWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    PrimaryPushButton,
    PushButton,
    SearchLineEdit,
    SubtitleLabel,
    TableWidget,
)
from qfluentwidgets import RoundMenu, Action

from ..country_flags import get_flag_icon
from ..models import Node

_SORT_KEYS = ["Name", "Group", "Protocol", "Ping", "Last used"]


class NodesPage(QWidget):
    import_clipboard_requested = pyqtSignal()
    delete_requested = pyqtSignal(object)          # emits set[str] of node IDs
    ping_requested = pyqtSignal(object)             # emits set[str] or empty set
    export_outbound_json_requested = pyqtSignal(str)
    export_runtime_json_requested = pyqtSignal(str)
    selected_node_changed = pyqtSignal(str)
    edit_node_requested = pyqtSignal(str)           # node_id
    bulk_edit_requested = pyqtSignal(object)        # set[str] of node_ids
    copy_link_requested = pyqtSignal(str)           # node_id

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("nodes")

        self._nodes: list[Node] = []
        self._visible_node_ids: list[str] = []
        self._sort_ascending = True

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = SubtitleLabel("Nodes", self)
        root.addWidget(title)

        # --- Filter row ---
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self.search_edit = SearchLineEdit(self)
        self.search_edit.setPlaceholderText("Search nodes")
        filter_row.addWidget(self.search_edit, 1)

        filter_row.addWidget(BodyLabel("Group:", self))
        self.group_filter = ComboBox(self)
        self.group_filter.setMinimumWidth(120)
        self.group_filter.addItem("All Groups")
        filter_row.addWidget(self.group_filter)

        filter_row.addWidget(BodyLabel("Tag:", self))
        self.tag_filter = ComboBox(self)
        self.tag_filter.setMinimumWidth(120)
        self.tag_filter.addItem("All Tags")
        filter_row.addWidget(self.tag_filter)

        filter_row.addWidget(BodyLabel("Sort:", self))
        self.sort_combo = ComboBox(self)
        self.sort_combo.setMinimumWidth(110)
        for key in _SORT_KEYS:
            self.sort_combo.addItem(key)
        filter_row.addWidget(self.sort_combo)

        self.sort_order_btn = PushButton("Asc", self)
        self.sort_order_btn.setFixedWidth(50)
        filter_row.addWidget(self.sort_order_btn)

        root.addLayout(filter_row)

        # --- Action toolbar ---
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.import_btn = PrimaryPushButton("Import from clipboard", self)
        self.edit_btn = PushButton("Edit", self)
        self.bulk_edit_btn = PushButton("Bulk edit", self)
        self.ping_btn = PushButton("Ping selected", self)
        self.ping_all_btn = PushButton("Ping all", self)
        self.export_outbound_btn = PushButton("Export outbound JSON", self)
        self.export_runtime_btn = PushButton("Export runtime config", self)
        self.delete_btn = PushButton("Delete selected", self)

        toolbar.addWidget(self.import_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.bulk_edit_btn)
        toolbar.addWidget(self.ping_btn)
        toolbar.addWidget(self.ping_all_btn)
        toolbar.addWidget(self.export_outbound_btn)
        toolbar.addWidget(self.export_runtime_btn)
        toolbar.addWidget(self.delete_btn)

        root.addLayout(toolbar)

        # --- Table ---
        self.table = TableWidget(self)
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Type", "Server", "Port", "Group", "Tags", "Ping", "Last used"]
        )
        vertical_header = cast(QHeaderView, self.table.verticalHeader())
        vertical_header.setVisible(False)

        horizontal_header = cast(QHeaderView, self.table.horizontalHeader())
        horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        horizontal_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        horizontal_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        horizontal_header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.setIconSize(QSize(20, 14))

        root.addWidget(self.table, 1)

        # --- Connections ---
        self.search_edit.textChanged.connect(self._reload)
        self.group_filter.currentIndexChanged.connect(self._reload)
        self.tag_filter.currentIndexChanged.connect(self._reload)
        self.sort_combo.currentIndexChanged.connect(self._reload)
        self.sort_order_btn.clicked.connect(self._toggle_sort_order)
        self.import_btn.clicked.connect(self.import_clipboard_requested)
        self.edit_btn.clicked.connect(self._on_edit)
        self.bulk_edit_btn.clicked.connect(self._on_bulk_edit)
        self.ping_btn.clicked.connect(self._on_ping_selected)
        self.ping_all_btn.clicked.connect(self._on_ping_all)
        self.export_outbound_btn.clicked.connect(self._on_export_outbound)
        self.export_runtime_btn.clicked.connect(self._on_export_runtime)
        self.delete_btn.clicked.connect(self._on_delete_selected)
        self.table.itemSelectionChanged.connect(self._emit_selection)
        self.table.doubleClicked.connect(self._on_double_click)
        self.table.customContextMenuRequested.connect(self._on_context_menu)

        # --- Keyboard shortcuts ---
        paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self)
        paste_shortcut.activated.connect(self.import_clipboard_requested)

    # ── Public API ──

    def set_nodes(self, nodes: list[Node], selected_id: str | None = None) -> None:
        self._nodes = list(nodes)
        self._rebuild_filter_combos()
        self._reload()
        if selected_id:
            self._select_node(selected_id)

    def update_ping(self, node_id: str, ping_ms: int | None) -> None:
        for row, visible_id in enumerate(self._visible_node_ids):
            if visible_id != node_id:
                continue
            text = "--" if ping_ms is None else f"{ping_ms} ms"
            self.table.setItem(row, 6, QTableWidgetItem(text))
            break

    # ── Filter combos ──

    def _rebuild_filter_combos(self) -> None:
        prev_group = self.group_filter.currentText()
        prev_tag = self.tag_filter.currentText()

        self.group_filter.blockSignals(True)
        self.group_filter.clear()
        self.group_filter.addItem("All Groups")
        groups = sorted({n.group for n in self._nodes if n.group})
        for g in groups:
            self.group_filter.addItem(g)
        idx = self.group_filter.findText(prev_group)
        self.group_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.group_filter.blockSignals(False)

        self.tag_filter.blockSignals(True)
        self.tag_filter.clear()
        self.tag_filter.addItem("All Tags")
        tags: set[str] = set()
        for n in self._nodes:
            tags.update(n.tags)
        for t in sorted(tags):
            self.tag_filter.addItem(t)
        idx = self.tag_filter.findText(prev_tag)
        self.tag_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.tag_filter.blockSignals(False)

    # ── Reload / filter / sort ──

    def _reload(self) -> None:
        query = self.search_edit.text().strip().lower()
        group_filter = self.group_filter.currentText()
        tag_filter = self.tag_filter.currentText()

        filtered = []
        for node in self._nodes:
            if group_filter != "All Groups" and node.group != group_filter:
                continue
            if tag_filter != "All Tags" and tag_filter not in node.tags:
                continue
            if query:
                haystack = " ".join(
                    [node.name, node.scheme, node.server, node.group, " ".join(node.tags)]
                ).lower()
                if query not in haystack:
                    continue
            filtered.append(node)

        sort_key = self.sort_combo.currentText()
        filtered = self._sort_nodes(filtered, sort_key, self._sort_ascending)

        self.table.blockSignals(True)
        self.table.setRowCount(len(filtered))
        self._visible_node_ids = []

        for row, node in enumerate(filtered):
            self._visible_node_ids.append(node.id)
            name_item = QTableWidgetItem(node.name or "Unnamed")
            icon = get_flag_icon(node.country_code)
            if icon:
                name_item.setIcon(icon)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(node.scheme.upper()))
            self.table.setItem(row, 2, QTableWidgetItem(node.server))
            self.table.setItem(row, 3, QTableWidgetItem(str(node.port)))
            self.table.setItem(row, 4, QTableWidgetItem(node.group))
            self.table.setItem(row, 5, QTableWidgetItem(", ".join(node.tags)))
            self.table.setItem(row, 6, QTableWidgetItem("--" if node.ping_ms is None else f"{node.ping_ms} ms"))
            self.table.setItem(row, 7, QTableWidgetItem(self._format_time(node.last_used_at)))
        self.table.blockSignals(False)

    @staticmethod
    def _sort_nodes(nodes: list[Node], key: str, ascending: bool) -> list[Node]:
        if key == "Name":
            return sorted(nodes, key=lambda n: n.name.lower(), reverse=not ascending)
        if key == "Group":
            return sorted(nodes, key=lambda n: n.group.lower(), reverse=not ascending)
        if key == "Protocol":
            return sorted(nodes, key=lambda n: n.scheme.lower(), reverse=not ascending)
        if key == "Ping":
            none_val = float("inf") if ascending else float("-inf")
            return sorted(
                nodes,
                key=lambda n: n.ping_ms if n.ping_ms is not None else none_val,
                reverse=not ascending,
            )
        if key == "Last used":
            return sorted(nodes, key=lambda n: n.last_used_at or "", reverse=not ascending)
        return nodes

    def _toggle_sort_order(self) -> None:
        self._sort_ascending = not self._sort_ascending
        self.sort_order_btn.setText("Asc" if self._sort_ascending else "Desc")
        self._reload()

    # ── Selection helpers ──

    def _selected_ids(self) -> set[str]:
        rows = {item.row() for item in self.table.selectedItems()}
        ids: set[str] = set()
        for row in rows:
            if 0 <= row < len(self._visible_node_ids):
                ids.add(self._visible_node_ids[row])
        return ids

    def _select_node(self, node_id: str) -> None:
        for row, value in enumerate(self._visible_node_ids):
            if value == node_id:
                self.table.selectRow(row)
                break

    def _emit_selection(self) -> None:
        ids = self._selected_ids()
        if len(ids) == 1:
            self.selected_node_changed.emit(next(iter(ids)))

    # ── Button handlers ──

    def _on_edit(self) -> None:
        ids = self._selected_ids()
        if len(ids) == 1:
            self.edit_node_requested.emit(next(iter(ids)))

    def _on_bulk_edit(self) -> None:
        ids = self._selected_ids()
        if ids:
            self.bulk_edit_requested.emit(ids)

    def _on_ping_selected(self) -> None:
        ids = self._selected_ids()
        if ids:
            self.ping_requested.emit(ids)

    def _on_ping_all(self) -> None:
        self.ping_requested.emit(set())

    def _on_delete_selected(self) -> None:
        ids = self._selected_ids()
        if ids:
            self.delete_requested.emit(ids)

    def _on_export_outbound(self) -> None:
        ids = self._selected_ids()
        if len(ids) != 1:
            return
        self.export_outbound_json_requested.emit(next(iter(ids)))

    def _on_export_runtime(self) -> None:
        ids = self._selected_ids()
        if len(ids) != 1:
            return
        self.export_runtime_json_requested.emit(next(iter(ids)))

    # ── Double-click / context menu ──

    def _on_double_click(self, index) -> None:
        row = index.row()
        if 0 <= row < len(self._visible_node_ids):
            self.edit_node_requested.emit(self._visible_node_ids[row])

    def _on_context_menu(self, pos) -> None:
        item = self.table.itemAt(pos)
        if item is None:
            return
        clicked_row = item.row()
        if clicked_row < 0 or clicked_row >= len(self._visible_node_ids):
            return

        clicked_id = self._visible_node_ids[clicked_row]
        current_ids = self._selected_ids()
        if clicked_id not in current_ids:
            self.table.clearSelection()
            self.table.selectRow(clicked_row)
            ids = {clicked_id}
        else:
            ids = current_ids

        menu = RoundMenu(parent=self)
        count = len(ids)

        if count == 1:
            node_id = next(iter(ids))
            edit_action = Action("Edit", self)
            edit_action.triggered.connect(lambda: self.edit_node_requested.emit(node_id))
            menu.addAction(edit_action)

            copy_action = Action("Copy link", self)
            copy_action.triggered.connect(lambda: self._copy_node_link(node_id))
            menu.addAction(copy_action)
        else:
            copy_action = Action(f"Copy {count} links", self)
            copy_action.triggered.connect(lambda: self._copy_multiple_links(ids))
            menu.addAction(copy_action)

        bulk_action = Action("Bulk edit", self)
        bulk_action.triggered.connect(lambda: self.bulk_edit_requested.emit(ids))
        menu.addAction(bulk_action)

        menu.addSeparator()

        ping_action = Action(f"Ping ({count})" if count > 1 else "Ping", self)
        ping_action.triggered.connect(lambda: self.ping_requested.emit(ids))
        menu.addAction(ping_action)

        menu.addSeparator()

        delete_label = f"Delete {count} nodes" if count > 1 else "Delete"
        delete_action = Action(delete_label, self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(ids))
        menu.addAction(delete_action)

        menu.exec(QCursor.pos())

    # ── Utilities ──

    def _copy_node_link(self, node_id: str) -> None:
        for node in self._nodes:
            if node.id == node_id and node.link:
                clipboard = QApplication.clipboard()
                if clipboard is not None:
                    clipboard.setText(node.link)
                break

    def _copy_multiple_links(self, node_ids: set[str]) -> None:
        links: list[str] = []
        for vid in self._visible_node_ids:
            if vid in node_ids:
                for node in self._nodes:
                    if node.id == vid and node.link:
                        links.append(node.link)
                        break
        if links:
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText("\n".join(links))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            self._on_delete_selected()
            return
        if event.matches(QKeySequence.StandardKey.Copy):
            ids = self._selected_ids()
            if ids:
                if len(ids) == 1:
                    self._copy_node_link(next(iter(ids)))
                else:
                    self._copy_multiple_links(ids)
            return
        super().keyPressEvent(event)

    @staticmethod
    def _format_time(value: str | None) -> str:
        if not value:
            return ""
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return value
