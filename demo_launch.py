# -*- coding: utf-8 -*-
"""带示例数据启动软件（不占用软件界面，双击「打开示例实验.bat」即可）。

用法：
    python demo_launch.py            # 默认载入产率示例（Sci Rep 2022，模型质量好）
    python demo_launch.py tpc        # 载入总多酚示例（同论文，检测噪声大，
                                     #   专门用来看"弱模型警告"长什么样）
    python demo_launch.py ee         # 载入 PLGA 包封率示例（BioMed Research International 2014，4因素）
    python demo_launch.py size       # 载入 PLGA 粒径示例（4因素，最小化）

示例为公开文献的真实实验数据：因素、BBD 设计、全部实测结果都已填好，
启动后直接点「下一步」就能走 拟合模型 → 响应面 → 寻优 → 验证 全流程。
"""
import os
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

from app.core.demo import DEMOS, make_paper_demo


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "yield"
    if which not in DEMOS:
        print(f"未知示例 {which!r}，可选：{', '.join(DEMOS)}")
        return 1

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from app.ui.theme import apply_theme

    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    QApplication.setStyle("Fusion")
    app = QApplication(sys.argv)
    app.setApplicationName("我的 RSM 实验助手（示例）")
    app.setFont(QFont("Microsoft YaHei UI", 9.5))
    apply_theme(app)

    from app.ui.main_window import MainWindow
    win = MainWindow()
    win.exp = make_paper_demo(which)
    win.exp.save()
    win.model = None
    win.optimum = None
    win.optimum_constrained = None
    win.page_new.refresh()
    win.page_design.refresh()
    win.ai_panel.refresh_stage(win.current_stage())
    from PySide6.QtCore import Qt as _Qt
    win.setWindowState(_Qt.WindowMaximized)
    win.show()
    win.raise_()
    win.activateWindow()
    from PySide6.QtCore import QTimer
    QTimer.singleShot(300, lambda: win.setWindowState(Qt.WindowMaximized))
    QTimer.singleShot(1200, lambda: win.setWindowState(Qt.WindowMaximized))
    win.statusBar().showMessage(
        f"示例已载入：{win.exp.name}（{len(win.exp.runs)} 个实验，结果全部填好）", 8000)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
