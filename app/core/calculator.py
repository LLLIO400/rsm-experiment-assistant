"""实验常用计算：摩尔浓度（知三求一）、稀释 C1V1=C2V2。

  1. c = m / (M·V) —— 质量 / 摩尔质量 / 体积 / 浓度，任知三求一
  2. C1·V1 = C2·V2 —— 稀释，任知三求一
"""
from __future__ import annotations

# 单位换算表（下拉框显示用，保持顺序）
MASS_UNITS = [("g", 1.0), ("mg", 1e-3), ("μg", 1e-6)]
VOL_UNITS = [("L", 1.0), ("mL", 1e-3), ("μL", 1e-6)]
CONC_UNITS = [("M (mol/L)", 1.0), ("mM", 1e-3), ("μM", 1e-6), ("nM", 1e-9)]


def unit_factor(units: list, name: str) -> float:
    for label, factor in units:
        if label == name:
            return factor
    return 1.0


def solve_molarity(mass=None, mw=None, volume=None, conc=None):
    """c = m/(M·V)：质量 g、摩尔质量 g/mol、体积 L、浓度 mol/L，恰好给三个求第四个。

    返回 (量名, 数值, 单位)。
    """
    vals = [mass, mw, volume, conc]
    known = [v for v in vals if v is not None]
    if len(known) != 3:
        raise ValueError("请填写其中三项、留空一项（软件求留空的那项）")
    if any(v is not None and v <= 0 for v in known):
        raise ValueError("数值必须大于 0")
    if mass is None:
        return "质量", conc * mw * volume, "g"
    if mw is None:
        return "摩尔质量", mass / (conc * volume), "g/mol"
    if volume is None:
        return "体积", mass / (mw * conc), "L"
    return "浓度", mass / (mw * volume), "mol/L"


def solve_dilution(c1=None, v1=None, c2=None, v2=None):
    """C1·V1 = C2·V2：恰好给三个求第四个。浓度单位一致、体积单位一致即可。

    返回 (量名, 数值)。
    """
    vals = [c1, v1, c2, v2]
    known = [v for v in vals if v is not None]
    if len(known) != 3:
        raise ValueError("请填写其中三项、留空一项（软件求留空的那项）")
    if any(v is not None and v <= 0 for v in known):
        raise ValueError("数值必须大于 0")
    if c1 is None:
        return "初始浓度 C1", c2 * v2 / v1
    if v1 is None:
        return "取液体积 V1", c2 * v2 / c1
    if c2 is None:
        return "目标浓度 C2", c1 * v1 / v2
    return "最终体积 V2", c1 * v1 / c2
