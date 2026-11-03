"""第三步：输入实验结果 —— 按运行序填写，支持 Excel 导入与剪贴板粘贴。"""
from __future__ import annotations

import io

import pandas as pd
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from ..core import excelio
from .widgets import page_header, status_chip, tip_label


class PageResults(QWidget):
    changed = Signal()

    def __init__(self, mw):
        super().__init__()
        self.mw = mw
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 22)
        lay.setSpacing(12)

        top = QHBoxLayout()
        top.addWidget(page_header("③ 输入实验结果", "按运行序填写实测值 · 支持 Excel 导入与剪贴板粘贴"), 1)
        self.chip = status_chip("", None)
        top.addWidget(self.chip)
        lay.addLayout(top)
        lay.addWidget(tip_label(
            "按「运行序」把每次实验的实测响应值填进最后一列（支持小数/整数）。"
            "也可以先导出模板在 Excel 里填，再导入；或直接从 Excel 复制区域后点「从剪贴板粘贴」。"))

        self.tbl = QTableWidget()
        self.tbl.setAlternatingRowColors(True)
        self.tbl.itemChanged.connect(self._on_item_changed)
        lay.addWidget(self.tbl, 1)

        bottom = QHBoxLayout()
        self.btn_paste = QPushButton("从剪贴板粘贴")
        self.btn_import = QPushButton("导入 Excel 文件")
        self.btn_import.setObjectName("primary")
        self.btn_template = QPushButton("导出结果模板 Excel")
        self.btn_clear = QPushButton("清空已填结果")
        bottom.addWidget(self.btn_paste)
        bottom.addWidget(self.btn_import)
        bottom.addWidget(self.btn_template)
        bottom.addWidget(self.btn_clear)
        bottom.addStretch(1)
        self.lbl_next = tip_label("")
        bottom.addWidget(self.lbl_next)
        lay.addLayout(bottom)

        self.btn_paste.clicked.connect(self.paste_clipboard)
        self.btn_import.clicked.connect(self.import_excel)
        self.btn_template.clicked.connect(self.export_template)
        self.btn_clear.clicked.connect(self.clear_results)

    # ---------- 展示 ----------
    def refresh(self):
        exp = self.mw.exp
        if not exp.has_design():
            self.tbl.setRowCount(0)
            self.chip.setText("尚未生成设计")
            return
        factors = exp.factor_list()
        headers = ["运行序", "标准序"] + [f.short_label() for f in factors] + [exp.response_name]
        runs = exp.runs_in_order()
        self._loading = True
        self.tbl.clear()
        self.tbl.setRowCount(len(runs))
        self.tbl.setColumnCount(len(headers))
        self.tbl.setHorizontalHeaderLabels(headers)
        self.tbl.horizontalHeader().resizeSection(0, 60)
        for r, run in enumerate(runs):
            vals = [run.order, run.std] + [f"{v:g}" for v in run.actual]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                it.setTextAlignment(Qt.AlignCenter)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                it.setForeground(Qt.gray)
                self.tbl.setItem(r, c, it)
            resp = "" if run.response is None else f"{run.response:g}"
            it = QTableWidgetItem(resp)
            it.setTextAlignment(Qt.AlignCenter)
            self.tbl.setItem(r, len(vals), it)
        self._loading = False
        self._update_chip()
        self._update_next()

    def _update_chip(self):
        exp = self.mw.exp
        n, total = exp.n_done(), len(exp.runs)
        if n == total:
            self.chip.setText(f"✓ 已填 {n}/{total}，可以做模型分析了")
            self.chip.setStyleSheet(
                "color:#166534;background:#dcfce7;border-radius:6px;padding:4px 10px;")
        else:
            self.chip.setText(f"已填 {n}/{total}")
            self.chip.setStyleSheet(
                "color:#92400e;background:#fef3c7;border-radius:6px;padding:4px 10px;")

    def _update_next(self):
        self.lbl_next.setText("全部填完后 → 第四步：分析模型。" if self.mw.exp.n_done()
                              else "提示：先在第二步生成设计。")

    # ---------- 编辑 ----------
    def _on_item_changed(self, item):
        if getattr(self, "_loading", False):
            return
        if item.column() != self.tbl.columnCount() - 1:
            return
        exp = self.mw.exp
        runs = exp.runs_in_order()
        r = item.row()
        if r >= len(runs):
            return
        txt = item.text().strip()
        run = runs[r]
        if not txt:
            run.response = None
        else:
            try:
                run.response = float(txt.replace(",", ""))
            except ValueError:
                QMessageBox.warning(self, "格式错误", f"「{txt}」不是数字，请重新输入")
                self._loading = True
                item.setText("")
                self._loading = False
                return
        exp.touch()
        exp.save()
        self._update_chip()

    def _apply_df(self, df: pd.DataFrame, title: str):
        try:
            n = excelio.import_results(self.mw.exp, df)
        except ValueError as e:
            QMessageBox.warning(self, title, str(e))
            return
        self.mw.exp.save()
        self.refresh()
        self.changed.emit()
        QMessageBox.information(self, title, f"已导入 {n} 个响应值")

    def paste_clipboard(self):
        text = QApplication.clipboard().text()
        if not text.strip():
            QMessageBox.information(self, "提示", "剪贴板是空的：请先在 Excel 里复制包含"
                                                 "「运行序」和响应值列的区域")
            return
        try:
            df = pd.read_csv(io.StringIO(text), sep="\t")
        except Exception as e:   # noqa: BLE001
            QMessageBox.warning(self, "粘贴失败", f"无法解析剪贴板内容：{e}")
            return
        self._apply_df(df, "从剪贴板导入")

    def import_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入结果", "", "Excel 文件 (*.xlsx *.xls)")
        if not path:
            return
        try:
            df = excelio.read_excel_any(path)
        except Exception as e:   # noqa: BLE001
            QMessageBox.warning(self, "导入失败", f"无法读取文件：{e}")
            return
        self._apply_df(df, "导入 Excel")

    def export_template(self):
        exp = self.mw.exp
        if not exp.has_design():
            QMessageBox.information(self, "提示", "请先生成设计")
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出结果模板",
                                              f"{exp.name}_结果模板.xlsx", "Excel 文件 (*.xlsx)")
        if path:
            excelio.export_results_excel(exp, path)
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def clear_results(self):
        if QMessageBox.question(self, "确认", "清空所有已填写的响应值？") != QMessageBox.Yes:
            return
        for r in self.mw.exp.run_list():
            r.response = None
        self.mw.exp.save()
        self.refresh()
