# -*- coding: utf-8 -*-
"""离屏自检：完整跑一遍用户流程并截图每一页。"""
import os
import shutil
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")
APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.core.models import Experiment
from app.core.stats import RSMModel
from app.ui.theme import apply_theme

SHOTS = os.path.join(APP_DIR, "_shots")


def true_response(a, b, c):
    na, nb, nc = (a - 2) / 1, (b - 0.4) / 0.2, (c - 10) / 5
    return 45800 - 6800 * na ** 2 - 5200 * nb ** 2 - 4100 * nc ** 2 + 3600 * na * nb


def main():
    QApplication.setStyle("Fusion")
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 9.5))
    apply_theme(app)
    from app.ui.main_window import MainWindow
    win = MainWindow()

    os.makedirs(SHOTS, exist_ok=True)
    errors = []

    def snap(name):
        app.processEvents()
        img = win.grab().toImage()
        img.save(os.path.join(SHOTS, name))
        print("shot:", name)

    def step():
        try:
            # 第 0 步：空白新建实验 → 模拟用户输入 LAMP 示例
            snap("1_新建实验_空白.png")
            from app.core.models import Experiment, Factor, SystemSetup, FixedComponent
            win.exp = Experiment(
                name="LAMP反应体系优化", response_name="荧光强度", objective="max",
                factors=[
                    Factor(name="Mg2+浓度", unit="mM", low=1, center=2, high=3,
                           volume_mode="stock", stock_conc=25, stock_label="Mg2+母液(25mM)"),
                    Factor(name="引物浓度", unit="μM", low=0.2, center=0.4, high=0.6,
                           volume_mode="stock", stock_conc=10, stock_label="引物母液(10x)"),
                    Factor(name="试剂C浓度", unit="mM", low=5, center=10, high=15,
                           volume_mode="direct"),
                ],
                system=SystemSetup(fixed_components=[FixedComponent("DNA", 20.0).__dict__.copy()]),
            )
            win.page_new.refresh()
            win.page_design.refresh()
            snap("1_新建实验.png")
            win.nav.setCurrentRow(1)

            def stage2():
                win.page_design.generate()
                snap("2_设计实验.png")
                win.nav.setCurrentRow(2)

                def stage3():
                    print("stage3 begin", flush=True)
                    rng = np.random.default_rng(11)
                    for r in win.exp.run_list():
                        a, b, c = r.actual
                        r.response = float(true_response(a, b, c) + rng.normal(0, 500))
                    print("responses set", flush=True)
                    win.page_results.refresh()
                    print("page3 refreshed", flush=True)
                    snap("3_输入结果.png")
                    win.nav.setCurrentRow(3)

                    def stage4():
                        win.page_analyze.fit_model()
                        snap("4_分析模型.png")
                        win.nav.setCurrentRow(4)

                        def stage5():
                            win.page_optimize.find(constrained=False)
                            opt = win.optimum
                            if opt:
                                win.sp_actual_target = None
                                from PySide6.QtWidgets import QDoubleSpinBox
                                win.page_optimize.sp_actual.setValue(opt["yhat"] * 0.975)
                                win.page_optimize.validate()
                            snap("5_最优条件与验证.png")

                            # AI 面板内置解读（无 API）
                            win.ai_panel.builtin_interpret()
                            snap("6_AI内置解读.png")
                            print("OFFSCREEN OK")
                            app.quit()

                        QTimer.singleShot(10, stage5)

                    QTimer.singleShot(10, stage4)

                QTimer.singleShot(10, stage3)

            QTimer.singleShot(10, stage2)
        except Exception as e:
            import traceback
            traceback.print_exc()
            errors.append(e)
            app.quit()

    QTimer.singleShot(10, step)
    app.exec()
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
