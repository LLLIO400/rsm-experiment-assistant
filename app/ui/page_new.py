"""第一步：新建实验 —— 用实验语言填写，不接触编码水平等统计学概念。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QDoubleSpinBox, QFormLayout, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QRadioButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..core.models import Experiment, Factor
from .widgets import FoldCard, page_header, read_float, tip_label

MAX_FACTORS = 5


class PageNew(QWidget):
    changed = Signal()

    def __init__(self, mw):
        super().__init__()
        self.mw = mw
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 22)
        lay.setSpacing(12)

        lay.addWidget(page_header("① 新建实验",
                                  "定义响应指标与因素水平 —— 编码水平等统计细节由软件处理"))
        lay.addWidget(tip_label(
            "用实验语言填写即可：软件会自动处理编码水平、设计矩阵等统计学细节。"
            "先定响应指标和优化目标，再列出要考察的因素及其低/中心/高水平（水平范围建议来自单因素实验）。"))

        # ---- 响应信息 ----
        g1 = FoldCard("响应指标与优化目标")
        f1 = QFormLayout()
        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("如：LAMP反应体系优化")
        self.ed_resp = QLineEdit()
        self.ed_unit = QLineEdit()
        f1.addRow("实验名称", self.ed_name)
        f1.addRow("响应指标", self.ed_resp)
        f1.addRow("单位（可空）", self.ed_unit)

        h = QHBoxLayout()
        self.rb_max = QRadioButton("最大化（越大越好）")
        self.rb_min = QRadioButton("最小化（越小越好）")
        self.rb_target = QRadioButton("目标值")
        self.sp_target = QDoubleSpinBox()
        self.sp_target.setDecimals(4)
        self.sp_target.setRange(-1e12, 1e12)
        self.sp_target.setEnabled(False)
        self.rb_max.setChecked(True)
        self.rb_target.toggled.connect(self.sp_target.setEnabled)
        for rb in (self.rb_max, self.rb_min, self.rb_target):
            h.addWidget(rb)
        h.addWidget(QLabel("目标值："))
        h.addWidget(self.sp_target)
        h.addStretch(1)
        f1.addRow("优化目标", h)
        g1.set_body(f1)
        lay.addWidget(g1)

        # ---- 因素表 ----
        g2 = FoldCard("实验因素（勾选启用，3~5 个）")
        self.tbl = QTableWidget(MAX_FACTORS, 6)
        self.tbl.setHorizontalHeaderLabels(["启用", "因素名称", "单位", "最低(-1)", "中心(0)", "最高(+1)"])
        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        self.tbl.setColumnWidth(0, 48)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in (2, 3, 4, 5):
            hh.setSectionResizeMode(col, QHeaderView.Fixed)
            self.tbl.setColumnWidth(col, 96)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.verticalHeader().setDefaultSectionSize(36)
        self.tbl.setFixedHeight(36 * (MAX_FACTORS + 1) + 8)
        self.tbl.itemChanged.connect(self._on_item_changed)
        g2.add_widget(tip_label("「中心」自动取（最低+最高）/2 —— BBD 要求三水平对称；"
                                "点上方标题行可折叠本卡片。"))
        g2.add_widget(self.tbl)
        lay.addWidget(g2)
        lay.addStretch(1)

        self.tbl.itemChanged.connect(lambda *_: self.changed.emit())
        self.ed_name.textChanged.connect(lambda *_: self.changed.emit())
        self.ed_resp.textChanged.connect(lambda *_: self.changed.emit())
        self.ed_unit.textChanged.connect(lambda *_: self.changed.emit())
        self.rb_max.toggled.connect(lambda *_: self.changed.emit())
        self.rb_min.toggled.connect(lambda *_: self.changed.emit())
        self.rb_target.toggled.connect(lambda *_: self.changed.emit())
        self.sp_target.valueChanged.connect(lambda *_: self.changed.emit())

    # ---------- 读写界面 ----------
    def refresh(self):
        exp = self.mw.exp
        self._loading = True
        self.ed_name.setText(exp.name)
        self.ed_resp.setText(exp.response_name)
        self.ed_unit.setText(exp.response_unit)
        (self.rb_max if exp.objective == "max" else
         self.rb_min if exp.objective == "min" else self.rb_target).setChecked(True)
        if exp.target_value is not None:
            self.sp_target.setValue(float(exp.target_value))
        self.tbl.blockSignals(True)
        factors = exp.factor_list()
        self._checks = []
        for r in range(MAX_FACTORS):
            cell = self._make_center_checkbox()
            self.tbl.setCellWidget(r, 0, cell)
            cell._chk.setChecked(r < len(factors))
            vals = ["", "", "", "", ""]
            if r < len(factors):
                f = factors[r]
                vals = [f.name, f.unit, f"{f.low:g}", f"{f.center:g}", f"{f.high:g}"]
            for c, v in enumerate(vals, start=1):
                item = self.tbl.item(r, c)
                if item is None:
                    item = QTableWidgetItem(v)
                    self.tbl.setItem(r, c, item)
                elif item.text() != v:
                    item.setText(v)
        self.tbl.blockSignals(False)
        self._loading = False

    def _make_center_checkbox(self) -> QWidget:
        cell = QWidget()
        hl = QHBoxLayout(cell)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setAlignment(Qt.AlignCenter)
        chk = QCheckBox()
        chk.stateChanged.connect(lambda *_: self.changed.emit())
        hl.addWidget(chk)
        cell._chk = chk
        return cell

    def save_to_exp(self):
        exp = self.mw.exp
        exp.name = self.ed_name.text().strip() or "未命名实验"
        exp.response_name = self.ed_resp.text().strip() or "响应值"
        exp.response_unit = self.ed_unit.text().strip()
        exp.objective = ("max" if self.rb_max.isChecked() else
                         "min" if self.rb_min.isChecked() else "target")
        exp.target_value = self.sp_target.value() if self.rb_target.isChecked() else None
        factors = []
        for r in range(MAX_FACTORS):
            cell = self.tbl.cellWidget(r, 0)
            chk = getattr(cell, "_chk", None) if cell is not None else None
            if chk is None or not chk.isChecked():
                continue
            name = self.tbl.item(r, 1).text().strip() if self.tbl.item(r, 1) else ""
            unit = self.tbl.item(r, 2).text().strip() if self.tbl.item(r, 2) else ""
            low = read_float(self.tbl.item(r, 3).text()) if self.tbl.item(r, 3) else None
            cen = read_float(self.tbl.item(r, 4).text()) if self.tbl.item(r, 4) else None
            high = read_float(self.tbl.item(r, 5).text()) if self.tbl.item(r, 5) else None
            if low is None or cen is None or high is None:
                raise ValueError(f"第 {r + 1} 行因素的水平数值不完整")
            if not (low < cen < high):
                raise ValueError(f"因素「{name or r + 1}」的水平必须满足 最低 < 中心 < 最高")
            factors.append(Factor(name=name or f"因素{chr(65 + len(factors))}", unit=unit,
                                  low=low, center=cen, high=high))
        if len(factors) < 3:
            raise ValueError("BBD 至少需要启用 3 个因素")
        # 保留配液设置
        old = {id(f): f for f in exp.factor_list()}
        for i, nf in enumerate(factors):
            if i < len(exp.factors):
                nf.volume_mode = exp.factor_list()[i].volume_mode
                nf.stock_conc = exp.factor_list()[i].stock_conc
                nf.stock_label = exp.factor_list()[i].stock_label
        exp.factors = factors

    def _on_item_changed(self, item):
        if getattr(self, "_loading", False):
            return
        # 低/高变化时自动把中心设为中点
        if item.column() in (3, 5):
            r = item.row()
            low = read_float(self.tbl.item(r, 3).text()) if self.tbl.item(r, 3) else None
            high = read_float(self.tbl.item(r, 5).text()) if self.tbl.item(r, 5) else None
            if low is not None and high is not None and low < high:
                self.tbl.blockSignals(True)
                mid = (low + high) / 2
                self.tbl.setItem(r, 4, QTableWidgetItem(f"{mid:g}"))
                self.tbl.blockSignals(False)
