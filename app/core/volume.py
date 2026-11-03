"""配液相关：把设计矩阵换算成实际配液表（各因素加入体积 + 补足液体积）。"""
from __future__ import annotations

from .models import Experiment


def prep_table(exp: Experiment) -> list:
    """返回每个 run 的配液信息：
    [{'std','order','actual', 'volumes', 'water', 'ok', 'issues'}]
    未启用体系检查时 volumes 全为 None、ok=True。
    """
    sysu = exp.system
    out = []
    for r in exp.run_list():
        if sysu.enabled:
            bd = exp.volume_breakdown(r.actual)
            vols, water, ok, issues = bd["volumes"], bd["water"], bd["ok"], bd["issues"]
        else:
            vols, water, ok, issues = [None] * len(r.actual), None, True, []
        out.append({
            "std": r.std, "order": r.order, "actual": list(r.actual),
            "volumes": vols, "water": water, "ok": ok, "issues": issues,
        })
    return out


def stock_requirements(exp: Experiment) -> list:
    """整个设计所需的最大母液用量（用于检查母液是否够用）。
    返回 [(因素名, 母液名, 最大用量μL)]；未用母液换算的因素不出现。"""
    rows = prep_table(exp)
    factors = exp.factor_list()
    need = {}
    for f_idx, f in enumerate(factors):
        if f.volume_mode == "stock" and f.stock_conc:
            used = [row["volumes"][f_idx] for row in rows if row["volumes"][f_idx] is not None]
            if used:
                label = f.stock_label or f"{f.short_label()}母液"
                need[label] = max(need.get(label, 0.0), max(used))
    return [(k, v) for k, v in need.items()]
