"""工具对话框：摩尔浓度计算器 / 稀释计算。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QRadioButton, QTabWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import calculator as calc
from .widgets import section_title, tip_label


def _value_row(label: str, units: list, decimals: int = 6) -> tuple:
    """一行输入：标签 + 数值框 + 单位下拉。返回 (行控件, 数值框, 单位框)。"""
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(8)
    sp = QDoubleSpinBox()
    sp.setDecimals(decimals)
    sp.setRange(0, 1e12)
    sp.setMinimumWidth(150)
    unit = QComboBox()
    for name, _f in units:
        unit.addItem(name)
    h.addWidget(QLabel(label))
    h.addWidget(sp, 1)
    h.addWidget(unit)
    h.addStretch(1)
    return row, sp, unit


def _num(sp: QDoubleSpinBox):
    v = sp.value()
    return v if v > 0 else None      # 0 视为未填


class MolarityTab(QWidget):
    """c = m/(M·V)：知三求一。"""

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.setSpacing(10)
        v.addWidget(tip_label("公式：浓度 c = 质量 m ÷ (摩尔质量 M × 体积 V)。"
                              "选择要求哪一项，填好其余三项，点「计算」。"
                              "摩尔质量 M 请查试剂瓶标签或说明书。"))

        self.rb_conc = QRadioButton("求浓度 c")
        self.rb_mass = QRadioButton("求质量 m（配液时称多少）")
        self.rb_vol = QRadioButton("求体积 V")
        self.rb_conc.setChecked(True)
        radio_row = QHBoxLayout()
        for rb in (self.rb_conc, self.rb_mass, self.rb_vol):
            radio_row.addWidget(rb)
        radio_row.addStretch(1)
        v.addLayout(radio_row)

        form = QFormLayout()
        form.setSpacing(8)
        self.row_mass, self.sp_mass, self.u_mass = _value_row("质量 m =", calc.MASS_UNITS)
        self.row_mw, self.sp_mw, self.u_mw = _value_row("摩尔质量 M =", [("g/mol", 1.0)])
        self.row_vol, self.sp_vol, self.u_vol = _value_row("体积 V =", calc.VOL_UNITS)
        self.row_conc, self.sp_conc, self.u_conc = _value_row("浓度 c =", calc.CONC_UNITS)
        form.addRow(self.row_mass)
        form.addRow(self.row_mw)
        form.addRow(self.row_vol)
        form.addRow(self.row_conc)
        v.addLayout(form)

        self.btn = QPushButton("计 算")
        self.btn.setObjectName("primary")
        self.btn.clicked.connect(self.compute)
        self.result = QLabel("—")
        f = QFont()
        f.setPointSizeF(f.pointSizeF() + 2)
        f.setBold(True)
        self.result.setFont(f)
        self.result.setStyleSheet("color:#4338ca;")
        bottom = QHBoxLayout()
        bottom.addWidget(self.btn)
        bottom.addSpacing(16)
        bottom.addWidget(self.result, 1)
        v.addLayout(bottom)
        v.addStretch(1)

        for rb in (self.rb_conc, self.rb_mass, self.rb_vol):
            rb.toggled.connect(self._sync_targets)

    def _sync_targets(self):
        self.sp_conc.setEnabled(not self.rb_conc.isChecked())
        self.sp_mass.setEnabled(not self.rb_mass.isChecked())
        self.sp_vol.setEnabled(not self.rb_vol.isChecked())

    def compute(self):
        try:
            mass = _num(self.sp_mass)
            mw = _num(self.sp_mw)
            vol = _num(self.sp_vol) * calc.unit_factor(calc.VOL_UNITS, self.u_vol.currentText()) \
                if _num(self.sp_vol) else None
            conc = _num(self.sp_conc) * calc.unit_factor(calc.CONC_UNITS, self.u_conc.currentText()) \
                if _num(self.sp_conc) else None
            name, value, unit = calc.solve_molarity(mass=mass, mw=mw, volume=vol, conc=conc)
        except ValueError as e:
            self.result.setText(f"⚠ {e}")
            self.result.setStyleSheet("color:#b91c1c;")
            return
        # 结果换回所选单位并回填
        if name == "浓度":
            factor = calc.unit_factor(calc.CONC_UNITS, self.u_conc.currentText())
            self.sp_conc.setValue(value / factor)
            shown = f"浓度 = {value / factor:g} {self.u_conc.currentText()}"
        elif name == "质量":
            factor = calc.unit_factor(calc.MASS_UNITS, self.u_mass.currentText())
            self.sp_mass.setValue(value / factor)
            shown = f"质量 = {value / factor:g} {self.u_mass.currentText()}"
        else:
            factor = calc.unit_factor(calc.VOL_UNITS, self.u_vol.currentText())
            self.sp_vol.setValue(value / factor)
            shown = f"体积 = {value / factor:g} {self.u_vol.currentText()}"
        self.result.setText("✓ " + shown)
        self.result.setStyleSheet("color:#15803d;")


class DilutionTab(QWidget):
    """C1V1 = C2V2：知三求一 + 配液提示。"""

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.setSpacing(10)
        v.addWidget(tip_label("公式：C1·V1 = C2·V2（浓溶液稀释）。选择要求哪一项，填好其余三项，"
                              "点「计算」。结果还会给出移液操作提示。"))

        self.rb_v1 = QRadioButton("求取液体积 V1（要吸多少储备液）")
        self.rb_v2 = QRadioButton("求最终体积 V2（定容到多少）")
        self.rb_c2 = QRadioButton("求可达到的浓度 C2")
        self.rb_c1 = QRadioButton("求所需储备液浓度 C1")
        self.rb_v1.setChecked(True)
        radio_row = QHBoxLayout()
        for rb in (self.rb_v1, self.rb_v2, self.rb_c2, self.rb_c1):
            radio_row.addWidget(rb)
        radio_row.addStretch(1)
        v.addLayout(radio_row)

        form = QFormLayout()
        form.setSpacing(8)
        self.row_c1, self.sp_c1, self.u_c1 = _value_row("初始浓度 C1 =", calc.CONC_UNITS)
        self.row_v1, self.sp_v1, self.u_v1 = _value_row("储备液体积 V1 =", calc.VOL_UNITS)
        self.row_c2, self.sp_c2, self.u_c2 = _value_row("目标浓度 C2 =", calc.CONC_UNITS)
        self.row_v2, self.sp_v2, self.u_v2 = _value_row("最终体积 V2 =", calc.VOL_UNITS)
        form.addRow(self.row_c1)
        form.addRow(self.row_v1)
        form.addRow(self.row_c2)
        form.addRow(self.row_v2)
        v.addLayout(form)

        self.btn = QPushButton("计 算")
        self.btn.setObjectName("primary")
        self.btn.clicked.connect(self.compute)
        self.result = QLabel("—")
        f = QFont()
        f.setPointSizeF(f.pointSizeF() + 2)
        f.setBold(True)
        self.result.setFont(f)
        self.result.setStyleSheet("color:#4338ca;")
        self.hint = tip_label("")
        self.hint.setWordWrap(True)
        bottom = QHBoxLayout()
        bottom.addWidget(self.btn)
        bottom.addSpacing(16)
        bottom.addWidget(self.result, 1)
        v.addLayout(bottom)
        v.addWidget(self.hint)
        v.addStretch(1)

        for rb in (self.rb_v1, self.rb_v2, self.rb_c2, self.rb_c1):
            rb.toggled.connect(self._sync_targets)

    def _sync_targets(self):
        self.sp_v1.setEnabled(not self.rb_v1.isChecked())
        self.sp_v2.setEnabled(not self.rb_v2.isChecked())
        self.sp_c2.setEnabled(not self.rb_c2.isChecked())
        self.sp_c1.setEnabled(not self.rb_c1.isChecked())

    def _conc(self, sp, unit_box):
        v = _num(sp)
        return v * calc.unit_factor(calc.CONC_UNITS, unit_box.currentText()) if v else None

    def _vol(self, sp, unit_box):
        v = _num(sp)
        return v * calc.unit_factor(calc.VOL_UNITS, unit_box.currentText()) if v else None

    def compute(self):
        try:
            c1, v1 = self._conc(self.sp_c1, self.u_c1), self._vol(self.sp_v1, self.u_v1)
            c2, v2 = self._conc(self.sp_c2, self.u_c2), self._vol(self.sp_v2, self.u_v2)
            name, value = calc.solve_dilution(c1=c1, v1=v1, c2=c2, v2=v2)
        except ValueError as e:
            self.result.setText(f"⚠ {e}")
            self.result.setStyleSheet("color:#b91c1c;")
            self.hint.setText("")
            return
        shown = f"{name} = {value:g}"
        if name.startswith("取液体积"):
            factor = calc.unit_factor(calc.VOL_UNITS, self.u_v1.currentText())
            self.sp_v1.setValue(value / factor)
            shown = f"V1 = {value / factor:g} {self.u_v1.currentText()}"
        elif name.startswith("最终体积"):
            factor = calc.unit_factor(calc.VOL_UNITS, self.u_v2.currentText())
            self.sp_v2.setValue(value / factor)
            shown = f"V2 = {value / factor:g} {self.u_v2.currentText()}"
        elif name.startswith("目标浓度"):
            factor = calc.unit_factor(calc.CONC_UNITS, self.u_c2.currentText())
            self.sp_c2.setValue(value / factor)
            shown = f"C2 = {value / factor:g} {self.u_c2.currentText()}"
        else:
            factor = calc.unit_factor(calc.CONC_UNITS, self.u_c1.currentText())
            self.sp_c1.setValue(value / factor)
            shown = f"C1 = {value / factor:g} {self.u_c1.currentText()}"
        self.result.setText("✓ " + shown)
        self.result.setStyleSheet("color:#15803d;")
        # 配液操作提示
        try:
            c1v = self._conc(self.sp_c1, self.u_c1)
            v1v = self._vol(self.sp_v1, self.u_v1)
            v2v = self._vol(self.sp_v2, self.u_v2)
            if c1v and v1v and v2v:
                dil = c1v / self._conc(self.sp_c2, self.u_c2) \
                    if self._conc(self.sp_c2, self.u_c2) else None
                fu = self.u_v2.currentText()   # 提示统一用“定容体积”的单位更好读
                add = v2v - v1v
                txt = (f"操作：吸取 V1 = {v1v / calc.unit_factor(calc.VOL_UNITS, fu):g} {fu} "
                       f"储备液，加稀释液至总体积 "
                       f"{v2v / calc.unit_factor(calc.VOL_UNITS, fu):g} {fu}"
                       f"（即再补 {add / calc.unit_factor(calc.VOL_UNITS, fu):g} {fu}）")
                if dil:
                    txt += f"；稀释倍数 = C1/C2 = {dil:g} 倍"
                self.hint.setText(txt)
        except Exception:   # noqa: BLE001
            pass


class CalculatorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("摩尔浓度 / 稀释 计算器")
        self.resize(560, 430)
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(10)
        tabs = QTabWidget()
        tabs.addTab(MolarityTab(), "摩尔浓度 c = m/(M·V)")
        tabs.addTab(DilutionTab(), "稀释 C1V1 = C2V2")
        v.addWidget(tabs, 1)
