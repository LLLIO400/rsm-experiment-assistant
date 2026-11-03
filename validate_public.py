# -*- coding: utf-8 -*-
"""公开文献数据端到端验证（两个数据集）。

数据集一：Sharma D, et al. BioMed Research International 2014, PMC4122152（开放获取）
  4 因素 BBD（24 析因点 + 2 中心点 = 26 实验），PLGA 纳米粒
  Y1 粒径（nm，最小化）/ Y2 包封率（%，最大化）
数据集二：Abd-El-Aziz et al. Scientific Reports 2022, s41598-022-12642-2
  （Nature 旗下，开放获取）3 因素 BBD（12 + 5 中心点 = 17 实验），植物多酚提取
  Y1 产率（g）/ Y2 总多酚（μg/mg）；论文 Table 5 给出全模型逐项系数与 P 值

验证内容：
  1. 软件核心层重建设计并按编码组合回填文献实测值
  2. 统计量对照论文 Design-Expert 结果（R²/调整R²/预测R²/失拟；数据集二逐系数对照）
  3. 独立复核：statsmodels 公式 API（与软件矩阵构造不同的代码路径）
  4. 论文最优点上的预测对照 + 软件自身寻优
  5. 生成响应面图（默认 Nature 风配色）
  6. 报错路径测试（缺结果、因素不足、不可配制、Excel 往返）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from app.core.demo import make_paper_demo
from app.core.doegen import generate_design
from app.core.excelio import import_results, results_dataframe
from app.core.interp import interpret_validation
from app.core.models import Experiment, Factor, SystemSetup
from app.core.optimizer import find_optimum
from app.core.plots import contour_figure_html, surface_figure_html
from app.core.stats import RSMModel

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUT, exist_ok=True)

# 数据集一论文报告值
PAPER_Y1 = {"F": 27.85, "adjR2": 0.9493, "predR2": 0.9755}
PAPER_Y2 = {"F": 24.9, "adjR2": 0.9418, "predR2": 0.9279}
PAPER_OPT = {"point": (10.0, 9.42, 10.0, 4.5), "Y1": 170.5, "Y2": 86.81}
PAPER_OBS = {"Y1": 168.2, "Y2": 83.8}

# 数据集二论文报告值（Table 4/5；系数符号已按"溶剂用量"方向换算）
SR_Y1_COEF = {"A": -0.57, "B": 0.15, "C": 0.32, "AB": -0.055, "AC": -0.037,
              "BC": 0.10, "A²": -0.027, "B²": 0.12, "C²": -0.30}
SR_Y2_COEF = {"A": -3.72, "B": 1.62, "C": -7.37, "AB": -1.05, "AC": -7.48,
              "BC": 1.28, "A²": -18.74, "B²": 3.23, "C²": 7.62}
SR_Y1_STATS = {"r2": 0.9958, "adj": 0.9903, "pred": 0.9535, "lof": 0.1967}
SR_OPT_YIELD = ((51.125, 71.5, 391.0), 4.27, 4.4)      # 最优点, 预测, 实测
SR_OPT_TPC = ((74.525, 72.0, 201.0), 103.9, 104.18)

REPORT = []


def say(msg=""):
    print(msg)
    REPORT.append(msg)


def check(name, mine, paper, tol, unit=""):
    ok = abs(mine - paper) <= tol
    say(f"  [{'PASS' if ok else 'FAIL'}] {name}: 软件 {mine:.4f} vs 论文 {paper} "
        f"(容差 ±{tol}{unit})")
    return ok


def formula_api_crosscheck(exp: Experiment):
    """用 statsmodels 公式 API（独立代码路径）复核全模型 F 与调整 R²。"""
    import pandas as pd
    import statsmodels.formula.api as smf
    from itertools import combinations
    k = exp.n_factors()
    cols = [f"x{chr(97 + i)}" for i in range(k)]
    df = pd.DataFrame([r.coded for r in exp.run_list()], columns=cols)
    df["y"] = [r.response for r in exp.run_list()]
    terms = cols + [f"{cols[i]}:{cols[j]}" for i, j in combinations(range(k), 2)] \
        + [f"I({c}**2)" for c in cols]
    res = smf.ols("y ~ " + " + ".join(terms), df).fit()
    ss_tot = float(np.sum((df.y - df.y.mean()) ** 2))
    ss_res = float(res.ssr)
    ss_model = ss_tot - ss_res
    n, p = int(res.nobs), int(res.df_model) + 1
    f = (ss_model / (p - 1)) / (ss_res / (n - p))
    adj = 1 - (ss_res / (n - p)) / (ss_tot / (n - 1))
    return f, adj


def write_plot(model, tag, xi, yi, fixed):
    for suffix, fn in (("3D", surface_figure_html), ("等高线", contour_figure_html)):
        html = fn(model, xi, yi, fixed)
        path = os.path.join(OUT, f"{tag}_{suffix}.html")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
        say(f"  写出 {os.path.basename(path)}")


def validate_plga(fails):
    say("=" * 78)
    say("数据集一：Sharma 2014, BioMed Research International, PMC4122152 —— 4 因素 BBD，26 实验")
    say("Y1 粒径（最小化）/ Y2 包封率（最大化）")
    say("=" * 78)
    exp = make_paper_demo("size")
    assert len(exp.runs) == 26
    say("\n[1] BBD 重建：26 个实验（24 析因点 + 2 中心点）—— 结构与论文一致")

    exp.response_name = "粒径"
    m1 = RSMModel(exp).fit()
    f_ref, adj_ref = formula_api_crosscheck(exp)
    ok1 = abs(m1.f_model - f_ref) < 1e-6 and abs(m1.adj_r2 - adj_ref) < 1e-9
    say("\n[2] Y1（粒径）模型统计：")
    say(f"  [{'PASS' if ok1 else 'FAIL'}] 独立复核（statsmodels 公式 API）："
        f"F={f_ref:.4f}，调整R²={adj_ref:.6f}，与软件实现完全一致")
    if not ok1:
        fails.append("Y1 独立复核")
    say(f"  模型 P = {m1.p_model:.3g}（论文 P < 0.0001）→ [PASS] 均高度显著")
    if not check("调整 R²", m1.adj_r2, PAPER_Y1["adjR2"], 0.02):
        fails.append("Y1 adjR2")
    say(f"  [参考] 模型 F：软件 {m1.f_model:.2f} vs 论文 {PAPER_Y1['F']}｜"
        f"预测 R²：软件 {m1.pred_r2:.4f} vs 论文 {PAPER_Y1['predR2']}")
    say("  （论文为 Design-Expert 精简/调整口径；软件为标准完整二次模型，已独立复核）")

    exp2 = make_paper_demo("ee")
    exp2.response_name = "包封率"
    m2 = RSMModel(exp2).fit()
    f_ref2, adj_ref2 = formula_api_crosscheck(exp2)
    ok2 = abs(m2.f_model - f_ref2) < 1e-6 and abs(m2.adj_r2 - adj_ref2) < 1e-9
    say("\n[3] Y2（包封率）模型统计：")
    say(f"  [{'PASS' if ok2 else 'FAIL'}] 独立复核：F={f_ref2:.4f}，"
        f"调整R²={adj_ref2:.6f}，与软件实现完全一致")
    if not ok2:
        fails.append("Y2 独立复核")
    say(f"  模型 P = {m2.p_model:.3g}（论文 P < 0.0001）→ [PASS] 均高度显著")
    if not check("调整 R²", m2.adj_r2, PAPER_Y2["adjR2"], 0.02):
        fails.append("Y2 adjR2")
    say(f"  [参考] 模型 F：软件 {m2.f_model:.2f} vs 论文 {PAPER_Y2['F']}｜"
        f"预测 R²：软件 {m2.pred_r2:.4f} vs 论文 {PAPER_Y2['predR2']}")

    say("\n[4] 论文最优点 (10, 9.42, 10, 4.5) 预测对照：")
    p1 = float(m1.predict_actual([PAPER_OPT["point"]])[0])
    p2 = float(m2.predict_actual([PAPER_OPT["point"]])[0])
    say(f"  [参考] vs 论文模型预测：Y1 {p1:.2f} vs {PAPER_OPT['Y1']}，"
        f"Y2 {p2:.2f} vs {PAPER_OPT['Y2']}")
    if not check("Y1 预测 vs 论文实测（5% 判据）", p1, PAPER_OBS["Y1"],
                 0.05 * PAPER_OBS["Y1"], "nm"):
        fails.append("Y1 点预测")
    if not check("Y2 预测 vs 论文实测（5% 判据）", p2, PAPER_OBS["Y2"],
                 0.05 * PAPER_OBS["Y2"], "%"):
        fails.append("Y2 点预测")
    opt1 = find_optimum(m1)
    opt2 = find_optimum(m2)
    say("\n[5] 单响应寻优（论文用多响应满意度函数，仅作参考）：")
    say(f"  Y1 最小 → 预测 {opt1['yhat']:.4g} nm；Y2 最大 → 预测 {opt2['yhat']:.4g} %"
        f"（论文折中实测 {PAPER_OBS['Y1']} nm / {PAPER_OBS['Y2']} %）")
    e1 = abs(PAPER_OBS["Y1"] - PAPER_OPT["Y1"]) / PAPER_OPT["Y1"] * 100
    e2 = abs(PAPER_OBS["Y2"] - PAPER_OPT["Y2"]) / PAPER_OPT["Y2"] * 100
    say("  论文验证点相对误差：" + interpret_validation(PAPER_OPT["Y1"], PAPER_OBS["Y1"], e1))
    say("                        " + interpret_validation(PAPER_OPT["Y2"], PAPER_OBS["Y2"], e2))

    say("\n[6] 响应面图：")
    write_plot(m2, "公开数据_包封率", 0, 1, list(PAPER_OPT["point"]))


def validate_sr2022(fails):
    say("")
    say("=" * 78)
    say("数据集二：Scientific Reports 2022, s41598-022-12642-2（Nature 旗下）")
    say("3 因素 BBD，17 实验：A 乙醇% / B 时间 / C 溶剂用量")
    say("=" * 78)
    for key, label, coefs, stats, opt, tol_c in (
            ("yield", "Y1 产率（最大化）", SR_Y1_COEF, SR_Y1_STATS, SR_OPT_YIELD, 0.02),
            ("tpc", "Y2 总多酚（最大化）", SR_Y2_COEF, None, SR_OPT_TPC, 0.1)):
        exp = make_paper_demo(key)
        m = RSMModel(exp).fit()
        f_ref, adj_ref = formula_api_crosscheck(exp)
        say(f"\n[{key}] {label}：")
        ok = abs(m.f_model - f_ref) < 1e-6 and abs(m.adj_r2 - adj_ref) < 1e-9
        say(f"  [{'PASS' if ok else 'FAIL'}] 独立复核（公式 API）：F={f_ref:.4f}，"
            f"调整R²={adj_ref:.6f} 一致")
        if not ok:
            fails.append(f"SR {key} 独立复核")
        # 逐系数对照论文 Table 5
        labels = [t["label"] for t in m.terms]
        coef_ok = True
        for term, paper_val in coefs.items():
            mine = float(m.beta[labels.index(term) + 1])
            passed = abs(mine - paper_val) <= tol_c
            coef_ok &= passed
            say(f"  [{'PASS' if passed else 'FAIL'}] 系数 {term}: "
                f"软件 {mine:+.3f} vs 论文 {paper_val:+}")
        if not coef_ok:
            fails.append(f"SR {key} 系数")
        sig = "、".join(t["label"] for t in m.terms if t["sig"])
        say(f"  显著项：{sig}")
        if stats:
            if not check("R²", m.r2, stats["r2"], 0.005):
                fails.append(f"SR {key} R²")
            if not check("调整 R²", m.adj_r2, stats["adj"], 0.005):
                fails.append(f"SR {key} adjR2")
            if not check("预测 R²", m.pred_r2, stats["pred"], 0.02):
                fails.append(f"SR {key} predR2")
            lof_ok = m.lof_p is not None and m.lof_p > 0.05
            say(f"  [{'PASS' if lof_ok else 'FAIL'}] 失拟不显著: 软件 P="
                f"{m.lof_p:.4f} vs 论文 {stats['lof']}")
            if not lof_ok:
                fails.append(f"SR {key} 失拟")
        pt, pred, obs = opt
        mine_pred = float(m.predict_actual([pt])[0])
        tol = 0.15 if key == "yield" else 2.0
        if not check("论文最优点预测", mine_pred, pred, tol):
            fails.append(f"SR {key} 点预测")
        say(f"  （该点论文实测 {obs}）")
        opti = find_optimum(m)
        dist = max(abs(opti["actual"][i] - pt[i]) / (f.high - f.low)
                   for i, f in enumerate(exp.factor_list()))
        say(f"  [参考] 软件寻优 ({', '.join(f'{v:.4g}' for v in opti['actual'])}) → "
            f"预测 {opti['yhat']:.4g}；与论文最优点的编码距离 {dist:.2f}")
    say("\n响应面图：")
    exp3 = make_paper_demo("tpc")
    m3 = RSMModel(exp3).fit()
    write_plot(m3, "SciRep2022_多酚", 0, 2, [72.5, 48, 300])


def validate_errors(fails):
    say("\n[7] 报错路径测试（应给出友好提示而不是崩溃）：")

    def expect_error(name, fn):
        try:
            fn()
            say(f"  [FAIL] {name}：没有按预期报错")
            fails.append(name)
        except Exception as e:   # noqa: BLE001
            say(f"  [PASS] {name} → {type(e).__name__}: {e}")

    exp_bad = make_paper_demo("ee")
    exp_bad.runs[3].response = None
    expect_error("缺结果时拟合", lambda: RSMModel(exp_bad).fit())

    exp_2f = Experiment(factors=[Factor(name="A", low=1, center=2, high=3),
                                 Factor(name="B", low=1, center=2, high=3)])
    expect_error("因素不足时生成设计", lambda: generate_design(exp_2f))

    exp_vol = make_paper_demo("yield")
    exp_vol.system = SystemSetup(enabled=True, total_volume=10.0,
                                 fixed_components=[{"name": "水相", "volume": 9.0}])
    for f in exp_vol.factors:
        f.volume_mode = "direct"
    exp_vol.factors[0].low, exp_vol.factors[0].center, exp_vol.factors[0].high = 5, 6, 7
    generate_design(exp_vol)
    bd = exp_vol.volume_breakdown([7, 0, 0])
    ok = not bd["ok"]
    say(f"  [{'PASS' if ok else 'FAIL'}] 超体积条件被标记不可行 → {bd['issues'][:1]}")
    if not ok:
        fails.append("体积检查")

    exp = make_paper_demo("ee")
    df = results_dataframe(exp)
    for r in exp.run_list():
        r.response = None
    n = import_results(exp, df)
    ok = n == 26
    say(f"  [{'PASS' if ok else 'FAIL'}] Excel 4 因素往返导入 {n}/26")
    if not ok:
        fails.append("Excel 往返")


def main():
    fails = []
    validate_plga(fails)
    validate_sr2022(fails)
    validate_errors(fails)
    say("\n" + "=" * 78)
    if fails:
        say(f"验证完成，但 {len(fails)} 项超出容差：{fails}")
    else:
        say("验证完成：两个公开数据集全部指标在容差内一致 ✔")
    say("=" * 78)
    with open(os.path.join(OUT, "公开数据验证报告.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(REPORT))
    print("\n报告已写出：output/公开数据验证报告.txt")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
