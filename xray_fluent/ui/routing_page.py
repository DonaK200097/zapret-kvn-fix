from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, ComboBox, PlainTextEdit, PrimaryPushButton, SubtitleLabel, SwitchButton

from ..models import RoutingSettings


class RoutingPage(QWidget):
    apply_requested = pyqtSignal(str, object, object, object, bool, str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("routing")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        root.addWidget(SubtitleLabel("Routing", self))

        header = QGridLayout()
        header.setHorizontalSpacing(12)
        header.setVerticalSpacing(8)

        header.addWidget(BodyLabel("Mode", self), 0, 0)
        self.mode_combo = ComboBox(self)
        self.mode_combo.addItem("Global", userData="global")
        self.mode_combo.addItem("Rule", userData="rule")
        self.mode_combo.addItem("Direct", userData="direct")
        header.addWidget(self.mode_combo, 0, 1)

        header.addWidget(BodyLabel("DNS", self), 1, 0)
        self.dns_combo = ComboBox(self)
        self.dns_combo.addItem("System DNS", userData="system")
        self.dns_combo.addItem("Built-in DNS", userData="builtin")
        header.addWidget(self.dns_combo, 1, 1)

        self.bypass_switch = SwitchButton("Bypass LAN", self)
        header.addWidget(self.bypass_switch, 2, 0, 1, 2)

        root.addLayout(header)

        root.addWidget(BodyLabel("Direct list (one item per line)", self))
        self.direct_edit = PlainTextEdit(self)
        self.direct_edit.setPlaceholderText("example.com\ngeoip:private")
        self.direct_edit.setFixedHeight(110)
        root.addWidget(self.direct_edit)

        root.addWidget(BodyLabel("Proxy list (one item per line)", self))
        self.proxy_edit = PlainTextEdit(self)
        self.proxy_edit.setPlaceholderText("youtube.com\nopenai.com")
        self.proxy_edit.setFixedHeight(110)
        root.addWidget(self.proxy_edit)

        root.addWidget(BodyLabel("Block list (one item per line)", self))
        self.block_edit = PlainTextEdit(self)
        self.block_edit.setPlaceholderText("ads.example.com")
        self.block_edit.setFixedHeight(110)
        root.addWidget(self.block_edit)

        row = QHBoxLayout()
        row.addStretch(1)
        self.apply_btn = PrimaryPushButton("Apply routing", self)
        row.addWidget(self.apply_btn)
        root.addLayout(row)
        root.addStretch(1)

        self.apply_btn.clicked.connect(self._emit_apply)

    def set_routing(self, routing: RoutingSettings) -> None:
        self._select_combo_value(self.mode_combo, routing.mode)
        self._select_combo_value(self.dns_combo, routing.dns_mode)
        self.bypass_switch.setChecked(routing.bypass_lan)
        self.direct_edit.setPlainText("\n".join(routing.direct_domains))
        self.proxy_edit.setPlainText("\n".join(routing.proxy_domains))
        self.block_edit.setPlainText("\n".join(routing.block_domains))

    def _emit_apply(self) -> None:
        mode = self.mode_combo.currentData() or "rule"
        dns_mode = self.dns_combo.currentData() or "system"
        self.apply_requested.emit(
            str(mode),
            self._split_lines(self.direct_edit.toPlainText()),
            self._split_lines(self.proxy_edit.toPlainText()),
            self._split_lines(self.block_edit.toPlainText()),
            self.bypass_switch.isChecked(),
            str(dns_mode),
        )

    @staticmethod
    def _split_lines(text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    @staticmethod
    def _select_combo_value(combo: ComboBox, value: str) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
