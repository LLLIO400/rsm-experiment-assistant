"""示例实验：公开文献 BBD 数据（一键填入，用于快速测试软件全流程）。

数据集一：Sharma D, et al. "Formulation and Optimization of Polymeric Nanoparticles
for Intranasal Delivery of Lorazepam Using Box-Behnken Design"
BioMed Research International 2014, PMC4122152（开放获取，CC BY）

4 因素 BBD：PLGA 纳米粒，24 析因点 + 2 中心点 = 26 个实验。
两个响应：Y1 粒径 z-average（nm，越小越好）、Y2 包封率 %EE（越大越好）。
本模块是这份数据在软件内的唯一副本，validate_public.py 也从这里取数。

数据集二：Abd-El-Aziz et al. Scientific Reports 2022, s41598-022-12642-2
（Nature 旗下，开放获取），3 因素 BBD，17 实验（见下方 SR2022_RUNS）。
"""
from __future__ import annotations

from datetime import datetime

from .doegen import generate_design
from .models import Experiment, Factor, SystemSetup

# (X1, X2, X3, X4 编码), Y1 粒径 nm, Y2 包封率 %
PAPER_RUNS = [
    ((0, -1, 0, -1), 211.0, 70.00),
    ((0, -1, 0, +1), 220.0, 88.48),
    ((-1, 0, +1, 0), 176.0, 83.00),
    ((0, 0, -1, -1), 177.0, 71.00),
    ((-1, -1, 0, 0), 205.0, 81.00),
    ((-1, 0, 0, +1), 177.0, 83.50),
    ((-1, 0, -1, 0), 184.0, 75.00),
    ((0, 0, 0, 0), 197.0, 86.60),    # 中心点 1
    ((+1, 0, 0, -1), 271.0, 76.00),
    ((0, +1, 0, +1), 192.0, 84.30),
    ((-1, +1, 0, 0), 177.0, 80.00),
    ((+1, -1, 0, 0), 318.0, 90.10),
    ((0, +1, +1, 0), 191.0, 83.50),
    ((+1, +1, 0, 0), 228.0, 82.00),
    ((+1, 0, -1, 0), 241.0, 88.00),
    ((0, +1, 0, -1), 182.5, 66.40),
    ((0, -1, -1, 0), 215.0, 87.83),
    ((+1, 0, 0, +1), 261.0, 89.00),
    ((0, 0, -1, +1), 193.0, 88.00),
    ((-1, 0, 0, -1), 167.0, 65.50),
    ((0, 0, +1, -1), 192.0, 69.00),
    ((0, -1, +1, 0), 241.0, 88.00),
    ((0, 0, +1, +1), 202.0, 87.00),
    ((0, +1, -1, 0), 186.0, 84.00),
    ((+1, 0, +1, 0), 283.0, 88.00),
    ((0, 0, 0, 0), 193.0, 85.12),    # 中心点 2
]

# Scientific Reports 2022 (s41598-022-12642-2)：3 因素 BBD，17 实验（5 中心点）
# 因素：A 乙醇体积分数(%) 50/72.5/95；B 提取时间(h) 24/48/72；
#       C 溶剂用量(mL/20g) 200/300/400（论文的"料液比 1:10/1:15/1:20"换算）
# 下表编码采用软件约定（C 为溶剂体积，与论文的料液比编码方向相反）。
SR2022_RUNS = [
    ((+1, -1, 0), 2.70, 64.87),
    ((+1, +1, 0), 2.95, 65.28),
    ((-1, +1, 0), 4.16, 77.39),
    ((-1, -1, 0), 3.69, 72.76),
    ((-1, 0, +1), 3.90, 76.17),
    ((+1, 0, +1), 2.63, 56.33),
    ((-1, 0, -1), 3.20, 77.63),
    ((+1, 0, -1), 2.08, 87.72),
    ((0, -1, +1), 3.20, 86.66),
    ((0, +1, +1), 3.65, 93.16),
    ((0, +1, -1), 2.80, 103.65),
    ((0, -1, -1), 2.76, 102.27),
    ((0, 0, 0), 3.22, 80.89),   # 以下 5 个中心点
    ((0, 0, 0), 3.32, 81.54),
    ((0, 0, 0), 3.26, 87.80),
    ((0, 0, 0), 3.29, 96.98),
    ((0, 0, 0), 3.30, 80.72),
]

