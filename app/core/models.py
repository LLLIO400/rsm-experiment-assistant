"""实验数据模型与 JSON 持久化。

一个 Experiment 对象对应磁盘上的一个 JSON 文件（data/ 目录），
界面五步操作（新建/设计/结果/分析/优化验证）都读写这一份数据。
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

if getattr(sys, "frozen", False):      # PyInstaller 绿色版：一切落在 exe 旁边
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(APP_DIR, "data")
SKILL_PATH = os.path.join(APP_DIR, "skills", "rsm_skill.md")
CONFIG_PATH = os.path.join(APP_DIR, "config.json")


@dataclass
class Factor:
    name: str = ""          # 如 "Mg2+浓度"
    unit: str = ""          # 如 "mM"
    low: float = 0.0        # 低水平（-1）
    center: float = 0.0     # 中心水平（0）
    high: float = 0.0       # 高水平（+1）
    # 配液方式：none=不参与体积检查 / direct=因素值即加入体积(μL) / stock=按母液浓度换算
    volume_mode: str = "none"
    stock_conc: Optional[float] = None   # 母液浓度（单位与因素一致）
    stock_label: str = ""    # 母液名称，仅用于配液表显示

    def step(self) -> float:
        return self.high - self.center

    def coded_to_actual(self, coded: float) -> float:
        return self.center + coded * self.step()

    def actual_to_coded(self, actual: float) -> float:
        s = self.step()
        return (actual - self.center) / s if s else 0.0

    def volume_for(self, actual_value: float, total_volume: float) -> Optional[float]:
        """该因素在给定取值下需要加入的体积（μL）；无法换算时返回 None。"""
        if self.volume_mode == "direct":
            return float(actual_value)
        if self.volume_mode == "stock" and self.stock_conc:
            return float(actual_value) * float(total_volume) / float(self.stock_conc)
        return None

    def short_label(self) -> str:
        return self.name or "因素"


@dataclass
class FixedComponent:
    name: str = "DNA"
    volume: float = 20.0    # μL


@dataclass
class SystemSetup:
    enabled: bool = True
    total_volume: float = 50.0       # μL
    min_pipette: float = 0.5         # 最小可准确移液体积 μL
    water_min: float = 0.0           # 补足液最少保留体积 μL
    filler_name: str = "水"
    fixed_components: list = field(default_factory=lambda: [asdict(FixedComponent())])
    # 兼容旧数据
    def fixed_list(self) -> list:
        return [FixedComponent(**f) if isinstance(f, dict) else f for f in self.fixed_components]

    def fixed_total(self) -> float:
        return sum(float(f.volume) for f in self.fixed_list())


@dataclass
class Run:
    std: int                       # 标准顺序号（1..N）
    order: int                     # 随机化后的实验运行顺序
    coded: list                    # 编码值列表 [-1/0/1]
    actual: list                   # 实际取值
    response: Optional[float] = None   # 实测响应值


@dataclass
class Validation:
    predicted: float
    actual: float
    error_pct: float
    note: str = ""
    time: str = ""


@dataclass
class Experiment:
    name: str = ""
    created: str = ""
    modified: str = ""
    file_path: str = ""

    response_name: str = "荧光强度"
    response_unit: str = ""
    objective: str = "max"          # max / min / target
    target_value: Optional[float] = None

    factors: list = field(default_factory=list)      # [Factor]
    n_center: int = 5
    system: SystemSetup = field(default_factory=SystemSetup)

    design_seed: int = 42
    runs: list = field(default_factory=list)         # [Run]，按标准序存储
    validations: list = field(default_factory=list)  # [Validation]

    # ---------- 基本操作 ----------
    def touch(self):
        self.modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def n_factors(self) -> int:
        return len(self.factors)

    def factor_list(self) -> list:
        return [Factor(**f) if isinstance(f, dict) else f for f in self.factors]

    def has_design(self) -> bool:
        return len(self.runs) > 0

    def results(self) -> dict:
        """std -> response"""
        out = {}
        for r in self.run_list():
            if r.response is not None:
                out[r.std] = float(r.response)
        return out

    def run_list(self) -> list:
        return [Run(**r) if isinstance(r, dict) else r for r in self.runs]

    def runs_in_order(self) -> list:
        return sorted(self.run_list(), key=lambda r: r.order)

    def n_done(self) -> int:
        return len(self.results())

    # ---------- 体积检查 ----------
    def volume_breakdown(self, actual_values: list) -> dict:
        """给定一组因素实际取值，返回 {'volumes': [..], 'water': .., 'total': ..,
        'issues': [str], 'ok': bool}。未配置体积方式的因素不参与检查。"""
        sysu = self.system
        factors = self.factor_list()
        volumes, issues = [], []
        checked_total = sysu.fixed_total()
        for f, v in zip(factors, actual_values):
            vol = f.volume_for(v, sysu.total_volume)
            volumes.append(vol)
            if vol is not None:
                checked_total += vol
                if vol < sysu.min_pipette:
                    issues.append(f"「{f.short_label()}」加入体积 {vol:.2f} μL 小于最小可移液体积 "
                                  f"{sysu.min_pipette:g} μL")
        water = sysu.total_volume - checked_total
        if water < sysu.water_min - 1e-9:
            issues.append(f"{sysu.filler_name}体积为 {water:.2f} μL（< {sysu.water_min:g} μL），"
                          f"总体系 {sysu.total_volume:g} μL 无法配制")
        return {
            "volumes": volumes,
            "water": water,
            "total": checked_total + max(water, 0.0),
            "issues": issues,
            "ok": not issues,
        }

    # ---------- 持久化 ----------
    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("file_path", None)
        return d

    @staticmethod
    def from_dict(d: dict) -> "Experiment":
        exp = Experiment()
        for k, v in d.items():
            if hasattr(exp, k):
                setattr(exp, k, v)
        exp.factors = [Factor(**f) if isinstance(f, dict) else f for f in exp.factors]
        exp.system = SystemSetup(**d["system"]) if isinstance(d.get("system"), dict) else SystemSetup()
        exp.runs = [Run(**r) if isinstance(r, dict) else r for r in exp.runs]
        exp.validations = [Validation(**v) if isinstance(v, dict) else v for v in exp.validations]
        return exp

    def save(self, path: Optional[str] = None) -> str:
        self.touch()
        path = path or self.file_path
        if not path:
            os.makedirs(DATA_DIR, exist_ok=True)
            safe = re.sub(r'[\\/:*?"<>|]', "_", self.name).strip() or "实验"
            path = os.path.join(DATA_DIR, f"{safe}_{datetime.now():%Y%m%d_%H%M%S}.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, ensure_ascii=False, indent=2)
        self.file_path = path
        return path

    @staticmethod
    def load(path: str) -> "Experiment":
        with open(path, "r", encoding="utf-8") as fh:
            exp = Experiment.from_dict(json.load(fh))
        exp.file_path = path
        return exp

    @staticmethod
    def new_default() -> "Experiment":
        """全新空白实验：任何内容都不预填，全部由用户输入。"""
        return Experiment(
            name="",
            created=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            response_name="",
            objective="max",
            factors=[],
            system=SystemSetup(fixed_components=[]),
        )


def load_skill_text() -> str:
    if os.path.exists(SKILL_PATH):
        with open(SKILL_PATH, "r", encoding="utf-8") as fh:
            return fh.read()
    return ""


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    return {"base_url": "https://api.openai.com/v1", "api_key": "", "model": "gpt-4o-mini"}


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
