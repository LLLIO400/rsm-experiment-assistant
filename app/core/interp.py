"""内置解读：把软件算出的统计量翻译成人话（确定性模板，不依赖 AI、不发明统计）。"""
from __future__ import annotations

from .models import Experiment
from .stats import RSMModel

P_CUT = 0.05


def interpret_model(exp: Experiment, m: RSMModel) -> str:
    lines = []
    # 模型整体
    if m.p_model < P_CUT:
        lines.append(f"✔ 模型整体显著（P = {m.p_model:.4f} < 0.05），说明所选二次模型"
                     f"能够解释响应值的变化。")
    else:
        lines.append(f"⚠ 模型整体不显著（P = {m.p_model:.4f} ≥ 0.05）。当前因素范围或水平"
                     f"设置可能不合适，建议检查单因素趋势后重新划定范围。")

    # R² 系列
    lines.append(f"模型解释了响应值变化的 {m.r2 * 100:.1f}%（R² = {m.r2:.3f}）；"
                 f"调整 R² = {m.adj_r2:.3f}，预测 R² = {m.pred_r2:.3f}。")
    if m.adj_r2 - m.pred_r2 > 0.2:
        lines.append(f"⚠ 调整 R² 与预测 R² 相差 {m.adj_r2 - m.pred_r2:.2f}（> 0.2）："
                     f"模型对已有数据拟合得好、但对新条件预测偏弱（过拟合迹象），"
                     f"用预测值时要多留余量。")
    if m.adeq < 4:
        lines.append(f"⚠ 信噪比（Adequate Precision）= {m.adeq:.2f}（< 4）：实验误差快要盖过"
                     f"因素效应了，先别急着用模型找最优——建议改进操作重复性或拉大水平间距。")
    else:
        lines.append(f"信噪比（Adequate Precision）= {m.adeq:.1f}（> 4）：因素效应明显大于"
                     f"实验误差，可以放心用这个模型去找最优条件。")

    # 失拟
    if m.lof_p is not None:
        if m.lof_p > P_CUT:
            lines.append(f"✔ 失拟检验 P = {m.lof_p:.3f} > 0.05，失拟不显著，"
                         f"说明模型形式与数据吻合得不错。")
        else:
            lines.append(f"⚠ 失拟检验 P = {m.lof_p:.3f} ≤ 0.05，失拟显著："
                         f"二次模型可能没有完整描述真实关系（可考虑变换响应值或扩大实验）。")

    # 各项显著性
    sig_terms = [t for t in m.terms if t["sig"]]
    if sig_terms:
        ranked = sorted(m.terms, key=lambda t: t["ss"], reverse=True)
        order = " > ".join(t["label"] for t in ranked[:5] if t["p"] < 0.2)
        parts = []
        for t in sig_terms:
            parts.append(f"{t['label']}（P = {t['p']:.3f}）")
        lines.append("显著项：" + "、".join(parts) + "。")
        if order:
            lines.append(f"按对响应值的影响大小排序（前几项）：{order}。")
        inter_sig = [t for t in sig_terms if "×" in t["desc"]]
        if inter_sig:
            d = inter_sig[0]["desc"].replace("（交互项）", "")
            lines.append(f"存在显著交互作用（如 {d}）：这些因素的最佳取值会互相影响，"
                         f"不能只根据单因素实验分别判断各自的最佳条件——这正是做 BBD 的意义。")
        sq_sig = [t for t in sig_terms if "二次项" in t["desc"]]
        if sq_sig:
            names = "、".join(t["desc"].replace("（二次项）", "") for t in sq_sig)
            lines.append(f"{names} 的二次项显著，说明响应值在该因素范围内存在峰值（或谷值），"
                         f" optimum 落在因素范围内部而不是边界上，值得继续找最优条件。")
    else:
        lines.append("没有检测到显著项（所有 P ≥ 0.05）。可能因素范围太窄、实验误差太大，"
                     "或真正起作用的因素不在当前因素中。")

    lines.append("提醒：以上统计量由 statsmodels/scipy 计算，AI 只负责解释；"
                 "响应面图好看 ≠ 模型可靠，最终要以验证实验为准。")
    return "\n\n".join(lines)


def interpret_optimum(exp: Experiment, opt: dict) -> str:
    factors = exp.factor_list()
    obj_txt = {"max": "最大化", "min": "最小化"}.get(exp.objective, "逼近目标值")
    lines = [f"优化目标：{obj_txt}{exp.response_name}。"]
    parts = "、".join(
        f"{chr(65 + i)}（{f.short_label()}）= {v:.3g} {f.unit}".strip()
        for i, (f, v) in enumerate(zip(factors, opt["actual"])))
    lines.append(f"预测最佳条件：{parts}；预测{exp.response_name} = {opt['yhat']:.6g}。")
    if opt["feasible"]:
        lines.append("✔ 该条件通过配液可行性检查，可以直接拿到实验室去配。"
                     "请按第五步做验证实验，用实测值检验模型预测。")
    else:
        lines.append("⚠ " + opt["note"] + " 建议在可执行范围内重新寻找最优条件"
                     "（软件会自动在配液约束下重新寻优）。")
    return "\n\n".join(lines)


def interpret_validation(predicted: float, actual: float, err_pct: float) -> str:
    if err_pct <= 5:
        judge = "误差很小，模型预测与实测吻合良好，模型具有实际参考价值。"
    elif err_pct <= 10:
        judge = "误差在可接受范围内，模型可用于指导该体系，但注意预测只是近似。"
    else:
        judge = ("误差偏大，建议检查：验证实验操作是否与建模实验一致、模型是否过拟合、"
                 "最优条件是否落在实验数据覆盖较好的区域。")
    return (f"预测值 {predicted:.6g}，实测值 {actual:.6g}，相对误差 {err_pct:.2f}%。{judge}")
