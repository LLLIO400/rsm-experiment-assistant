"""二次响应面模型拟合与 ANOVA（统计量全部由 statsmodels / scipy 计算）。

模型（编码单位）：Y = β0 + Σβi·xi + Σβij·xi·xj + Σβii·xi²
各项 P 值即完整模型下的偏检验（t 检验，与 Design-Expert 的 Adjusted F 检验等价，
F = t²）；预测 R² 由帽子矩阵 PRESS 计算；失拟检验以重复实验（中心点）为纯误差。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
import statsmodels.api as sm
from scipy import stats as sps

from .models import Experiment

LETTERS = "ABCDEFGH"


def term_specs(k: int) -> list:
    """返回 [(term_key, kind, {因子索引: 指数})]，不含截距。
    kind: 'main' / 'inter' / 'square'"""
    specs = []
    for i in range(k):
        specs.append((f"x{i}", "main", {i: 1}))
    for i, j in combinations(range(k), 2):
        specs.append((f"x{i}x{j}", "inter", {i: 1, j: 1}))
    for i in range(k):
        specs.append((f"x{i}^2", "square", {i: 2}))
    return specs


def build_matrix(coded: np.ndarray) -> np.ndarray:
    """coded: (N,k) → 设计矩阵 (N, 1+terms)，第一列为截距。"""
    n, k = coded.shape
    cols = [np.ones(n)]
    for _, _, exps in term_specs(k):
        col = np.ones(n)
        for i, e in exps.items():
            col = col * coded[:, i] ** e
        cols.append(col)
    return np.column_stack(cols)


def term_label(spec_key: str) -> str:
    """x0x1^2 → B² 之类的显示标签（用字母 A/B/C...）。"""
    import re
    parts = []
    for m in re.finditer(r"x(\d)(\^2)?", spec_key):
        idx = int(m.group(1))
        if m.group(2):
            parts.append(f"{LETTERS[idx]}²")
        else:
            parts.append(LETTERS[idx])
    return "".join(parts)


@dataclass
class RSMModel:
    exp: Experiment
    beta: np.ndarray = None
    labels: list = field(default_factory=list)      # 含截距的项标签
    descs: list = field(default_factory=list)       # 项描述（因素名组合）
    y: np.ndarray = None
    X: np.ndarray = None
    n_runs: int = 0
    df_model: int = 0
    df_resid: int = 0
    ss_model: float = 0.0
    ss_resid: float = 0.0
    ms_model: float = 0.0
    mse: float = 0.0
    f_model: float = 0.0
    p_model: float = 0.0
    r2: float = 0.0
    adj_r2: float = 0.0
    pred_r2: float = 0.0
    press: float = 0.0
    adeq: float = 0.0
    rmse: float = 0.0
    mean_y: float = 0.0
    cv: float = 0.0
    lof_f: float = None
    lof_p: float = None
    lof_df: int = 0
    pe_df: int = 0
    terms: list = field(default_factory=list)   # 每项的检验结果

    # ---------- 拟合 ----------
    def fit(self) -> "RSMModel":
        exp = self.exp
        factors = exp.factor_list()
        k = len(factors)
        runs = [r for r in exp.run_list() if r.response is not None]
        if len(runs) < len(exp.run_list()):
            raise ValueError(f"还有 {len(exp.run_list()) - len(runs)} 个实验未填写结果，请先完成第三步")
        if len(runs) <= len(term_specs(k)) + 1:
            raise ValueError("实验数量不足，无法拟合二次模型（请检查设计是否生成、结果是否填完）")

        coded = np.array([r.coded for r in runs], dtype=float)
        self.y = np.array([float(r.response) for r in runs], dtype=float)
        self.X = build_matrix(coded)

        self.labels = ["截距"] + [term_label(key) for key, _, _ in term_specs(k)]
        self.descs = ["—"]
        for key, kind, idx in term_specs(k):
            names = [factors[i].short_label() for i in idx]
            if kind == "main":
                self.descs.append(f"{names[0]}（一次项）")
            elif kind == "inter":
                self.descs.append(f"{' × '.join(names)}（交互项）")
            else:
                self.descs.append(f"{names[0]}（二次项）")

        res = sm.OLS(self.y, self.X).fit()
        self.beta = res.params
        n, p = self.X.shape
        self.n_runs = n
        self.df_model = p - 1
        self.df_resid = int(res.df_resid)
        self.mean_y = float(np.mean(self.y))
        self.ss_resid = float(np.sum(res.resid ** 2))
        self.mse = float(res.mse_resid)
        self.rmse = float(np.sqrt(self.mse))
        self.ss_model = float(np.sum((self.X @ self.beta - self.mean_y) ** 2))
        self.ms_model = self.ss_model / self.df_model
        self.f_model = self.ms_model / self.mse
        self.p_model = float(sps.f.sf(self.f_model, self.df_model, self.df_resid))
        self.r2 = 1 - self.ss_resid / float(np.sum((self.y - self.mean_y) ** 2))
        ss_tot = float(np.sum((self.y - self.mean_y) ** 2))
        self.adj_r2 = 1 - (self.ss_resid / self.df_resid) / (ss_tot / (n - 1))

        # PRESS 与预测 R²（帽子矩阵）
        XtX_inv = np.linalg.pinv(self.X.T @ self.X)
        h = np.einsum("ij,jk,ik->i", self.X, XtX_inv, self.X)
        resid = self.y - self.X @ self.beta
        self.press = float(np.sum((resid / (1 - h)) ** 2))
        self.pred_r2 = 1 - self.press / ss_tot

        # Adequate Precision（信噪比）
        pred = self.X @ self.beta
        p_terms = self.df_model
        self.adeq = float((pred.max() - pred.min()) / np.sqrt(p_terms * self.mse))
        self.cv = float(self.rmse / self.mean_y * 100) if abs(self.mean_y) > 1e-12 else float("nan")

        self._fit_terms(res)
        self._fit_lof(runs, coded)
        return self

    def _fit_terms(self, res):
        self.terms = []
        ss_tot = float(np.sum((self.y - self.mean_y) ** 2))
        for i in range(1, len(self.beta)):   # 跳过截距
            t = float(res.tvalues[i])
            f_val = t * t
            p_val = float(res.pvalues[i])
            ss = f_val * self.mse
            self.terms.append({
                "label": self.labels[i],
                "desc": self.descs[i],
                "coef": float(self.beta[i]),
                "se": float(res.bse[i]),
                "t": t,
                "f": f_val,
                "p": p_val,
                "ss": float(ss),
                "contrib": 100.0 * ss / ss_tot if ss_tot else 0.0,
                "sig": p_val < 0.05,
            })

    def _fit_lof(self, runs, coded):
        """失拟检验：以重复设计点（通常是中心点）为纯误差。"""
        groups = {}
        for r, crow in zip(runs, coded):
            key = tuple(np.round(crow, 9))
            groups.setdefault(key, []).append(float(r.response))
        n_groups = len(groups)
        pe_df = self.n_runs - n_groups
        self.pe_df = pe_df
        if pe_df <= 0 or self.df_resid - pe_df <= 0:
            self.lof_f = self.lof_p = None
            return
        ss_pe = 0.0
        for ys in groups.values():
            arr = np.array(ys)
            ss_pe += float(np.sum((arr - arr.mean()) ** 2))
        df_lof = self.df_resid - pe_df
        ss_lof = self.ss_resid - ss_pe
        ms_pe = ss_pe / pe_df
        ms_lof = ss_lof / df_lof
        self.lof_df = df_lof
        if ms_pe <= 0:
            self.lof_f, self.lof_p = None, None
            return
        self.lof_f = ms_lof / ms_pe
        self.lof_p = float(sps.f.sf(self.lof_f, df_lof, pe_df))

    # ---------- 预测 ----------
    def predict_coded(self, coded_points: np.ndarray) -> np.ndarray:
        coded_points = np.atleast_2d(np.asarray(coded_points, dtype=float))
        return build_matrix(coded_points) @ self.beta

    def predict_actual(self, actual_points) -> np.ndarray:
        factors = self.exp.factor_list()
        pts = np.atleast_2d(np.asarray(actual_points, dtype=float))
        coded = np.array([[f.actual_to_coded(v) for f, v in zip(factors, row)] for row in pts])
        return self.predict_coded(coded)

    # ---------- 汇总 ----------
    def summary_rows(self) -> list:
        """模型汇总表（用于界面展示）：[(指标, 值, 说明)]"""
        fp = lambda p: "< 0.0001" if p < 1e-4 else f"{p:.4f}"  # noqa: E731
        rows = [
            ("模型 F 值", f"{self.f_model:.2f}",
             "因素效应相对实验误差的强度：F 越大，这些因素对结果的影响越明显"),
            ("模型 P 值", fp(self.p_model),
             "P < 0.05：因素整体确实在影响结果，值得继续分析；"
             "P ≥ 0.05：因素范围可能没选对，或实验误差太大"),
            ("R²", f"{self.r2:.4f}",
             "模型解释了实验数据变化的百分比（0.94 = 94%），越接近 1 越贴合"),
            ("调整 R²", f"{self.adj_r2:.4f}",
             "扣除\"项数多 R² 自然偏高\"水分后的 R²；与 R² 差距大说明模型里有凑数的项"),
            ("预测 R²", f"{self.pred_r2:.4f}",
             "预测没做过的条件能有多准——最实用的指标；偏低说明换个条件模型就未必行"),
            ("标准差 (RMSE)", f"{self.rmse:.4g}",
             "实验点偏离模型的平均幅度，单位与响应值相同：预测值大致在 ±此值内浮动"),
            ("均值", f"{self.mean_y:.4g}",
             "全部实验响应值的平均，用来衡量标准差算大算小"),
            ("变异系数 C.V.%", f"{self.cv:.2f}",
             "标准差 ÷ 均值。实验操作稳定度参考：一般 < 10% 说明做得比较稳"),
            ("信噪比 (Adequate Precision)", f"{self.adeq:.2f}",
             "因素效应是实验误差的多少倍：> 4 才值得用模型找最优条件；"
             "偏小说明误差盖过了效应，先改进操作重复性再说"),
        ]
        if self.lof_p is not None:
            rows.append(("失拟 P 值", fp(self.lof_p),
                         "> 0.05：二次模型足以描述数据规律（好事）；"
                         "≤ 0.05：数据里有模型没抓住的规律，需补实验或换模型形式"))
        else:
            rows.append(("失拟 P 值", "不可计算",
                         "缺少重复实验（BBD 至少 2 个中心点才能算）"))
        return rows
