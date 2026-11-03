"""Box-Behnken 设计（BBD）生成。

设计矩阵为编码水平：每个因素取 -1 / 0 / +1，
BBD 由 "所有因素两两组合的四个角点、其余因素固定在 0" 构成，
共 2k(k-1) 个析因点，另加若干中心点。
"""
from __future__ import annotations

import itertools
import random

from .models import Experiment, Run


def bbd_coded_matrix(k: int) -> list:
    """k 因素 BBD 的标准顺序编码矩阵（不含中心点）。"""
    rows = []
    for i, j in itertools.combinations(range(k), 2):
        for vi, vj in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            row = [0] * k
            row[i], row[j] = vi, vj
            rows.append(row)
    return rows


def generate_design(exp: Experiment) -> None:
    """按当前因素水平生成 BBD 并写入 exp.runs（含随机化运行顺序与中心点）。"""
    factors = exp.factor_list()
    k = len(factors)
    if k < 3:
        raise ValueError("BBD 至少需要 3 个因素")

    coded = bbd_coded_matrix(k)
    coded += [[0] * k for _ in range(exp.n_center)]
    n = len(coded)

    rng = random.Random(exp.design_seed)
    orders = list(range(1, n + 1))
    rng.shuffle(orders)

    exp.runs = []
    for idx, crow in enumerate(coded):
        actual = [f.coded_to_actual(c) for f, c in zip(factors, crow)]
        exp.runs.append(Run(std=idx + 1, order=orders[idx], coded=crow, actual=actual))
