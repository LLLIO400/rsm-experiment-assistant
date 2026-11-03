"""预测最优条件：网格多起点 + L-BFGS-B/SLSQP 数值优化（scipy）。

目标：最大化 / 最小化 / 逼近目标值。
启用体系检查时，若无约束最优条件不可配制，
自动在"补足液 ≥ 最低保留、各因素加入体积 ≥ 最小移液量"约束下重新寻优。
"""
from __future__ import annotations

import numpy as np
from scipy import optimize as spo

from .models import Experiment
from .stats import RSMModel


def _objective(model: RSMModel, exp: Experiment):
    if exp.objective == "max":
        return lambda x: -float(model.predict_coded(x)[0])
    if exp.objective == "min":
        return lambda x: float(model.predict_coded(x)[0])
    target = float(exp.target_value)

    def f(x):
        return abs(float(model.predict_coded(x)[0]) - target)
    return f


def _volume_affine(exp: Experiment):
    """把体积约束写成编码变量 x 的仿射函数。
    返回 (k_list, c_list)：V_i(x) = k_i * (center_i + step_i * x_i) 中与 x 有关的斜率/截距，
    以及 water(x) = W0 + Σ w_i·x_i。"""
    factors = exp.factor_list()
    sysu = exp.system
    k_list, c_list, w_coefs = [], [], []
    fixed_total = sysu.fixed_total()
    w0 = sysu.total_volume - fixed_total
    for f in factors:
        step = f.step()
        if f.volume_mode == "direct":
            k, c = 1.0, 0.0
        elif f.volume_mode == "stock" and f.stock_conc:
            k = float(sysu.total_volume) / float(f.stock_conc)
            c = 0.0
        else:
            k_list.append(None)
            c_list.append(None)
            w_coefs.append(0.0)
            continue
        # V_i = k * (center + step * x) + c
        k_list.append(k * step)
        c_list.append(k * f.center + c)
        w_coefs.append(-(k * step))
        w0 -= (k * f.center + c)
    return k_list, c_list, w_coefs, w0


def _constraints(exp: Experiment):
    """SLSQP 约束列表（编码空间）：每个都要求 >= 0。"""
    sysu = exp.system
    k_list, c_list, w_coefs, w0 = _volume_affine(exp)
    cons = [{"type": "ineq",
             "fun": lambda x, w=w_coefs, w0=w0: w0 + float(np.dot(w, x)) - sysu.water_min,
             "label": f"{sysu.filler_name} ≥ {sysu.water_min:g} μL"}]
    for i, (k, c) in enumerate(zip(k_list, c_list)):
        if k is None:
            continue
        cons.append({"type": "ineq",
                     "fun": lambda x, k=k, c=c, i=i: (k * x[i] + c) - sysu.min_pipette,
                     "label": f"因素 {chr(65 + i)} 加入体积 ≥ {sysu.min_pipette:g} μL"})
    return cons


def find_optimum(model: RSMModel, constrained: bool = False) -> dict:
    """返回 {'coded','actual','yhat','feasible','breakdown','note'}"""
    exp = model.exp
    k = exp.n_factors()
    fun = _objective(model, exp)

    bounds = [(-1.0, 1.0)] * k
    starts = [np.zeros(k)]
    grid = np.array(np.meshgrid(*([np.linspace(-1, 1, 5)] * k), indexing="ij")).reshape(k, -1).T
    starts += [g for g in grid]

    cons = _constraints(exp) if constrained else []
    method = "SLSQP" if constrained else "L-BFGS-B"

    best_x, best_f = None, np.inf
    for x0 in starts:
        try:
            res = spo.minimize(fun, np.asarray(x0, float), method=method,
                               bounds=bounds, constraints=cons,
                               options={"maxiter": 300})
            if res.success and res.fun < best_f:
                best_x, best_f = res.x, res.fun
        except Exception:
            continue
    if best_x is None:   # 兜底：粗网格里挑最好的
        vals = [fun(g) for g in grid]
        best_x = grid[int(np.argmin(vals))]

    yhat = float(model.predict_coded(best_x)[0])
    factors = exp.factor_list()
    actual = [f.coded_to_actual(float(x)) for f, x in zip(factors, best_x)]

    if exp.system.enabled:
        bd = exp.volume_breakdown(actual)
        feasible, issues = bd["ok"], bd["issues"]
    else:
        bd = None
        feasible, issues = True, []

    note = ""
    if not feasible:
        note = "预测最优条件在实际体系中无法直接配制：" + "；".join(issues)
    return {
        "coded": [float(x) for x in best_x],
        "actual": actual,
        "yhat": yhat,
        "feasible": feasible,
        "breakdown": bd,
        "note": note,
    }
