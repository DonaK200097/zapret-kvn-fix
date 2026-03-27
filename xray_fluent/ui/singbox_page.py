from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    MessageBox,
    PlainTextEdit,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
)


class SingboxPage(QWidget):
    open_requested = pyqtSignal()
    save_requested = pyqtSignal(str)
    validate_requested = pyqtSignal(str)
    apply_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("singbox")

        self._current_path = ""
        self._saved_text = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        root.addWidget(SubtitleLabel("sing-box", self))

        self.file_label = CaptionLabel("Файл: --", self)
        self.file_label.setWordWrap(True)
        root.addWidget(self.file_label)

        self.hint_label = CaptionLabel(
            "Если в конфиге есть outbound tag `proxy`, он будет заменен на выбранный сервер перед запуском.",
            self,
        )
        self.hint_label.setWordWrap(True)
        root.addWidget(self.hint_label)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.open_btn = PushButton("Открыть", self)
        self.save_btn = PushButton("Сохранить", self)
        self.validate_btn = PushButton("Проверить JSON", self)
        self.apply_btn = PrimaryPushButton("Применить", self)

        toolbar.addWidget(self.open_btn)
        toolbar.addWidget(self.save_btn)
        toolbar.addWidget(self.validate_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(self.apply_btn)
        root.addLayout(toolbar)

        self.editor = PlainTextEdit(self)
        self.editor.setPlaceholderText("Raw sing-box.json")
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.editor.setFont(font)
        root.addWidget(self.editor, 1)

        root.addWidget(BodyLabel("Статус", self))
        self.status_box = PlainTextEdit(self)
        self.status_box.setReadOnly(True)
        self.status_box.setFixedHeight(92)
        self.status_box.setFont(font)
        root.addWidget(self.status_box)

        self.editor.textChanged.connect(self._on_text_changed)
        self.open_btn.clicked.connect(self._on_open_clicked)
        self.save_btn.clicked.connect(lambda: self.save_requested.emit(self.editor.toPlainText()))
        self.validate_btn.clicked.connect(lambda: self.validate_requested.emit(self.editor.toPlainText()))
        self.apply_btn.clicked.connect(lambda: self.apply_requested.emit(self.editor.toPlainText()))

        self._refresh_file_label()

    def set_document(self, path: Path, text: str) -> None:
        self._current_path = str(path)
        self.editor.blockSignals(True)
        self.editor.setPlainText(text)
        self.editor.blockSignals(False)
        self._saved_text = text
        self._refresh_file_label()

    def is_dirty(self) -> bool:
        return self.editor.toPlainText() != self._saved_text

    def set_status(self, level: str, message: str) -> None:
        prefix = {
            "success": "OK",
            "warning": "Внимание",
            "error": "Ошибка",
            "info": "Инфо",
        }.get(level.strip().lower(), "Статус")
        self.status_box.setPlainText(f"{prefix}: {message}".strip())

    def mark_saved(self, path: Path | None = None, text: str | None = None) -> None:
        if path is not None:
            self._current_path = str(path)
        if text is None:
            text = self.editor.toPlainText()
        self._saved_text = text
        self._refresh_file_label()

    def _on_open_clicked(self) -> None:
        if self.is_dirty():
            box = MessageBox("Несохранённые изменения", "Открыть другой файл без сохранения текущих правок?", self.window())
            box.yesButton.setText("Открыть")
            box.cancelButton.setText("Отмена")
            if not box.exec():
                return
        self.open_requested.emit()

    def _on_text_changed(self) -> None:
        self._refresh_file_label()

    def _refresh_file_label(self) -> None:
        if self._current_path:
            label = Path(self._current_path).as_posix()
        else:
            label = "--"
        suffix = " *" if self.is_dirty() else ""
        self.file_label.setText(f"Файл: {label}{suffix}")
