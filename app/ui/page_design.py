"""第二步：设计实验 —— 生成 BBD、随机化、显示实际实验值，并做配液可行性检查。

配液设置用 QGridLayout 表单（不用内嵌控件的表格）：控件按列对齐、
随窗口伸缩，长文本（如"按母液浓度换算"）不会被截断。
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QSpinBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import doegen, excelio, volume
from ..core.models import DATA_DIR, FixedComponent
from .widgets import (BAD_BG, OK_BG, WARN_BG, FoldCard, page_header, section_title,
                      status_chip, tip_label)

PREP_MODES = [("不参与体积检查", "none"), ("按体积(μL)直接加入", "direct"),
              ("按母液浓度换算", "stock")]


def _grid_header(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setStyleSheet("color:#6b7280;font-size:8.5pt;font-weight:600;"
                      "border-bottom:1px solid #e7eaf0;padding:2px 0;")
    return lab


class PageDesign(QWidget):
    changed = Signal()

    def __init__(self, mw):
        super().__init__()
        self.mw = mw
        self._loading = True          # 构造/重建期间禁止信号回写 exp.system
        self._fixed_rows = []         # [(name_edit, vol_spin)]
        self._mode_rows = []          # [(combo, conc_edit, label_edit)]
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 22)
        lay.setSpacing(12)

        top = QHBoxLayout()
        top.addWidget(page_header("② 设计实验", "BBD 生成 · 随机化运行序 · 配液可行性检查"), 1)
        top.addWidget(QLabel("中心点数："))
        self.sp_center = QSpinBox()
        self.sp_center.setRange(2, 8)
        self.sp_center.setValue(5)
        top.addWidget(self.sp_center)
        self.btn_gen = QPushButton("生成设计（重新随机化）")
        self.btn_gen.setObjectName("primary")
        top.addWidget(self.btn_gen)
        lay.addLayout(top)
        lay.addWidget(tip_label(
            "软件自动完成：生成 BBD 矩阵 → 把 -1/0/+1 换算成实际实验值 → 随机化实验顺序 → "
            "加入中心点。请按「运行序」做实验，避免时间趋势混入因素效应。"))
        self.btn_gen.clicked.connect(self.generate)

        # ---- 配液检查（可折叠） ----
        self.gs = FoldCard("反应体系与配液检查（点这行可折叠/展开）")
        vs = QVBoxLayout()
        row1 = QHBoxLayout()
        self.chk_sys = QCheckBox("启用体系检查")
        self.sp_total = QDoubleSpinBox()
        self.sp_total.setRange(1, 1e6)
        self.sp_total.setDecimals(2)
        self.sp_total.setSuffix(" μL")
        self.sp_min = QDoubleSpinBox()
        self.sp_min.setRange(0, 1e4)
        self.sp_min.setDecimals(2)
        self.sp_min.setSuffix(" μL")
        row1.addWidget(self.chk_sys)
        row1.addWidget(QLabel("总反应体积："))
        row1.addWidget(self.sp_total)
        row1.addWidget(QLabel("　最小可移液体积："))
        row1.addWidget(self.sp_min)
        row1.addWidget(QLabel("　补足液：水（自动补足至总体积）"))
        row1.addStretch(1)
        vs.addLayout(row1)

        # 固定组分（网格表单）
        vs.addWidget(section_title("固定组分（体积固定、不参与优化）"))
        self.host_fixed = QWidget()
        self.grid_fixed = QGridLayout(self.host_fixed)
        self.grid_fixed.setContentsMargins(0, 0, 0, 0)
        self.grid_fixed.setHorizontalSpacing(10)
        self.grid_fixed.setVerticalSpacing(6)
        self.grid_fixed.setColumnStretch(0, 3)
        self.grid_fixed.setColumnStretch(1, 1)
        self.grid_fixed.setColumnStretch(2, 0)
        vs.addWidget(self.host_fixed)
        self.btn_add_fixed = QPushButton("＋ 添加固定组分")
        self.btn_add_fixed.clicked.connect(self._add_fixed)
        vs.addWidget(self.btn_add_fixed)

        # 因素加入方式（网格表单）
        vs.addWidget(section_title("各因素加入方式（决定配液体积怎么算）"))
        self.host_mode = QWidget()
        self.grid_mode = QGridLayout(self.host_mode)
        self.grid_mode.setContentsMargins(0, 0, 0, 0)
        self.grid_mode.setHorizontalSpacing(10)
        self.grid_mode.setVerticalSpacing(6)
        for col, stretch in ((0, 3), (1, 3), (2, 2), (3, 3)):
            self.grid_mode.setColumnStretch(col, stretch)
        vs.addWidget(self.host_mode)
        vs.addWidget(tip_label(
            "换算公式：加入体积 = 因素取值 × 总体积 ÷ 母液浓度；"
            "若因素直接以加入体积(μL)定义，选「按体积直接加入」。"))
        self.gs.set_body(vs)
        lay.addWidget(self.gs)

        self.chk_sys.stateChanged.connect(lambda *_: self._settings_changed())
        self.sp_total.valueChanged.connect(lambda *_: self._settings_changed())
        self.sp_min.valueChanged.connect(lambda *_: self._settings_changed())

        # ---- 设计表 ----
        lay.addWidget(section_title("实验方案（含配液体积）"))
        self.chip = status_chip("尚未生成设计", None)
        lay.addWidget(self.chip)
        self.tbl = QTableWidget()
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.verticalHeader().setDefaultSectionSize(32)
        lay.addWidget(self.tbl, 1)

        bottom = QHBoxLayout()
        self.btn_export = QPushButton("导出实验方案 Excel")
        self.btn_open_dir = QPushButton("打开数据文件夹")
        bottom.addWidget(self.btn_export)
        bottom.addWidget(self.btn_open_dir)
        bottom.addStretch(1)
        self.lbl_next = tip_label("")
        bottom.addWidget(self.lbl_next)
        lay.addLayout(bottom)

        self.btn_export.clicked.connect(self.export_excel)
        self.btn_open_dir.clicked.connect(self.open_dir)
        self._loading = False

    # ---------- 配液设置读写 ----------
    def _add_fixed(self):
        s = self.mw.exp.system
        s.fixed_components.append(FixedComponent(name="", volume=5.0).__dict__.copy())
        self._rebuild_fixed()
        self._settings_changed()

    def _del_fixed(self, idx: int):
        s = self.mw.exp.system
        if 0 <= idx < len(s.fixed_components):
            s.fixed_components.pop(idx)
            self._rebuild_fixed()
            self._settings_changed()

    def _settings_changed(self):
        if getattr(self, "_loading", False):
            return
        self.save_system()
        self.refresh_table()
        self.changed.emit()

    def save_system(self):
        s = self.mw.exp.system
        s.enabled = self.chk_sys.isChecked()
        s.total_volume = self.sp_total.value()
        s.min_pipette = self.sp_min.value()
        fixed = []
        for name_edit, vol_spin in self._fixed_rows:
            name = name_edit.text().strip()
            if name:
                fixed.append(FixedComponent(name=name, volume=vol_spin.value()).__dict__.copy())
        s.fixed_components = fixed
        factors = self.mw.exp.factor_list()
        for r, (combo, conc_edit, label_edit) in enumerate(self._mode_rows):
            if r >= len(factors):
                break
            factors[r].volume_mode = combo.currentData()
            txt = conc_edit.text().strip()
            try:
                factors[r].stock_conc = float(txt) if txt else None
            except ValueError:
                factors[r].stock_conc = None
            factors[r].stock_label = label_edit.text().strip()
        self.mw.exp.factors = factors

    # ---------- 网格重建 ----------
    def _rebuild_fixed(self):
        self._loading = True
        while self.grid_fixed.count():
            item = self.grid_fixed.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._fixed_rows = []
        s = self.mw.exp.system
        for c, col in ((0, "名称"), (1, "体积(μL)"), (2, "")):
            self.grid_fixed.addWidget(_grid_header(col), 0, c)
        for r, fc in enumerate(s.fixed_list(), start=1):
            name_edit = QLineEdit(fc.name)
            name_edit.setPlaceholderText("如 DNA 模板")
            vol_spin = QDoubleSpinBox()
            vol_spin.setRange(0, 1e6)
            vol_spin.setDecimals(2)
            vol_spin.setValue(fc.volume)
            vol_spin.setMinimumWidth(96)
            del_btn = QPushButton("✕")
            del_btn.setFixedSize(30, 28)
            del_btn.setToolTip("删除该固定组分")
            del_btn.clicked.connect(lambda _=False, i=r - 1: self._del_fixed(i))
            name_edit.textChanged.connect(lambda *_: self._settings_changed())
            vol_spin.valueChanged.connect(lambda *_: self._settings_changed())
            self.grid_fixed.addWidget(name_edit, r, 0)
            self.grid_fixed.addWidget(vol_spin, r, 1)
            self.grid_fixed.addWidget(del_btn, r, 2, Qt.AlignLeft)
            self._fixed_rows.append((name_edit, vol_spin))
        self._loading = False

    def _rebuild_modes(self):
        self._loading = True
        while self.grid_mode.count():
            item = self.grid_mode.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._mode_rows = []
        for c, col in enumerate(("因素", "加入方式", "母液浓度(与因素单位相同)", "母液名称(可选)")):
            self.grid_mode.addWidget(_grid_header(col), 0, c)
        for r, f in enumerate(self.mw.exp.factor_list(), start=1):
            lab = QLabel(f"{chr(65 + r - 1)}：{f.short_label()}")
            lab.setStyleSheet("font-weight:600;padding:2px 0;")
            combo = QComboBox()
            combo.setMinimumWidth(190)
            for label, key in PREP_MODES:
                combo.addItem(label, key)
            mode = f.volume_mode if f.volume_mode in [k for _, k in PREP_MODES] else "none"
            combo.setCurrentIndex([k for _, k in PREP_MODES].index(mode))
            conc_edit = QLineEdit("" if f.stock_conc is None else f"{f.stock_conc:g}")
            conc_edit.setPlaceholderText("如 25")
            conc_edit.setMinimumWidth(90)
            label_edit = QLineEdit(f.stock_label or "")
            label_edit.setPlaceholderText("如 Mg²⁺母液")
            combo.currentIndexChanged.connect(lambda *_: self._settings_changed())
            conc_edit.textChanged.connect(lambda *_: self._settings_changed())
            label_edit.textChanged.connect(lambda *_: self._settings_changed())
            self.grid_mode.addWidget(lab, r, 0)
            self.grid_mode.addWidget(combo, r, 1)
            self.grid_mode.addWidget(conc_edit, r, 2)
            self.grid_mode.addWidget(label_edit, r, 3)
            self._mode_rows.append((combo, conc_edit, label_edit))
        self._loading = False

    # ---------- 生成与展示 ----------
    def generate(self):
        try:
            self.mw.page_new.save_to_exp()
        except ValueError as e:
            QMessageBox.warning(self, "请先完善第一步", str(e))
            return
        self.save_system()
        exp = self.mw.exp
        try:
            doegen.generate_design(exp)
        except ValueError as e:
            QMessageBox.warning(self, "无法生成设计", str(e))
            return
        exp.touch()
        exp.save()
        self.mw.model = None
        self.mw.optimum = None
        self.refresh()
        self.gs.set_collapsed(True)   # 已生效的设置收起，把空间让给实验方案表
        self.changed.emit()

    def refresh(self):
        exp = self.mw.exp
        s = exp.system
        self._loading = True
        self.chk_sys.setChecked(s.enabled)
        self.sp_total.setValue(s.total_volume)
        self.sp_min.setValue(s.min_pipette)
        self._loading = False
        self._rebuild_fixed()
        self._rebuild_modes()
        self.refresh_table()

    def refresh_table(self):
        exp = self.mw.exp
        if not exp.has_design():
            self.tbl.setRowCount(0)
            self.chip.setText("尚未生成设计 —— 请点击「生成设计」")
            self.chip.setStyleSheet(
                f"color:#92400e;background:{WARN_BG};border-radius:12px;"
                f"padding:4px 13px;font-weight:600;")
            return
        prep = volume.prep_table(exp)
        prep_map = {p["std"]: p for p in prep}
        factors = exp.factor_list()
        headers = ["运行序", "标准序"]
        for f in factors:
            headers.append(f"{f.short_label()}({f.unit})" if f.unit else f.short_label())
        if exp.system.enabled:
            for i, f in enumerate(factors):
                if any(p["volumes"][i] is not None for p in prep):
                    headers.append(f"{f.short_label()}体积")
            headers.append(f"{exp.system.filler_name}体积")
            headers.append("配液可行")
        headers.append(exp.response_name or "实测值")

        runs = exp.runs_in_order()
        self.tbl.setRowCount(len(runs))
        self.tbl.setColumnCount(len(headers))
        self.tbl.setHorizontalHeaderLabels(headers)
        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setStretchLastSection(True)
        for c in range(len(headers)):
            it = self.tbl.horizontalHeaderItem(c)
            it.setTextAlignment(Qt.AlignCenter)
        for r_i, run in enumerate(runs):
            p = prep_map[run.std]
            col = 0
            vals = [run.order, run.std] + [f"{v:g}" for v in run.actual]
            for v in vals:
                it = QTableWidgetItem(str(v))
                it.setTextAlignment(Qt.AlignCenter)
                self.tbl.setItem(r_i, col, it)
                col += 1
            if exp.system.enabled:
                for i, vol in enumerate(p["volumes"]):
                    if vol is None:
                        continue
                    it = QTableWidgetItem(f"{vol:.2f}")
                    it.setTextAlignment(Qt.AlignCenter)
                    self.tbl.setItem(r_i, col, it)
                    col += 1
                water_txt = "—" if p["water"] is None else f"{p['water']:.2f}"
                it = QTableWidgetItem(water_txt)
                it.setTextAlignment(Qt.AlignCenter)
                if p["water"] is not None and p["water"] < exp.system.water_min:
                    it.setBackground(QColor(BAD_BG))
                self.tbl.setItem(r_i, col, it)
                col += 1
                ok_it = QTableWidgetItem("✓ 可执行" if p["ok"] else "⚠ 无法配制")
                ok_it.setTextAlignment(Qt.AlignCenter)
                if not p["ok"]:
                    ok_it.setBackground(QColor(BAD_BG))
                    ok_it.setToolTip("；".join(p["issues"]))
                self.tbl.setItem(r_i, col, ok_it)
                col += 1
            resp = "—" if run.response is None else f"{run.response:.4g}"
            it = QTableWidgetItem(resp)
            it.setTextAlignment(Qt.AlignCenter)
            self.tbl.setItem(r_i, col, it)

        n_bad = sum(1 for p in prep if not p["ok"])
        if n_bad == 0:
            self.chip.setText(f"✓ BBD 共 {len(runs)} 个实验，全部条件可配制"
                              f"（总体系 {exp.system.total_volume:g} μL）")
            self.chip.setStyleSheet(
                f"color:#15803d;background:{OK_BG};border-radius:12px;"
                f"padding:4px 13px;font-weight:600;")
        else:
            self.chip.setText(f"⚠ {n_bad} 个实验条件在实际体系中无法配制："
                              f"请调整因素范围或体系设置（统计设计成立 ≠ 实验可执行）")
            self.chip.setStyleSheet(
                f"color:#b91c1c;background:{BAD_BG};border-radius:12px;"
                f"padding:4px 13px;font-weight:600;")
        self.lbl_next.setText("方案可行后 → 第三步：做完实验回来填结果。")

    def export_excel(self):
        exp = self.mw.exp
        if not exp.has_design():
            QMessageBox.information(self, "提示", "请先生成设计")
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出实验方案", f"{exp.name}_实验方案.xlsx",
                                              "Excel 文件 (*.xlsx)")
        if not path:
            return
        excelio.export_design_excel(exp, path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def open_dir(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(DATA_DIR))