DEMOS = {
    # key: (文案, 响应名, 单位, 优化目标, 数据集, 取第几列数据)
    "yield": ("示例·提取产率（Sci Rep 2022, 3因素）", "提取产率", "g", "max", "sr2022", 1),
    "tpc": ("示例·总多酚含量（Sci Rep 2022, 3因素·弱模型演示）", "总多酚含量", "μg/mg",
            "max", "sr2022", 2),
    "ee": ("示例·PLGA纳米粒包封率（Biomed Res Int 2014, 4因素）", "包封率", "%", "max", "plga", 2),
    "size": ("示例·PLGA纳米粒粒径（Biomed Res Int 2014, 4因素）", "粒径", "nm", "min", "plga", 1),
}


def make_paper_demo(which: str = "ee") -> Experiment:
    """一键生成完整的示例实验：因素 + BBD 设计 + 全部文献实测结果。"""
    title, resp, unit, obj, dataset, yidx = DEMOS[which]
    if dataset == "sr2022":
        return _make_sr2022(title, resp, unit, obj, yidx)
    return _make_plga(title, resp, unit, obj, yidx)


def _fill_runs(exp: Experiment, runs, yidx):
    """按编码组合回填实测值；中心点按出现顺序对应。"""
    lookup = {tuple(r[0]): r[yidx] for r in runs}
    centers = iter(r[yidx] for r in runs if tuple(r[0]) == (0,) * len(r[0]))
    for run in exp.run_list():
        key = tuple(int(v) for v in run.coded)
        run.response = float(next(centers)) if key == (0,) * len(key) else float(lookup[key])


def _make_sr2022(title, resp, unit, obj, yidx) -> Experiment:
    exp = Experiment(
        name=title,
        created=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        response_name=resp, response_unit=unit, objective=obj,
        factors=[
            Factor(name="乙醇体积分数", unit="%", low=50, center=72.5, high=95),
            Factor(name="提取时间", unit="h", low=24, center=48, high=72),
            Factor(name="溶剂用量", unit="mL/20g", low=200, center=300, high=400),
        ],
        n_center=5,
        system=SystemSetup(enabled=False),
    )
    generate_design(exp)
    _fill_runs(exp, SR2022_RUNS, yidx)
    return exp


def _make_plga(title, resp, unit, obj, yidx) -> Experiment:
    exp = Experiment(
        name=title,
        created=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        response_name=resp,
        response_unit=unit,
        objective=obj,
        factors=[
            Factor(name="PLGA浓度", unit="mg/mL", low=10, center=35, high=60),
            Factor(name="Poloxamer407浓度", unit="mg/mL", low=2, center=8.5, high=15),
            Factor(name="水/有机相比例", unit="v/v", low=2, center=6, high=10),
            Factor(name="药物浓度", unit="mg/mL", low=1, center=3, high=5),
        ],
        n_center=2,
        system=SystemSetup(enabled=False),   # 文献数据不涉及固定体积配液
    )
    generate_design(exp)
    lookup = {tuple(r[0]): r[yidx] for r in PAPER_RUNS}
    centers = iter(r[yidx] for r in PAPER_RUNS if tuple(r[0]) == (0, 0, 0, 0))
    for run in exp.run_list():
        key = tuple(int(v) for v in run.coded)
        run.response = float(next(centers)) if key == (0, 0, 0, 0) else float(lookup[key])
    return exp
