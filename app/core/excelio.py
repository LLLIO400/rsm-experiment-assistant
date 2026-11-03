"""Excel 导入 / 导出（pandas + openpyxl）。"""
from __future__ import annotations

import io

import pandas as pd

from .models import Experiment
from .volume import prep_table


def design_dataframe(exp: Experiment, with_prep: bool = True) -> pd.DataFrame:
    """实验方案表（按随机运行顺序）。with_prep=True 时附带配液体积列。"""
    factors = exp.factor_list()
    prep = {p["std"]: p for p in prep_table(exp)}
    rows = []
    for r in exp.runs_in_order():
        row = {"运行序": r.order, "标准序": r.std}
        for i, f in enumerate(factors):
            row[f"{f.short_label()}({f.unit})" if f.unit else f.short_label()] = r.actual[i]
        if with_prep and exp.system.enabled:
            p = prep[r.std]
            for i, f in enumerate(factors):
                if p["volumes"][i] is not None:
                    row[f"{f.short_label()}体积(μL)"] = round(p["volumes"][i], 2)
            row[f"{exp.system.filler_name}体积(μL)"] = (
                round(p["water"], 2) if p["water"] is not None else None)
            row["配液可行"] = "✓" if p["ok"] else "⚠"
        row[f"{exp.response_name}"] = None
        rows.append(row)
    return pd.DataFrame(rows)


def export_design_excel(exp: Experiment, path: str) -> str:
    df = design_dataframe(exp, with_prep=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="实验方案")
        ws = writer.sheets["实验方案"]
        ws.insert_rows(1)
        ws.cell(row=1, column=1, value=f"实验：{exp.name} ｜ BBD 设计 ｜ "
                                       f"响应值：{exp.response_name}（请只在最后一列填实测值）")
    return path


def results_dataframe(exp: Experiment) -> pd.DataFrame:
    factors = exp.factor_list()
    rows = []
    for r in exp.runs_in_order():
        row = {"运行序": r.order, "标准序": r.std}
        for i, f in enumerate(factors):
            row[f.short_label()] = r.actual[i]
        row[exp.response_name] = r.response
        rows.append(row)
    return pd.DataFrame(rows)


def export_results_excel(exp: Experiment, path: str) -> str:
    results_dataframe(exp).to_excel(path, index=False, sheet_name="结果")
    return path


def import_results(exp: Experiment, df: pd.DataFrame) -> int:
    """从 DataFrame 中按"运行序"匹配填入实测响应值，返回更新条数。
    兼容：有"运行序"列则按它匹配；否则要求列结构与导出模板完全一致按行序。"""
    factors = exp.factor_list()
    df.columns = [str(c).strip() for c in df.columns]
    resp_col = None
    for c in df.columns:
        if exp.response_name in c:
            resp_col = c
            break
    if resp_col is None:
        raise ValueError(f"找不到响应值列「{exp.response_name}」")

    run_col = None
    for cand in ("运行序", "运行顺序", "实验号"):
        if cand in df.columns:
            run_col = cand
            break

    updated = 0
    run_map = {r.order: r for r in exp.run_list()}
    if run_col is not None:
        for _, row in df.iterrows():
            try:
                key = int(float(row[run_col]))
            except (TypeError, ValueError):
                continue
            val = row[resp_col]
            if pd.isna(val) or key not in run_map:
                continue
            run_map[key].response = float(val)
            updated += 1
    else:
        ordered = exp.runs_in_order()
        vals = pd.to_numeric(df[resp_col], errors="coerce")
        for r, val in zip(ordered, vals):
            if pd.notna(val):
                r.response = float(val)
                updated += 1
    if updated:
        exp.touch()
    return updated


def read_excel_any(source) -> pd.DataFrame:
    """source: 文件路径 或 原始字节。"""
    if isinstance(source, (bytes, bytearray)):
        return pd.read_excel(io.BytesIO(source), engine="openpyxl")
    return pd.read_excel(source, engine="openpyxl")
