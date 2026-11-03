"""界面层共享小工具。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

ACCENT = "#2563eb"
WARN_BG = "#fef3c7"
BAD_BG = "#fee2e2"
OK_BG = "#dcfce7"


def hline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFrameShadow(QFrame.Sunken)
    return f


def section_title(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName("sectionTitle")
    return lab


class FoldCard(QWidget):
    """可折叠卡片：点标题行收起/展开正文，收起后只留一行标题。"""

    def __init__(self, title: str, collapsed: bool = False):
        super().__init__()
        self.setObjectName("foldCard")
        self._title = title
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.btn = QPushButton()
        self.btn.setObjectName("foldHeader")
        self.btn.setCheckable(True)
        self.btn.setChecked(collapsed)
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.toggled.connect(self._apply)
        v.addWidget(self.btn)
        self.body = QWidget()
        self.body.setObjectName("foldBody")
        self.body_l = QVBoxLayout(self.body)
        self.body_l.setContentsMargins(12, 6, 12, 10)
        self.body_l.setSpacing(8)
        v.addWidget(self.body)
        self._apply(collapsed)

    def set_body(self, layout):
        self.body_l.addLayout(layout)

    def add_widget(self, w: QWidget, stretch: int = 0):
        self.body_l.addWidget(w, stretch)

    def add_layout(self, layout, stretch: int = 0):
        self.body_l.addLayout(layout, stretch)

    def set_collapsed(self, collapsed: bool):
        self.btn.setChecked(collapsed)

    def _apply(self, collapsed: bool):
        arrow = "▸" if collapsed else "▾"
        self.btn.setText(f"{arrow}  {self._title}")
        self.body.setVisible(not collapsed)


def page_header(title: str, caption: str = "") -> QWidget:
    """页面顶部标题区：大标题 + 灰色说明。"""
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("pageTitle")
    v.addWidget(t)
    if caption:
        c = QLabel(caption)
        c.setObjectName("pageCaption")
        c.setWordWrap(True)
        v.addWidget(c)
    return w


def tip_label(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setObjectName("tipLabel")
    return lab


def status_chip(text: str, ok: bool | None = True) -> QLabel:
    lab = QLabel(text)
    color = {True: "#15803d", False: "#b91c1c", None: "#b45309"}[ok]
    bg = {True: "#ecfdf5", False: "#fef2f2", None: "#fffbeb"}[ok]
    lab.setStyleSheet(f"color:{color};background:{bg};"
                      f"border-radius:12px;padding:4px 13px;font-weight:600;")
    return lab


def read_float(text: str) -> float | None:
    try:
        return float(str(text).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None


def fmt(x: float | None, nd: int = 4) -> str:
    if x is None:
        return ""
    return f"{x:.{nd}g}"


def make_table(headers: list, rows: int = 0) -> QTableWidget:
    t = QTableWidget(rows, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setStretchLastSection(True)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(30)
    t.setShowGrid(False)
    return t


def fill_row(table: QTableWidget, row: int, values: list, editable_cols: set | None = None):
    editable_cols = editable_cols or set()
    for col, v in enumerate(values):
        item = QTableWidgetItem("" if v is None else str(v))
        if col not in editable_cols:
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setForeground(Qt.gray)
        table.setItem(row, col, item)


def row_of(widget_layout: list) -> QHBoxLayout:
    box = QHBoxLayout()
    box.setSpacing(8)
    for w in widget_layout:
        box.addWidget(w)
    box.addStretch(1)
    return box
