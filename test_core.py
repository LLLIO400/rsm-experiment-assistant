# -*- coding: utf-8 -*-
"""核心层端到端冒烟测试：BBD 生成 → 配液检查 → 二次拟合 → ANOVA → 寻优 → 验证。"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.models import Experiment, Factor, SystemSetup, FixedComponent
from app.core.doegen import generate_design, bbd_coded_matrix
from app.core.stats import RSMModel, term_label
from app.core.optimizer import find_optimum
from app.core.interp import interpret_model, interpret_optimum, interpret_validation
from app.core.volume import prep_table, stock_requirements
from app.core.excelio import design_dataframe, results_dataframe, import_results

FAIL = []


def check(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"[{tag}] {name} {detail}")
    if not cond:
        FAIL.append(name)


def make_exp() -> Experiment:
    exp = Experiment(
        name="LAMP反应体系优化", response_name="荧光强度", objective="max",
        factors=[
            Factor(name="Mg2+浓度", unit="mM", low=1, center=2, high=3,
                   volume_mode="stock", stock_conc=25, stock_label="Mg母液"),
            Factor(name="引物浓度", unit="μM", low=0.2, center=0.4, high=0.6,
                   volume_mode="stock", stock_conc=10, stock_label="引物母液(10x)"),
            Factor(name="试剂C浓度", unit="mM", low=5, center=10, high=15,
                   volume_mode="direct"),
        ],
        system=SystemSetup(
            enabled=True, total_volume=50.0, min_pipette=0.5,
            fixed_components=[FixedComponent("DNA", 20.0).__dict__.copy()],
        ),
        n_center=5,
    )
    return exp


def main():
    # ---------- 1. BBD 结构 ----------
    m3 = bbd_coded_matrix(3)
    check("BBD 3因素=12个析因点", len(m3) == 12)
    check("BBD 每行恰好两个±1", all(sum(1 for v in row if v != 0) == 2 for row in m3))
    check("BBD 无重复组合", len({tuple(r) for r in m3}) == 12)

    exp = make_exp()
    generate_design(exp)
    check("设计含 12+5=17 个 run", len(exp.runs) == 17)
    orders = sorted(r.order for r in exp.runs)
    check("运行序是 1..17 的随机排列", orders == list(range(1, 18)))
    centers = [r for r in exp.runs if all(c == 0 for c in r.coded)]
    check("5 个中心点", len(centers) == 5)

    # ---------- 2. 配液检查 ----------
    prep = prep_table(exp)
    ok_all = all(p["ok"] for p in prep)
    check("默认示例所有 run 配液可行", ok_all,
          "" if ok_all else str([p["issues"] for p in prep if not p["ok"]][:2]))
    # 中心点：Mg 2mM→2*50/25=4μL, 引物 0.4μM→0.4*50/10=2μL, C=10μL → 水=50-20-4-2-10=14
    center = next(p for p in prep if all(c == 0 for c in
                  next(r for r in exp.run_list() if r.std == p["std"]).coded))
    check("中心点水体积=14μL", abs(center["water"] - 14.0) < 1e-9,
          f"实际 {center['water']}")
    reqs = stock_requirements(exp)
    check("母液需求包含两项", len(reqs) == 2, str(reqs))

    # 人为制造不可行：把 C 范围调大 → direct 体积超限
    exp_bad = make_exp()
    exp_bad.factors[2].high = 45
    exp_bad.factors[2].center = 25
    exp_bad.factors[2].low = 5
    generate_design(exp_bad)
    prep_bad = prep_table(exp_bad)
    bad = [p for p in prep_bad if not p["ok"]]
    check("超体积条件被标记不可行", len(bad) > 0, f"{len(bad)} 个不可行")

    # ---------- 3. 拟合：用已知函数造数据 ----------
    exp2 = make_exp()
    generate_design(exp2)
    rng = np.random.default_rng(7)
    true = lambda a, b, c: (45000 * (1 + 0.62 * ((a - 2.4) / 1) ** 2 * -1 + 0.3 * ((b - 0.4) / 0.2) ** 2 * -1
                            + 0.25 * ((c - 10.8) / 5) ** 2 * -1 + 0.18 * ((a - 2) / 1) * ((b - 0.4) / 0.2)))
    for r in exp2.run_list():
        a, b, c = r.actual
        r.response = float(true(a, b, c) + rng.normal(0, 400))
    model = RSMModel(exp2).fit()
    check("模型显著", model.p_model < 0.0001, f"P={model.p_model:.2g}")
    check("R² 很高", model.r2 > 0.99, f"R²={model.r2:.4f}")
    check("失拟不显著", model.lof_p is not None and model.lof_p > 0.05,
          f"lof_P={model.lof_p}")
    check("各项检验齐全(9项)", len(model.terms) == 9)
    sig_labels = [t["label"] for t in model.terms if t["sig"]]
    check("显著项包含 A²/B²/C²", {"A²", "B²", "C²"} <= set(sig_labels), str(sig_labels))
    check("预测R²<调整R²且接近1", 0.9 < model.pred_r2 <= model.adj_r2 + 1e-9,
          f"pred={model.pred_r2:.4f} adj={model.adj_r2:.4f}")
    check(" adeq >4", model.adeq > 4, f"{model.adeq:.1f}")

    # 预测抽查：中心点附近预测与真值接近
    pred_mid = float(model.predict_actual([[2.0, 0.4, 10.0]])[0])
    check("中心点预测接近真值", abs(pred_mid - true(2.0, 0.4, 10.0)) < 800,
          f"pred={pred_mid:.0f} true={true(2.0, 0.4, 10.0):.0f}")

    # ---------- 4. 寻优 ----------
    opt = find_optimum(model)
    check("无约束最优可行", opt["feasible"], opt["note"])
    # 真函数在 a=2.4,b=0.4,c=10.8 附近最大
    err = [abs(o - t) / (f.high - f.low) * 2 for o, t, f in
           zip(opt["actual"], [2.4, 0.4, 10.8], exp2.factor_list())]
    check("最优条件接近真值(编码距离<0.15)", max(err) < 0.15,
          f"opt={['%.3f' % o for o in opt['actual']]} dist={['%.3f' % e for e in err]}")
    check("预测值接近真最大", abs(opt["yhat"] - true(2.4, 0.4, 10.8)) < 800,
          f"yhat={opt['yhat']:.0f}")

    # 约束寻优：让 C 的直接体积上限受水体积限制
    exp3 = make_exp()
    exp3.factors[2].low, exp3.factors[2].center, exp3.factors[2].high = 5, 27.5, 50
    generate_design(exp3)
    for r in exp3.run_list():
        a, b, c = r.actual
        r.response = float(true(a, b, c) + rng.normal(0, 400))
    m3f = RSMModel(exp3).fit()
    opt3 = find_optimum(m3f)
    if opt3["feasible"]:
        check("该场景无约束最优即可行(可接受)", True)
    else:
        opt3c = find_optimum(m3f, constrained=True)
        check("约束寻优后可行", opt3c["feasible"], str(opt3c["breakdown"]["issues"] if opt3c["breakdown"] else ""))
        check("约束寻优值不高于无约束值",
              (m3f.predict_actual([opt3c["actual"]])[0] <= m3f.predict_actual([opt3["actual"]])[0] + 1))

    # ---------- 5. 解读文本 ----------
    txt = interpret_model(exp2, model)
    check("解读提到交互作用", "交互" in txt)
    txt2 = interpret_optimum(exp2, opt)
    check("最优解读含预测值", f"{opt['yhat']:.0f}".replace(",", "") in txt2.replace(",", ""))
    txt3 = interpret_validation(24583, 23970, 2.49)
    check("验证解读含误差", "2.49" in txt3)

    # ---------- 6. Excel 往返 ----------
    df = design_dataframe(exp2, with_prep=True)
    check("方案表列含配液可行", "配液可行" in df.columns, str(list(df.columns)[:6]))
    df.loc[df["运行序"] == exp2.runs_in_order()[0].order, "荧光强度"] = 12345.0
    n = import_results(exp2, df)
    check("Excel 导入更新1条", n == 1)
    check("导入值已写入", exp2.results().get(
        next(r.std for r in exp2.run_list() if r.order == exp2.runs_in_order()[0].order)) == 12345.0)

    print()
    if FAIL:
        print(f"共 {len(FAIL)} 项失败: {FAIL}")
        sys.exit(1)
    print("全部通过 ✔")


if __name__ == "__main__":
    main()
