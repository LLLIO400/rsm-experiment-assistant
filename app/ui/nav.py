"""现代风格步骤导航栏：编号徽章 + 标题 + 副标题，选中态为靛蓝卡片。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .theme import repolish


class NavItem(QFrame):
    clicked = Signal(int)

    def __init__(self, index: int, title: str, caption: str):
        super().__init__()
        self.index = index
        self.setObjectName("navItem")
        self.setCursor(Qt.PointingHandCursor)

        h = QHBoxLayout(self)
        h.setContentsMargins(10, 8, 10, 8)
        h.setSpacing(11)
        self.badge = QLabel(str(index + 1))
        self.badge.setObjectName("navBadge")
        self.badge.setFixedSize(26, 26)
        self.badge.setAlignment(Qt.AlignCenter)
        v = QVBoxLayout()
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(1)
        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("navTitle")
        self.cap_lbl = QLabel(caption)
        self.cap_lbl.setObjectName("navCaption")
        v.addWidget(self.title_lbl)
        v.addWidget(self.cap_lbl)
        h.addWidget(self.badge)
        h.addLayout(v, 1)
        self.setSelected(False)

    def mousePressEvent(self, ev):  # noqa: N802
        self.clicked.emit(self.index)

    def setSelected(self, selected: bool):
        self.setProperty("selected", bool(selected))
        repolish(self)


class NavRail(QWidget):
    currentRowChanged = Signal(int)

    def __init__(self, steps: list):
        super().__init__()
        self.setObjectName("navRail")
        self.setFixedWidth(236)
        self._current = -1
        self._items = []

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 16, 12, 12)
        v.setSpacing(4)

        header = QHBoxLayout()
        dot = QLabel("●")
        dot.setStyleSheet(f"color:#4f46e5;font-size:15pt;background:transparent;")
        name = QVBoxLayout()
        name.setSpacing(0)
        t = QLabel("RSM 实验助手")
        t.setObjectName("navHeader")
        s = QLabel("响应面优化 · Box-Behnken")
        s.setObjectName("navHeaderSub")
        name.addWidget(t)
        name.addWidget(s)
        header.addWidget(dot)
        header.addLayout(name, 1)
        v.addLayout(header)
        v.addSpacing(14)

        for i, (title, caption) in enumerate(steps):
            item = NavItem(i, title, caption)
            item.clicked.connect(self.setCurrentRow)
            v.addWidget(item)
            self._items.append(item)
        v.addStretch(1)

        footer = QLabel("统计由 statsmodels / scipy\n本地计算 · AI 仅负责解释")
        footer.setObjectName("navFooter")
        footer.setAlignment(Qt.AlignLeft)
        v.addWidget(footer)

    def setCurrentRow(self, idx: int):
        if idx == self._current:
            return
        self._current = idx
        for i, item in enumerate(self._items):
            item.setSelected(i == idx)
        self.currentRowChanged.emit(idx)

    def currentRow(self) -> int:
        return self._current
