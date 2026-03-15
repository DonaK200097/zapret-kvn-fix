from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout
from qfluentwidgets import BodyLabel, EditableComboBox, LineEdit, PrimaryPushButton, PushButton, SubtitleLabel

from ..models import Node


class NodeEditDialog(QDialog):
    def __init__(self, node: Node, existing_groups: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Node")
        self.setModal(True)
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(10)

        root.addWidget(SubtitleLabel("Edit Node", self))

        root.addWidget(BodyLabel(f"Protocol: {node.scheme.upper()}", self))
        root.addWidget(BodyLabel(f"Server: {node.server}:{node.port}", self))

        root.addWidget(BodyLabel("Name", self))
        self.name_edit = LineEdit(self)
        self.name_edit.setText(node.name)
        self.name_edit.setPlaceholderText("Node name")
        root.addWidget(self.name_edit)

        root.addWidget(BodyLabel("Group", self))
        self.group_combo = EditableComboBox(self)
        for g in existing_groups:
            self.group_combo.addItem(g)
        self.group_combo.setText(node.group)
        root.addWidget(self.group_combo)

        root.addWidget(BodyLabel("Tags (comma-separated)", self))
        self.tags_edit = LineEdit(self)
        self.tags_edit.setText(", ".join(node.tags))
        self.tags_edit.setPlaceholderText("tag1, tag2, tag3")
        root.addWidget(self.tags_edit)

        row = QHBoxLayout()
        row.addStretch(1)
        self.cancel_btn = PushButton("Cancel", self)
        self.save_btn = PrimaryPushButton("Save", self)
        row.addWidget(self.cancel_btn)
        row.addWidget(self.save_btn)
        root.addLayout(row)

        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self.accept)
        self.name_edit.returnPressed.connect(self.accept)

    def get_updated_fields(self) -> dict:
        raw_tags = self.tags_edit.text().strip()
        tags = [t.strip() for t in raw_tags.split(",") if t.strip()] if raw_tags else []
        return {
            "name": self.name_edit.text().strip(),
            "group": self.group_combo.text().strip() or "Default",
            "tags": tags,
        }
