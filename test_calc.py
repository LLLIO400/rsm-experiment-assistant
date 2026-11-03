# -*- coding: utf-8 -*-
"""计算器核心测试：摩尔浓度知三求一、稀释。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core import calculator as calc

FAIL = []


def check(name, got, want, tol=0.01):
    ok = abs(got - want) <= tol
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {got:.4f} vs 期望 {want}")
    if not ok:
        FAIL.append(name)


def main():
    # ---- 摩尔浓度知三求一 ----
    name, v, u = calc.solve_molarity(mass=29.22, mw=58.44, volume=0.5)
    check("c = 29.22g NaCl / 0.5L", v, 1.0)
    name, v, u = calc.solve_molarity(mw=58.44, volume=0.25, conc=0.1)
    check("m = 0.1M NaCl 250mL", v, 1.461, tol=0.001)
    name, v, u = calc.solve_molarity(mass=18.015, mw=18.015, conc=2.0)
    check("V: 18.015g 水 / 2M", v, 0.5)
    name, v, u = calc.solve_molarity(mass=4.0, volume=0.1, conc=1.0)
    check("M: 4g / 100mL / 1M", v, 40.0)

    try:
        calc.solve_molarity(mass=1, mw=1)
        print("[FAIL] 只给两项未报错"); FAIL.append("molarity-args")
    except ValueError:
        print("[PASS] 摩尔浓度参数不足正确报错")

    # ---- 稀释 ----
    name, v = calc.solve_dilution(c1=1.0, c2=0.1, v2=0.05)     # 求V1
    check("V1: 1M→0.1M 定容50mL", v, 0.005)
    name, v = calc.solve_dilution(c1=2.0, v1=0.01, c2=0.05)     # 求V2
    check("V2: 2M×10mL→0.05M", v, 0.4)
    name, v = calc.solve_dilution(v1=0.005, v2=0.05, c2=0.1)    # 求C1
    check("C1", v, 1.0)
    name, v = calc.solve_dilution(c1=50e-3, v1=10e-3, v2=100e-3)  # 求C2
    check("C2: 50mM 10mL→100mL", v, 5e-3)

    print()
    if FAIL:
        print(f"{len(FAIL)} 项失败: {FAIL}")
        sys.exit(1)
    print("计算器全部通过 ✔")


if __name__ == "__main__":
    main()
