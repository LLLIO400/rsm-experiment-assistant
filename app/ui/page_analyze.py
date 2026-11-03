"""第四步：分析模型 —— 二次模型拟合、ANOVA 表、内置解读、交互式响应面图。

布局：上下排列的三张可折叠卡片（点标题行收起/展开）：
  ① 统计表（模型汇总 / 各项检验 页签）
  ② 内置解读（统计结果的白话解释）
  ③ 响应面绘图区（X/Y 轴、配色、固定因素 + 3D/等高线页签）
想看哪块就展开哪块，小窗口下把不用的卡片折叠起来即可。
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QHBoxLayout, QHeaderView,
                               QLabel, QMessageBox, QPushButton, QTabWidget,
                               QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout,
                               QWidget)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except Exception:   # noqa: BLE001
    HAS_WEBENGINE = False

from ..core import plots
from ..core.interp import interpret_model
from ..core.stats import RSMModel
from .widgets import (BAD_BG, OK_BG, FoldCard, page_header, status_chip, tip_label)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "output")

INTERP_HINT = (
    "这里会显示对统计结果的白话解读（由软件本地生成，不依赖 AI）。\n\n"
    "现在还没有内容：请先点击右上角「拟合模型」。拟合完成后，这里会自动说明"
    "模型是否可靠、哪些因素/交互项显著、以及下一步建议。"
)


def fmt_p(p: float) -> str:
    return "< 0.0001" if p < 1e-4 else f"{p:.4f}"


class PageAnalyze(QWidget):
    def __init__(self, mw):
        super().__init__()
        self.mw = mw

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 22)
        lay.setSpacing(10)

        top = QHBoxLayout()
        top.addWidget(page_header("④ 分析模型", "ANOVA · 白话解读 · 交互式响应面图"), 1)
        self.btn_fit = QPushButton("拟合模型")
        self.btn_fit.setObjectName("primary")
        top.addWidget(self.btn_fit)
        self.chip = status_chip("未拟合", None)
        top.addWidget(self.chip)
        lay.addLayout(top)
        lay.addWidget(tip_label(
            "统计量全部由 statsmodels/scipy 在本地计算：模型 F/P、各项偏检验、R²/调整R²/预测R²、"
            "失拟检验（以中心点重复为纯误差）、信噪比。AI 只负责解释，不参与计算。"
            "各卡片标题行均可点击折叠。"))
        self.btn_fit.clicked.connect(self.fit_model)

        # ================= 卡片一：统计表 =================
        self.card_tbl = FoldCard("统计表（模型汇总 · 各项检验）")
        self.tabs_tbl = QTabWidget()
        self.tbl_summary = QTableWidget()
        self.tbl_summary.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_summary.verticalHeader().setVisible(False)
        self.tbl_summary.verticalHeader().setDefaultSectionSize(30)
        self.tbl_summary.setWordWrap(True)
        self.tabs_tbl.addTab(self.tbl_summary, "模型汇总")

        self.tbl_terms = QTableWidget()
        self.tbl_terms.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_terms.verticalHeader().setVisible(False)
        self.tbl_terms.verticalHeader().setDefaultSectionSize(30)
        self.tbl_terms.setAlternatingRowColors(True)
        self.tabs_tbl.addTab(self.tbl_terms, "各项检验")
        self.tabs_tbl.setMinimumHeight(240)
        self.card_tbl.add_widget(self.tabs_tbl)
        lay.addWidget(self.card_tbl)

        # ================= 卡片二：内置解读 =================
        self.card_interp = FoldCard("内置解读（统计结果的白话解释，不依赖 AI）")
        self.txt_interp = QTextEdit()
        self.txt_interp.setReadOnly(True)
        self.txt_interp.setPlainText(INTERP_HINT)
        self.txt_interp.setMinimumHeight(96)
        self.txt_interp.setMaximumHeight(200)
        self.card_interp.add_widget(self.txt_interp)
        lay.addWidget(self.card_interp)

        # ================= 卡片三：绘图区 =================
        self.card_plot = FoldCard("响应面绘图（3D 可旋转 · 等高线）")
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("X 轴："))
        self.cmb_x = QComboBox()
        self.cmb_x.setMinimumWidth(150)
        row1.addWidget(self.cmb_x)
        row1.addWidget(QLabel("Y 轴："))
        self.cmb_y = QComboBox()
        self.cmb_y.setMinimumWidth(150)
        row1.addWidget(self.cmb_y)
        row1.addWidget(QLabel("　配色："))
        self.cmb_cmap = QComboBox()
        self.cmb_cmap.setMinimumWidth(160)
        for name in plots.COLORSCALES:
            self.cmb_cmap.addItem(name)
        self.cmb_cmap.setCurrentText(plots.DEFAULT_CMAP)
        row1.addWidget(self.cmb_cmap)
        row1.addStretch(1)
        self.card_plot.add_layout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("固定其它因素于："))
        self.fixed_spins_layout = QHBoxLayout()
        self.fixed_spins_layout.setSpacing(6)
        row2.addLayout(self.fixed_spins_layout)
        row2.addStretch(1)
        self.btn_plot = QPushButton("绘制响应面")
        self.btn_plot.setObjectName("primary")
        row2.addWidget(self.btn_plot)
        self.btn_browser = QPushButton("在浏览器打开")
        row2.addWidget(self.btn_browser)
        self.card_plot.add_layout(row2)

        if HAS_WEBENGINE:
            self.tabs = QTabWidget()
            self.view3d = QWebEngineView()
            self.view2d = QWebEngineView()
            self.tabs.addTab(self.view3d, "3D 响应面（可拖动旋转 / 滚轮缩放）")
            self.tabs.addTab(self.view2d, "二维等高线")
            self.tabs.setMinimumHeight(280)
            self.card_plot.add_widget(self.tabs, stretch=1)
        else:
            self.tabs = None
            self.card_plot.add_widget(
                tip_label("（本机缺少 QtWebEngine 组件：请点「在浏览器打开」查看交互图）"))
        lay.addWidget(self.card_plot, 1)

        self.cmb_x.currentIndexChanged.connect(self._on_axis_changed)
        self.cmb_y.currentIndexChanged.connect(self._on_axis_changed)
        self.btn_plot.clicked.connect(self.draw_plots)
        self.btn_browser.clicked.connect(self.open_in_browser)

    # ---------- 拟合 ----------
    def fit_model(self):
        exp = self.mw.exp
        if not exp.has_design():
            QMessageBox.information(self, "提示", "请先生成设计并完成实验")
            return
        try:
            self.mw.model = RSMModel(exp).fit()
        except ValueError as e:
            QMessageBox.warning(self, "无法拟合", str(e))
            return
        exp.save()
        self._fill_tables()
        self._fill_axes()
        self.mw.ai_panel.refresh_stage(self.mw.current_stage())
        self.mw.ai_panel.builtin_interpret()
        self.draw_plots()

    def _fill_tables(self):
        m = self.mw.model
        ok = m.p_model < 0.05
        self.chip.setText(f"模型 P {fmt_p(m.p_model)}，R² = {m.r2:.3f}，"
                          f"预测 R² = {m.pred_r2:.3f}" + ("（显著）" if ok else "（不显著⚠）"))
        self.chip.setStyleSheet(
            f"color:{'#15803d' if ok else '#b91c1c'};background:"
            f"{OK_BG if ok else BAD_BG};border-radius:12px;padding:4px 13px;font-weight:600;")

        rows = m.summary_rows()
        self.tbl_summary.setRowCount(len(rows))
        self.tbl_summary.setColumnCount(3)
        self.tbl_summary.setHorizontalHeaderLabels(["指标", "值", "说明"])
        sh = self.tbl_summary.horizontalHeader()
        sh.setSectionResizeMode(QHeaderView.ResizeToContents)
        sh.setSectionResizeMode(2, QHeaderView.Stretch)   # 说明列占剩余宽度
        for i, (a, b, c) in enumerate(rows):
            self.tbl_summary.setItem(i, 0, QTableWidgetItem(a))
            it = QTableWidgetItem(str(b))
            it.setTextAlignment(Qt.AlignCenter)
            self.tbl_summary.setItem(i, 1, it)
            note = QTableWidgetItem(c)
            note.setForeground(Qt.gray)
            note.setToolTip(c)
            self.tbl_summary.setItem(i, 2, note)
        # 等布局完成后再按实际列宽计算换行行高（否则说明列还没展开，行高算错）
        QTimer.singleShot(60, self.tbl_summary.resizeRowsToContents)

        heads = ["项", "含义", "系数(编码)", "标准误", "F", "P", "贡献%", "显著性"]
        self.tbl_terms.setRowCount(len(m.terms))
        self.tbl_terms.setColumnCount(len(heads))
        self.tbl_terms.setHorizontalHeaderLabels(heads)
        hh = self.tbl_terms.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setStretchLastSection(True)
        for i, t in enumerate(m.terms):
            vals = [t["label"], t["desc"], f"{t['coef']:.4g}", f"{t['se']:.3g}",
                    f"{t['f']:.2f}", fmt_p(t["p"]), f"{t['contrib']:.1f}",
                    "显著" if t["sig"] else "不显著"]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c >= 2:
                    it.setTextAlignment(Qt.AlignCenter)
                self.tbl_terms.setItem(i, c, it)
            self.tbl_terms.item(i, 5).setForeground(Qt.darkRed if t["sig"] else Qt.gray)
            sig_it = self.tbl_terms.item(i, 7)
            sig_it.setForeground(Qt.darkGreen if t["sig"] else Qt.gray)

        self.txt_interp.setPlainText(interpret_model(self.mw.exp, m))

    # ---------- 响应面 ----------
    def _fill_axes(self):
        exp = self.mw.exp
        factors = exp.factor_list()
        for cmb in (self.cmb_x, self.cmb_y):
            cmb.blockSignals(True)
            cmb.clear()
            for i, f in enumerate(factors):
                cmb.addItem(f"{chr(65 + i)}：{f.short_label()}", i)
            cmb.blockSignals(False)
        self.cmb_x.setCurrentIndex(0)
        self.cmb_y.setCurrentIndex(1 if len(factors) > 1 else 0)
        self._rebuild_fixed_spins()

    def _on_axis_changed(self):
        if self.sender() is self.cmb_x:
            if self.cmb_y.currentIndex() == self.cmb_x.currentIndex():
                other = (self.cmb_x.currentIndex() + 1) % self.cmb_y.count()
                self.cmb_y.setCurrentIndex(other)
        else:
            if self.cmb_x.currentIndex() == self.cmb_y.currentIndex():
                other = (self.cmb_y.currentIndex() + 1) % self.cmb_x.count()
                self.cmb_x.setCurrentIndex(other)
        self._rebuild_fixed_spins()

    def _rebuild_fixed_spins(self):
        exp = self.mw.exp
        factors = exp.factor_list()
        if not factors:
            return
        xi = self.cmb_x.currentData()
        yi = self.cmb_y.currentData()
        if xi is None or yi is None:
            return
        while self.fixed_spins_layout.count():
            item = self.fixed_spins_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._fixed_spins = {}
        for i, f in enumerate(factors):
            if i in (xi, yi):
                continue
            sp = QDoubleSpinBox()
            sp.setDecimals(3)
            sp.setRange(f.low, f.high)
            sp.setSingleStep(max((f.high - f.low) / 40, 1e-6))
            sp.setValue(f.center)
            sp.setFixedWidth(88)
            sp.setToolTip(f"{f.short_label()} 固定在 {f.low:g}~{f.high:g} {f.unit}")
            self.fixed_spins_layout.addWidget(QLabel(f"{chr(65 + i)}："))
            self.fixed_spins_layout.addWidget(sp)
            self._fixed_spins[i] = sp
        self.fixed_spins_layout.addStretch(1)

    def _fixed_values(self):
        exp = self.mw.exp
        factors = exp.factor_list()
        vals = [f.center for f in factors]
        # 若已找到最优条件，默认用最优条件所在截面
        if self.mw.optimum is not None:
            vals = list(self.mw.optimum["actual"])
        for i, sp in getattr(self, "_fixed_spins", {}).items():
            vals[i] = sp.value()
        return vals

    def draw_plots(self):
        m = self.mw.model
        if m is None:
            self.chip.setText("请先拟合模型")
            return
        factors = self.mw.exp.factor_list()
        xi, yi = self.cmb_x.currentData(), self.cmb_y.currentData()
        if xi is None or yi is None or len(factors) < 2:
            return
        fixed = self._fixed_values()
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        cmap = self.cmb_cmap.currentText()
        html3d = plots.surface_figure_html(m, xi, yi, fixed, cmap=cmap)
        html2d = plots.contour_figure_html(m, xi, yi, fixed, cmap=cmap)
        p3 = os.path.join(OUTPUT_DIR, "响应面_3D.html")
        p2 = os.path.join(OUTPUT_DIR, "响应面_等高线.html")
        with open(p3, "w", encoding="utf-8") as fh:
            fh.write(html3d)
        with open(p2, "w", encoding="utf-8") as fh:
            fh.write(html2d)
        self._last_html = {"3d": p3, "2d": p2}
        if HAS_WEBENGINE:
            self.view3d.load(QUrl.fromLocalFile(p3))
            self.view2d.load(QUrl.fromLocalFile(p2))

    def open_in_browser(self):
        if not hasattr(self, "_last_html"):
            self.draw_plots()
        if hasattr(self, "_last_html"):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_html["3d"]))

    def refresh(self):
        exp = self.mw.exp
        if not exp.has_design():
            self.chip.setText("尚未生成设计")
            return
        if self.mw.model is not None:
            try:
                self.mw.model = RSMModel(exp).fit()
            except ValueError:
                self.mw.model = None
        if self.mw.model is not None:
            self._fill_tables()
            self._fill_axes()
        else:
            self.chip.setText("未拟合")
            if self.txt_interp.toPlainText().strip() in ("", INTERP_HINT):
                self.txt_interp.setPlainText(INTERP_HINT)
