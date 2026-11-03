"""导出实验记录（Markdown）：实验信息 → 设计与结果 → ANOVA → 最优 → 验证。"""
from __future__ import annotations

from .excelio import results_dataframe
from .stats import RSMModel


def experiment_record_markdown(exp, model: RSMModel | None, optimum: dict | None) -> str:
    L = []
    L.append(f"# 实验记录：{exp.name}")
    L.append(f"\n- 创建时间：{exp.created}　最后修改：{exp.modified}")
    obj = {"max": "最大化", "min": "最小化"}.get(exp.objective, f"目标值 {exp.target_value}")
    unit = f"（{exp.response_unit}）" if exp.response_unit else ""
    L.append(f"- 响应指标：{exp.response_name}{unit}，优化目标：{obj}")
    L.append(f"- 设计方法：Box-Behnken Design（BBD），{len(exp.runs)} 个实验"
             f"（含 {exp.n_center} 个中心点），随机化运行顺序")

    L.append("\n## 因素与水平\n")
    L.append("| 因素 | 名称 | 单位 | 低(-1) | 中心(0) | 高(+1) | 配液方式 |")
    L.append("|---|---|---|---|---|---|---|")
    for i, f in enumerate(exp.factor_list()):
        mode = {"none": "—", "direct": "按体积直接加入",
                "stock": f"母液换算({f.stock_conc:g})"}.get(f.volume_mode, "—")
        L.append(f"| {chr(65 + i)} | {f.name} | {f.unit} | {f.low:g} | {f.center:g} | "
                 f"{f.high:g} | {mode} |")

    if exp.system.enabled:
        L.append("\n## 反应体系\n")
        L.append(f"总体系 {exp.system.total_volume:g} μL；"
                 + "；".join(f"{c.name} {c.volume:g} μL" for c in exp.system.fixed_list())
                 + f"；其余由 {exp.system.filler_name} 补足（最小移液体积 "
                   f"{exp.system.min_pipette:g} μL）。")

    if exp.has_design():
        L.append("\n## 实验方案与结果\n")
        df = results_dataframe(exp)
        cols = list(df.columns)
        L.append("| " + " | ".join(str(c) for c in cols) + " |")
        L.append("|" + "---|" * len(cols))
        for _, row in df.iterrows():
            L.append("| " + " | ".join("—" if pd_isna(v) else str(v) for v in row.tolist())
                     + " |")

    if model is not None:
        L.append("\n## 模型分析（ANOVA 摘要）\n")
        for a, b, c in model.summary_rows():
            L.append(f"- {a}：**{b}**（{c}）")
        L.append("\n| 项 | 系数(编码) | F | P | 显著性 |")
        L.append("|---|---|---|---|---|")
        for t in model.terms:
            L.append(f"| {t['label']}（{t['desc']}） | {t['coef']:.4g} | {t['f']:.2f} | "
                     f"{t['p']:.4f} | {'显著' if t['sig'] else '不显著'} |")
        from .interp import interpret_model
        L.append("\n## 结果解读\n\n" + interpret_model(exp, model))

    if optimum is not None:
        L.append("\n## 预测最优条件\n")
        parts = "、".join(f"{chr(65 + i)} = {v:.4g} {f.unit}".strip()
                          for i, (f, v) in enumerate(zip(exp.factor_list(),
                                                         optimum["actual"])))
        L.append(f"- {parts}")
        L.append(f"- 预测{exp.response_name}：**{optimum['yhat']:.6g}**")
        L.append(f"- 配液可行性：{'✓ 可执行' if optimum['feasible'] else '⚠ ' + optimum['note']}")

    if exp.validations:
        L.append("\n## 验证实验\n")
        L.append("| 时间 | 预测值 | 实测值 | 相对误差 |")
        L.append("|---|---|---|---|")
        for v in exp.validations:
            L.append(f"| {v.time} | {v.predicted:.6g} | {v.actual:.6g} | {v.error_pct:.2f}% |")
        L.append("\n相对误差 = |实测 − 预测| / 预测 × 100%。")

    L.append("\n---\n*统计计算由 statsmodels/scipy 完成；本记录由「我的 RSM 实验助手」生成。*")
    return "\n".join(L)


def pd_isna(v) -> bool:
    try:
        import pandas as pd
        return bool(pd.isna(v))
    except Exception:   # noqa: BLE001
        return v is None
