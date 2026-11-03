"""现代扁平主题：全局 QSS 设计系统（卡片 / 圆角 / 细描边 / 靛蓝主色）。"""

ACCENT = "#4f46e5"
ACCENT_HOVER = "#4338ca"
ACCENT_ACTIVE = "#3730a3"
ACCENT_SOFT = "#eef2ff"
ACCENT_SOFT_TEXT = "#312e81"

BG = "#f5f6f8"
SURFACE = "#ffffff"
BORDER = "#e7eaf0"
BORDER_STRONG = "#d8dde6"
TEXT = "#111827"
TEXT_2 = "#374151"
MUTED = "#6b7280"
FAINT = "#9ca3af"

QSS = f"""
* {{
    outline: none;
}}
QWidget {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", sans-serif;
    color: {TEXT};
}}
QMainWindow, QDialog {{ background: {BG}; }}

/* ---------- 顶部菜单 ---------- */
QMenuBar {{
    background: {BG};
    border: none;
    padding: 2px 6px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 5px 10px;
    border-radius: 7px;
    color: {TEXT_2};
}}
QMenuBar::item:selected {{ background: {ACCENT_SOFT}; color: {ACCENT_SOFT_TEXT}; }}
QMenu {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{ padding: 7px 26px 7px 14px; border-radius: 7px; color: {TEXT_2}; }}
QMenu::item:selected {{ background: {ACCENT_SOFT}; color: {ACCENT_SOFT_TEXT}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 5px 8px; }}

/* ---------- 输入控件 ---------- */
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {{
    background: {SURFACE};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 5px 10px;
    color: {TEXT_2};
    selection-background-color: #c7d2fe;
}}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit:disabled, QDoubleSpinBox:disabled, QSpinBox:disabled, QComboBox:disabled {{
    background: #f3f4f6; color: {FAINT}; border-color: {BORDER};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    border: none; background: transparent; width: 16px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: #eef0f4; border-radius: 4px;
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {ACCENT_SOFT_TEXT};
    padding: 4px;
    outline: none;
}}

/* ---------- 按钮 ---------- */
QPushButton {{
    background: {SURFACE};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 6px 16px;
    color: {TEXT_2};
}}
QPushButton:hover {{ background: #f2f4f7; border-color: #c9d0da; }}
QPushButton:pressed {{ background: #e9ecf2; }}
QPushButton:disabled {{ color: {FAINT}; background: #f7f8fa; border-color: {BORDER}; }}

QPushButton#primary {{
    background: {ACCENT}; border: 1px solid {ACCENT}; color: #ffffff; font-weight: 600;
}}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton#primary:pressed {{ background: {ACCENT_ACTIVE}; }}
QPushButton#primary:disabled {{ background: #c7c9f4; border-color: #c7c9f4; color: #f4f5ff; }}

QPushButton#chip {{
    background: {ACCENT_SOFT}; border: none; border-radius: 8px;
    color: {ACCENT_SOFT_TEXT}; padding: 5px 10px; font-size: 8.5pt;
}}
QPushButton#chip:hover {{ background: #e0e7ff; }}

/* ---------- 卡片容器 ---------- */
QGroupBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    margin-top: 26px;
    padding: 8px 12px 12px 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 4px; top: 8px;
    color: {TEXT};
    font-weight: 600;
}}

/* ---------- 文本层级 ---------- */
QLabel#pageTitle {{
    font-size: 17pt; font-weight: 600; color: {TEXT}; letter-spacing: 0.3px;
}}
QLabel#pageCaption {{ color: {MUTED}; font-size: 9.5pt; }}
QLabel#sectionTitle {{ font-size: 11pt; font-weight: 600; color: {TEXT}; }}
QLabel#tipLabel {{ color: {MUTED}; font-size: 9pt; }}

/* ---------- 表格 ---------- */
QTableWidget {{
    background: {SURFACE};
    alternate-background-color: #fafbfd;
    border: 1px solid {BORDER};
    border-radius: 10px;
    gridline-color: #f0f2f6;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {TEXT};
    padding: 2px;
}}
QTableWidget::item {{ padding: 4px 8px; }}
QHeaderView::section {{
    background: transparent;
    color: {MUTED};
    font-weight: 600;
    font-size: 9pt;
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 7px 8px;
}}
QTableCornerButton::section {{ background: transparent; border: none; }}

/* ---------- 文本域 ---------- */
QTextEdit, QPlainTextEdit {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 4px;
    color: {TEXT_2};
    selection-background-color: #c7d2fe;
}}
QTextEdit:readOnly, QPlainTextEdit:readOnly {{ background: {SURFACE}; }}

/* ---------- 滚动条 ---------- */
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #d3d8e0; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #b8bfcc; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #d3d8e0; border-radius: 4px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: #b8bfcc; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---------- 分割线 / Splitter ---------- */
QFrame[frameShape="4"] {{ border: none; color: {BORDER}; }}
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:vertical {{ height: 8px; }}
QSplitter::handle:horizontal {{ width: 8px; }}

/* ---------- Tab ---------- */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    background: {SURFACE};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    padding: 7px 16px;
    margin-right: 4px;
    border-radius: 8px;
}}
QTabBar::tab:selected {{ background: {ACCENT_SOFT}; color: {ACCENT_SOFT_TEXT}; font-weight: 600; }}
QTabBar::tab:hover {{ color: {ACCENT_SOFT_TEXT}; }}

/* ---------- Dock ---------- */
QDockWidget {{
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
    color: {TEXT};
}}
QDockWidget::title {{
    background: transparent;
    padding: 10px 4px 6px 6px;
    font-weight: 600;
}}

/* ---------- 提示气泡 ---------- */
QToolTip {{
    background: #1f2937; color: #f9fafb;
    border: none; padding: 6px 10px; border-radius: 6px; font-size: 9pt;
}}

/* ---------- 可折叠卡片 ---------- */
QWidget#foldCard {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QPushButton#foldHeader {{
    background: transparent;
    border: none;
    border-radius: 11px;
    padding: 9px 14px;
    text-align: left;
    font-weight: 600;
    color: {TEXT_2};
}}
QPushButton#foldHeader:hover {{ background: #f8fafc; }}
QWidget#foldBody {{ background: transparent; border-radius: 12px; }}

/* ---------- 底部步骤导航 ---------- */
QWidget#footerBar {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

/* ---------- 状态栏 ---------- */
QStatusBar {{ background: transparent; color: {MUTED}; border-top: 1px solid {BORDER}; }}

/* ---------- 导航栏 ---------- */
QWidget#navRail {{ background: #fbfcfe; border-right: 1px solid {BORDER}; }}
QLabel#navHeader {{ font-size: 13pt; font-weight: 700; color: {TEXT}; }}
QLabel#navHeaderSub {{ color: {MUTED}; font-size: 8.5pt; }}
QFrame#navItem {{ background: transparent; border-radius: 10px; }}
QFrame#navItem:hover {{ background: #f1f3f7; }}
NavItem[selected="true"] {{ background: {ACCENT_SOFT}; }}
QLabel#navBadge {{
    background: #e8eaf1; color: #4b5563;
    border-radius: 13px; font-weight: 700; font-size: 10pt;
}}
NavItem[selected="true"] QLabel#navBadge {{ background: {ACCENT}; color: #ffffff; }}
QLabel#navTitle {{ color: {TEXT_2}; font-weight: 600; }}
NavItem[selected="true"] QLabel#navTitle {{ color: {ACCENT_SOFT_TEXT}; }}
QLabel#navCaption {{ color: {FAINT}; font-size: 8pt; }}
NavItem[selected="true"] QLabel#navCaption {{ color: #6366f1; }}
QLabel#navFooter {{ color: {FAINT}; font-size: 8pt; }}
"""


def apply_theme(app):
    app.setStyleSheet(QSS)


def repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
