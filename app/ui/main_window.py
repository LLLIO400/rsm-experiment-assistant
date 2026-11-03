"""主窗口：左侧五步导航 + 中央页面 + 右侧 AI 助手面板。"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QMainWindow, QMessageBox,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from ..core.models import DATA_DIR, Experiment, load_config
from ..core.demo import DEMOS, make_paper_demo
from ..core.record import experiment_record_markdown
from .ai_panel import make_ai_dock
from .nav import NavRail
from .widgets import tip_label
from .page_analyze import PageAnalyze
from .page_design import PageDesign
from .page_new import PageNew
from .page_optimize import PageOptimize
from .page_results import PageResults

STEPS = [
    ("新建实验", "响应指标与因素水平"),
    ("设计实验", "BBD · 随机化 · 配液检查"),
    ("输入结果", "填写 / 导入实测数据"),
    ("分析模型", "ANOVA · 响应面图"),
    ("最优条件与验证", "寻优 · 可执行性 · 验证"),
]
STAGE_NAMES = ["新建实验", "设计实验", "输入结果", "模型分析", "最优条件与验证"]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.exp = Experiment.new_default()
        self.model = None
        self.optimum = None
        self.optimum_constrained = None
        self._calc_dialog = None

        self.setWindowTitle("我的 RSM 实验助手")
        self.resize(1280, 800)

        central = QWidget()
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self.nav = NavRail(STEPS)
        h.addWidget(self.nav)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)

        self.stack = QStackedWidget()
        self.page_new = PageNew(self)
        self.page_design = PageDesign(self)
        self.page_results = PageResults(self)
        self.page_analyze = PageAnalyze(self)
        self.page_optimize = PageOptimize(self)
        for p in (self.page_new, self.page_design, self.page_results,
                  self.page_analyze, self.page_optimize):
            self.stack.addWidget(p)
        rv.addWidget(self.stack, 1)

        footer = QWidget()
        footer.setObjectName("footerBar")
        fh = QHBoxLayout(footer)
        fh.setContentsMargins(16, 10, 16, 10)
        self.lbl_footer = tip_label("")
        fh.addWidget(self.lbl_footer, 1)
        self.btn_prev = QPushButton("←  上一步")
        self.btn_prev.clicked.connect(self.prev_step)
        fh.addWidget(self.btn_prev)
        self.btn_next = QPushButton("下一步  →")
        self.btn_next.setObjectName("primary")
        self.btn_next.clicked.connect(self.next_step)
        fh.addWidget(self.btn_next)
        fm = QVBoxLayout()
        fm.setContentsMargins(26, 0, 26, 14)
        fm.addWidget(footer)
        rv.addLayout(fm)

        h.addWidget(right, 1)
        self.setCentralWidget(central)

        self.ai = make_ai_dock(self._ai_state)
        self.ai_panel = self.ai.widget()
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai)
        screen = self.screen().availableGeometry() if self.screen() else None
        if screen:
            self.resize(min(1460, int(screen.width() * 0.94)),
                        min(900, int(screen.height() * 0.9)))
        else:
            self.resize(1460, 900)

        self.nav.currentRowChanged.connect(self._switch)
        self.nav.setCurrentRow(0)
        self._make_menus()
        self.page_design.refresh()
        self.page_new.refresh()
        self.ai_panel.refresh_stage(self.current_stage())
        self._update_footer()

    # ---------- 导航 ----------
    def _switch(self, idx: int):
        self.stack.setCurrentIndex(idx)
        page = self.stack.widget(idx)
        if hasattr(page, "refresh"):
            try:
                page.refresh()
            except Exception as e:   # noqa: BLE001
                QMessageBox.warning(self, "刷新页面出错", str(e))
        self.ai_panel.refresh_stage(self.current_stage())
        self._update_footer()

    def current_stage(self) -> str:
        return STAGE_NAMES[self.nav.currentRow()]

    FOOTER_HINTS = [
        "填好响应指标与 3~5 个因素的水平，然后点「下一步」。",
        "确认配液设置后点「生成设计」；方案全部可执行就可以导出 Excel 去做实验。",
        "实验做完，把实测值填进最后一列（可从 Excel 粘贴）；全部填完后进入分析。",
        "点「拟合模型」查看左侧 ANOVA 与解读；右侧可直接交互查看 3D 响应面和等高线。",
        "点「寻找最佳条件」；条件可执行就去做验证实验，填入实测值完成闭环。",
    ]

    def _update_footer(self):
        idx = self.nav.currentRow()
        self.btn_prev.setVisible(idx > 0)
        self.btn_next.setVisible(idx < len(STEPS) - 1)
        self.lbl_footer.setText(self.FOOTER_HINTS[idx] if idx < len(self.FOOTER_HINTS) else "")

    def prev_step(self):
        idx = self.nav.currentRow()
        if idx > 0:
            self.nav.setCurrentRow(idx - 1)

    def next_step(self):
        idx = self.nav.currentRow()
        if idx >= len(STEPS) - 1:
            return
        if idx == 0:
            try:
                self.page_new.save_to_exp()
            except ValueError as e:
                QMessageBox.warning(self, "还不能进入下一步", str(e))
                return
        elif idx == 1:
            if not self.exp.has_design():
                QMessageBox.information(self, "请先生成设计",
                                        "先点击「生成设计（重新随机化）」得到实验方案，再进入下一步。")
                return
        elif idx == 2:
            missing = len(self.exp.runs) - self.exp.n_done()
            if missing:
                ret = QMessageBox.question(
                    self, "还有未填结果",
                    f"还有 {missing} 个实验没有填实测值，确定要跳到模型分析吗？（分析需要全部结果）",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if ret != QMessageBox.Yes:
                    return
        elif idx == 3 and self.model is None:
            self.page_analyze.fit_model()
            if self.model is None:
                return
        self.nav.setCurrentRow(idx + 1)

    def _ai_state(self):
        opt = self.optimum or self.optimum_constrained
        return self.exp, self.model, opt, self.current_stage()

    # ---------- 菜单 ----------
    def _make_menus(self):
        m = self.menuBar().addMenu("项目(&P)")
        act_new = QAction("新建实验", self)
        act_new.triggered.connect(self.new_experiment)
        act_open = QAction("打开实验…", self)
        act_open.setShortcut(QKeySequence.Open)
        act_open.triggered.connect(self.open_experiment)
        act_save = QAction("保存", self)
        act_save.setShortcut(QKeySequence.Save)
        act_save.triggered.connect(self.save_experiment)
        act_record = QAction("导出实验记录 (Markdown)…", self)
        act_record.triggered.connect(self.export_record)
        act_dir = QAction("打开数据文件夹", self)
        act_dir.triggered.connect(
            lambda: QDesktopServices.openUrl(
                QUrl.fromLocalFile(DATA_DIR if os.path.exists(DATA_DIR)
                                   else os.path.dirname(self.exp.file_path or "."))))
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(self.close)
        for a in (act_new, act_open, act_save, act_record, act_dir, act_quit):
            m.addAction(a)

        t = self.menuBar().addMenu("工具(&T)")
        act_calc = QAction("摩尔浓度 / 稀释 计算器…", self)
        act_calc.setShortcut(QKeySequence("Ctrl+L"))
        act_calc.triggered.connect(self.open_calculator)
        t.addAction(act_calc)

        h = self.menuBar().addMenu("帮助(&H)")
        act_skill = QAction("查看 RSM Skill（实验大脑说明书）", self)
        act_skill.triggered.connect(self.view_skill)
        h.addAction(act_skill)
        act_about = QAction("关于", self)
        act_about.triggered.connect(self.about)
        h.addAction(act_about)

    # ---------- 项目动作 ----------
    def new_experiment(self):
        if not self._confirm_discard():
            return
        self.exp = Experiment.new_default()
        self.model = None
        self.optimum = None
        self.optimum_constrained = None
        self.nav.setCurrentRow(0)
        self.page_new.refresh()
        self.ai_panel.refresh_stage(self.current_stage())

    def load_demo(self, which: str):
        """一键填入公开文献示例：因素 + BBD 设计 + 26 个实测结果。"""
        self.save_experiment(silent=True)
        try:
            self.exp = make_paper_demo(which)
        except Exception as e:   # noqa: BLE001
            QMessageBox.warning(self, "载入示例失败", str(e))
            return
        self.model = None
        self.optimum = None
        self.optimum_constrained = None
        self.exp.save()
        self.nav.setCurrentRow(0)
        self.page_new.refresh()
        self.page_design.refresh()
        self.ai_panel.refresh_stage(self.current_stage())
        QMessageBox.information(
            self, "示例已载入",
            f"「{self.exp.name}」已填好：4 个因素、26 个实验的 BBD 设计和全部实测结果。\n\n"
            f"可直接点「下一步」走到第 ④ 步拟合模型、第 ⑤ 步寻找最优条件；\n"
            f"也可以随时改因素名/范围再来一遍。")

    def open_experiment(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "打开实验", DATA_DIR,
                                              "RSM 实验 (*.json)")
        if not path:
            return
        try:
            self.exp = Experiment.load(path)
        except Exception as e:   # noqa: BLE001
            QMessageBox.warning(self, "打开失败", str(e))
            return
        self.model = None
        self.optimum = None
        self.optimum_constrained = None
        self.nav.setCurrentRow(0)
        self.page_new.refresh()
        self.ai_panel.refresh_stage(self.current_stage())

    def save_experiment(self, silent: bool = False):
        try:
            self.page_new.save_to_exp()
        except ValueError as e:
            if not silent:
                QMessageBox.warning(self, "无法保存", str(e))
            return
        path = self.exp.save()
        if not silent:
            self.statusBar().showMessage(f"已保存：{path}", 5000)

    def export_record(self):
        self.save_experiment(silent=True)
        path, _ = QFileDialog.getSaveFileName(self, "导出实验记录",
                                              f"{self.exp.name}_实验记录.md",
                                              "Markdown (*.md)")
        if not path:
            return
        opt = self.optimum or self.optimum_constrained
        try:
            text = experiment_record_markdown(self.exp, self.model, opt)
        except Exception as e:   # noqa: BLE001
            QMessageBox.warning(self, "导出失败", str(e))
            return
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def open_calculator(self):
        """摩尔浓度/稀释/摩尔质量计算器（非模态，可边做实验边算）。"""
        from .dialog_calc import CalculatorDialog
        if self._calc_dialog is None:
            self._calc_dialog = CalculatorDialog(self)
        self._calc_dialog.show()
        self._calc_dialog.raise_()
        self._calc_dialog.activateWindow()

    def view_skill(self):
        from ..core.models import SKILL_PATH
        QDesktopServices.openUrl(QUrl.fromLocalFile(SKILL_PATH))

    def about(self):
        QMessageBox.about(
            self, "关于",
            "<b>我的 RSM 实验助手</b><br>面向实验人员的响应面法（RSM/BBD）优化工具。<br><br>"
            "流程：确定因素 → BBD → 实验 → 填结果 → 分析 → 找最优 → 验证。<br>"
            "统计计算：statsmodels / scipy / numpy（本地完成）；<br>"
            "AI 助手只做解释，不参与计算。<br><br>"
            "一句话：单因素定范围，BBD 看组合；模型找最优，实验做验证。")

    def _confirm_discard(self) -> bool:
        return True

    def closeEvent(self, ev):
        self.save_experiment(silent=True)
        super().closeEvent(ev)
