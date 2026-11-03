# -*- coding: utf-8 -*-
"""我的 RSM 实验助手 —— 启动入口。

用法：python main.py
"""
import os
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

# QtWebEngine 需要在 QApplication 创建前共享 OpenGL 上下文

from PySide6.QtCore import Qt, QTimer   # noqa: E402
from PySide6.QtGui import QFont        # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui.theme import apply_theme   # noqa: E402


def main() -> int:
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    QApplication.setStyle("Fusion")
    app = QApplication(sys.argv)
    app.setApplicationName("我的 RSM 实验助手")
    app.setFont(QFont("Microsoft YaHei UI", 9.5))
    apply_theme(app)

    from app.ui.main_window import MainWindow
    win = MainWindow()
    if "--demo" in sys.argv[1:]:
        from app.core.demo import make_paper_demo
        key = sys.argv[sys.argv.index("--demo") + 1] if             len(sys.argv) > sys.argv.index("--demo") + 1 else "yield"
        from app.core.demo import DEMOS
        win.exp = make_paper_demo(key if key in DEMOS else "yield")
        win.exp.save()
        win.model = None
        win.optimum = None
        win.optimum_constrained = None
        win.page_new.refresh()
        win.page_design.refresh()
        win.ai_panel.refresh_stage(win.current_stage())
    win.setWindowState(Qt.WindowMaximized)   # 先设状态再 show（顺序最稳）
    win.show()
    win.raise_()
    win.activateWindow()  # 压到 bat 控制台前面，避免被黑窗口挡住
    # 双保险：事件循环起来后再确认一次最大化，防止被系统/时序顶回普通状态
    QTimer.singleShot(300, lambda: win.setWindowState(Qt.WindowMaximized))
    QTimer.singleShot(1200, lambda: win.setWindowState(Qt.WindowMaximized))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
