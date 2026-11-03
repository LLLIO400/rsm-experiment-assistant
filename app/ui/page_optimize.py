"""第五步：最优条件与验证 —— 数值寻优、配液可行性检查、验证实验闭环。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDoubleSpinBox, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem, QTextEdit,
                               QVBoxLayout, QWidget)

from ..core.interp import interpret_optimum, interpret_validation
from ..core.optimizer import find_optimum
from .widgets import (BAD_BG, OK_BG, WARN_BG, FoldCard, page_header, status_chip,
                      tip_label)


class PageOptimize(QWidget):
    def __init__(self, mw):
        super().__init__()
        self.mw = mw
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 22)
        lay.setSpacing(12)

        lay.addWidget(page_header("⑤ 最优条件与验证", "预测最优 · 配液可执行性 · 验证实验闭环"))

        g1 = FoldCard("预测最佳条件")
        v1 = QVBoxLayout()
        row = QHBoxLayout()
        self.btn_find = QPushButton("寻找最佳条件")
        self.btn_find.setObjectName("primary")
        row.addWidget(self.btn_find)
        self.btn_constrained = QPushButton("⚠ 在可执行范围内重新寻优")
        self.btn_constrained.setEnabled(False)
        self.btn_constrained.setToolTip("当无约束最优条件无法配制时，在「补足液≥保留量、"
                                        "各因素加入体积≥最小移液量」约束下重新寻找")
        row.addWidget(self.btn_constrained)
        self.chip_opt = status_chip("未寻优", None)
        row.addWidget(self.chip_opt)
        row.addStretch(1)
        v1.addLayout(row)

        self.tbl_opt = QTableWidget()
        self.tbl_opt.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_opt.horizontalHeader().setStretchLastSection(True)
        self.tbl_opt.verticalHeader().setVisible(False)
        self.tbl_opt.verticalHeader().setDefaultSectionSize(32)
        v1.addWidget(self.tbl_opt)
        self.txt_opt_interp = QTextEdit()
        self.txt_opt_interp.setReadOnly(True)
        self.txt_opt_interp.setStyleSheet("background:#f8fafc;")
        self.txt_opt_interp.setMinimumHeight(96)
        self.txt_opt_interp.setMaximumHeight(170)
        v1.addWidget(self.txt_opt_interp)
        g1.set_body(v1)
        lay.addWidget(g1)

        g2 = FoldCard("验证实验（预测最优条件拿到实验室实际做一遍）")
        v2 = QVBoxLayout()
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("预测响应："))
        self.lbl_pred = QLabel("—")
        self.lbl_pred.setStyleSheet("font-weight:bold;")
        row2.addWidget(self.lbl_pred)
        row2.addWidget(QLabel("　实测响应："))
        self.sp_actual = QDoubleSpinBox()
        self.sp_actual.setDecimals(4)
        self.sp_actual.setRange(-1e12, 1e12)
        row2.addWidget(self.sp_actual)
        self.btn_validate = QPushButton("计算验证结果")
        row2.addWidget(self.btn_validate)
        self.chip_val = status_chip("", None)
        row2.addWidget(self.chip_val)
        row2.addStretch(1)
        v2.addLayout(row2)

        self.tbl_validations = QTableWidget()
        self.tbl_validations.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_validations.horizontalHeader().setStretchLastSection(True)
        self.tbl_validations.verticalHeader().setVisible(False)
        self.tbl_validations.verticalHeader().setDefaultSectionSize(32)
        self.tbl_validations.setMinimumHeight(110)
        v2.addWidget(self.tbl_validations)
        g2.set_body(v2)
        lay.addWidget(g2)
        lay.addStretch(1)
        self.lbl_next = tip_label("验证误差较小（如 ≤5%）即说明模型有实际参考价值；"
                                  "之后可在菜单「项目」里导出完整实验记录。")
        lay.addWidget(self.lbl_next)

        self.btn_find.clicked.connect(lambda: self.find(constrained=False))
        self.btn_constrained.clicked.connect(lambda: self.find(constrained=True))
        self.btn_validate.clicked.connect(self.validate)

    # ---------- 寻优 ----------
    def find(self, constrained: bool):
        m = self.mw.model
        if m is None:
            QMessageBox.information(self, "提示", "请先在第四步拟合模型")
            return
        try:
            opt = find_optimum(m, constrained=constrained)
        except Exception as e:   # noqa: BLE001
            QMessageBox.warning(self, "寻优失败", str(e))
            return
        if constrained:
            self.mw.optimum_constrained = opt
        else:
            self.mw.optimum = opt
        self._show_opt(opt, constrained)
        self.mw.ai_panel.refresh_stage(self.mw.current_stage())

    def _show_opt(self, opt: dict, constrained: bool):
        exp = self.mw.exp
        factors = exp.factor_list()
        title = "（可执行范围内）" if constrained else ""
        heads = ["因素", f"最优值{title}", "单位", "加入体积(μL)", "编码水平"]
        self.tbl_opt.clear()
        self.tbl_opt.setColumnCount(len(heads))
        self.tbl_opt.setHorizontalHeaderLabels(heads)
        self.tbl_opt.setRowCount(len(factors) + 1)
        for i, f in enumerate(factors):
            vol = ""
            if opt["breakdown"] and opt["breakdown"]["volumes"][i] is not None:
                vol = f"{opt['breakdown']['volumes'][i]:.2f}"
            vals = [f"{chr(65 + i)}：{f.short_label()}", f"{opt['actual'][i]:.4g}",
                    f.unit, vol, f"{opt['coded'][i]:.3f}"]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c:
                    it.setTextAlignment(Qt.AlignCenter)
                self.tbl_opt.setItem(i, c, it)
        water = opt["breakdown"]["water"] if opt["breakdown"] else None
        last = [f"{exp.system.filler_name}（补足）",
                f"{water:.2f}" if water is not None else "—", "μL", "", ""]
        for c, v in enumerate(last):
            it = QTableWidgetItem(v)
            if c:
                it.setTextAlignment(Qt.AlignCenter)
            self.tbl_opt.setItem(len(factors), c, it)

        if opt["feasible"]:
            self.chip_opt.setText(f"✓ 条件可执行 ｜ 预测{exp.response_name} = {opt['yhat']:.6g}")
            self.chip_opt.setStyleSheet(
                f"color:#166534;background:{OK_BG};border-radius:6px;padding:4px 10px;")
            self.btn_constrained.setEnabled(False)
        else:
            self.chip_opt.setText(f"⚠ 无法直接配制 ｜ 预测 = {opt['yhat']:.6g}")
            self.chip_opt.setStyleSheet(
                f"color:#991b1b;background:{BAD_BG};border-radius:6px;padding:4px 10px;")
            self.btn_constrained.setEnabled(not constrained)
        self.lbl_pred.setText(f"{opt['yhat']:.6g}")
        self.txt_opt_interp.setPlainText(interpret_optimum(exp, opt))
        self.mw.exp.save()

    # ---------- 验证 ----------
    def validate(self):
        opt = self.mw.optimum or self.mw.optimum_constrained
        if opt is None:
            QMessageBox.information(self, "提示", "请先点击「寻找最佳条件」")
            return
        actual = self.sp_actual.value()
        predicted = opt["yhat"]
        if abs(predicted) < 1e-12:
            QMessageBox.warning(self, "无法计算", "预测响应接近 0，相对误差无意义")
            return
        err = abs(actual - predicted) / abs(predicted) * 100
        from datetime import datetime
        from ..core.models import Validation
        v = Validation(predicted=predicted, actual=actual, error_pct=err,
                       time=datetime.now().strftime("%Y-%m-%d %H:%M"))
        self.mw.exp.validations.append(v)
        self.mw.exp.save()
        ok = err <= 10
        self.chip_val.setText(f"预测 {predicted:.6g} ｜ 实测 {actual:.6g} ｜ 相对误差 {err:.2f}%")
        self.chip_val.setStyleSheet(
            f"color:{'#166534' if ok else '#991b1b'};background:"
            f"{OK_BG if ok else BAD_BG};border-radius:6px;padding:4px 10px;")
        self._refresh_validations()
        self.append_interp(interpret_validation(predicted, actual, err))
        self.mw.ai_panel.refresh_stage(self.mw.current_stage())

    def append_interp(self, text: str):
        cur = self.txt_opt_interp.toPlainText()
        self.txt_opt_interp.setPlainText((cur + "\n\n【验证】" + text).strip())

    def _refresh_validations(self):
        vals = self.mw.exp.validations
        heads = ["时间", "预测值", "实测值", "相对误差", "备注"]
        self.tbl_validations.setRowCount(len(vals))
        self.tbl_validations.setColumnCount(len(heads))
        self.tbl_validations.setHorizontalHeaderLabels(heads)
        for i, v in enumerate(vals):
            row = [v.time, f"{v.predicted:.6g}", f"{v.actual:.6g}",
                   f"{v.error_pct:.2f}%", v.note]
            for c, x in enumerate(row):
                it = QTableWidgetItem(str(x))
                if c:
                    it.setTextAlignment(Qt.AlignCenter)
                self.tbl_validations.setItem(i, c, it)

    def refresh(self):
        self._refresh_validations()
        exp = self.mw.exp
        opt = self.mw.optimum or self.mw.optimum_constrained
        if opt is not None:
            self._show_opt(opt, opt is self.mw.optimum_constrained)
        else:
            self.chip_opt.setText("请先在第四步拟合模型，再点击「寻找最佳条件」")
            self.chip_opt.setStyleSheet(
                f"color:#92400e;background:{WARN_BG};border-radius:6px;padding:4px 10px;")
