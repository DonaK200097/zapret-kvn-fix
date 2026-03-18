"""Zapret (DPI bypass) management page — preset selection + start/stop."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    ComboBox,
    IndeterminateProgressBar,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
)


class ZapretPage(QWidget):
    start_requested = pyqtSignal(str)   # preset name
    stop_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("zapret")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        root.addWidget(SubtitleLabel("Обход блокировок (zapret)", self))

        # ── Info card ────────────────────────────────
        info_card = CardWidget(self)
        info_lay = QVBoxLayout(info_card)
        info_lay.setContentsMargins(16, 12, 16, 12)
        info_lay.setSpacing(4)
        info_lay.addWidget(BodyLabel(
            "Zapret (winws2) — инструмент обхода DPI-блокировок.\n"
            "Выберите пресет и нажмите «Запустить». Работает независимо от VPN/прокси.",
            self,
        ))
        info_lay.addWidget(CaptionLabel(
            "Требуются права администратора. Файлы zapret должны находиться в папке zapret/ рядом с приложением.",
            self,
        ))
        root.addWidget(info_card)

        # ── Preset selector ──────────────────────────
        preset_row = QHBoxLayout()
        preset_row.setSpacing(12)
        preset_row.addWidget(BodyLabel("Пресет:", self))
        self.preset_combo = ComboBox(self)
        self.preset_combo.setMinimumWidth(350)
        preset_row.addWidget(self.preset_combo, 1)
        self.refresh_btn = PushButton("Обновить", self)
        preset_row.addWidget(self.refresh_btn)
        root.addLayout(preset_row)

        # ── Status ───────────────────────────────────
        status_card = CardWidget(self)
        status_lay = QHBoxLayout(status_card)
        status_lay.setContentsMargins(16, 12, 16, 12)
        status_lay.setSpacing(12)

        self.status_label = BodyLabel("Остановлен", self)
        status_lay.addWidget(self.status_label, 1)

        self.progress = IndeterminateProgressBar(self)
        self.progress.setFixedHeight(3)
        self.progress.hide()
        status_lay.addWidget(self.progress)

        root.addWidget(status_card)

        # ── Buttons ──────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.start_btn = PrimaryPushButton("Запустить", self)
        self.start_btn.setMinimumWidth(160)
        btn_row.addWidget(self.start_btn)
        self.stop_btn = PushButton("Остановить", self)
        self.stop_btn.setMinimumWidth(160)
        self.stop_btn.setEnabled(False)
        btn_row.addWidget(self.stop_btn)
        root.addLayout(btn_row)

        root.addStretch(1)

        # ── Signals ──────────────────────────────────
        self.start_btn.clicked.connect(self._on_start)
        self.stop_btn.clicked.connect(self._on_stop)
        self.refresh_btn.clicked.connect(lambda: self.start_requested.emit("__refresh__"))

    # ── Public API ───────────────────────────────────

    def set_presets(self, names: list[str], selected: str = "") -> None:
        self.preset_combo.clear()
        for name in names:
            self.preset_combo.addItem(name)
        if selected and selected in names:
            self.preset_combo.setCurrentText(selected)
        elif names:
            self.preset_combo.setCurrentIndex(0)

    def set_running(self, running: bool) -> None:
        if running:
            self.status_label.setText("Работает")
            self.status_label.setStyleSheet("color: #4CAF50;")
            self.progress.show()
            self.progress.start()
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.preset_combo.setEnabled(False)
        else:
            self.status_label.setText("Остановлен")
            self.status_label.setStyleSheet("")
            self.progress.stop()
            self.progress.hide()
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.preset_combo.setEnabled(True)

    def set_error(self, message: str) -> None:
        self.status_label.setText(f"Ошибка: {message}")
        self.status_label.setStyleSheet("color: #F44336;")
        self.set_running(False)
        self.status_label.setStyleSheet("color: #F44336;")

    def current_preset(self) -> str:
        return self.preset_combo.currentText()

    # ── Private ──────────────────────────────────────

    def _on_start(self) -> None:
        name = self.preset_combo.currentText()
        if name:
            self.start_requested.emit(name)

    def _on_stop(self) -> None:
        self.stop_requested.emit()
