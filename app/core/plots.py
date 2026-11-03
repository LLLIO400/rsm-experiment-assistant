"""响应面绘图：Plotly 3D 曲面与二维等高线（离线 HTML，可旋转缩放）。

配色不锁定：默认 Turbo（蓝→绿→黄→红，接近 Design-Expert / 论文常见风格），
另有 Viridis / Cividis / Jet / 蓝白红可选。
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio

from .models import Experiment
from .stats import RSMModel

pio.templates.default = "plotly_white"

# 配色方案（plotly 内置命名色带 + 自定义蓝-白-红发散色带）
COLORSCALES = {
    "Viridis（Nature 常用）": "Viridis",
    "Cividis（色盲友好）": "Cividis",
    "Turbo（蓝绿黄红论文风）": "Turbo",
    "Jet（经典彩虹）": "Jet",
    "蓝-白-红（发散）": [(0.0, "#2166ac"), (0.25, "#67a9cf"), (0.5, "#f7f7f7"),
                       (0.75, "#ef8a62"), (1.0, "#b2182b")],
}
DEFAULT_CMAP = "Viridis（Nature 常用）"

FONT = dict(family="Microsoft YaHei UI, Arial, sans-serif", size=13, color="#374151")


def resolve_scale(name: str):
    return COLORSCALES.get(name, "Turbo")


def surface_grid(model: RSMModel, x_idx: int, y_idx: int, fixed_values: list,
                 n: int = 45):
    """返回 xa, ya（实际单位网格）与 za（预测响应）。"""
    factors = model.exp.factor_list()
    fx, fy = factors[x_idx], factors[y_idx]
    xs = np.linspace(fx.low, fx.high, n)
    ys = np.linspace(fy.low, fy.high, n)
    xa, ya = np.meshgrid(xs, ys)
    pts = np.tile(np.asarray(fixed_values, dtype=float), (xa.size, 1))
    pts[:, x_idx] = xa.ravel()
    pts[:, y_idx] = ya.ravel()
    za = model.predict_actual(pts).reshape(xa.shape)
    return xa, ya, za


def _design_points(model: RSMModel, x_idx: int, y_idx: int, fixed_values: list,
                   tol: float = 1e-6):
    """把与截面条件一致的设计点投到图上（其它因素取值≈固定值）。"""
    xs, ys, zs = [], [], []
    for r in model.exp.run_list():
        if r.response is None:
            continue
        if all(abs(v - f) < max(tol, abs(f) * 1e-6)
               for i, (v, f) in enumerate(zip(r.actual, fixed_values))
               if i not in (x_idx, y_idx)):
            xs.append(r.actual[x_idx])
            ys.append(r.actual[y_idx])
            zs.append(float(r.response))
    return xs, ys, zs


def _fixed_text(factors, x_idx, y_idx, fixed_values) -> str:
    return "，".join(f"{factors[i].short_label()} = {fixed_values[i]:.4g}"
                     for i in range(len(factors)) if i not in (x_idx, y_idx))


def surface_figure_html(model: RSMModel, x_idx: int, y_idx: int,
                        fixed_values: list, height: int = 620,
                        cmap: str = DEFAULT_CMAP) -> str:
    exp = model.exp
    factors = exp.factor_list()
    scale = resolve_scale(cmap)
    xa, ya, za = surface_grid(model, x_idx, y_idx, fixed_values)

    fig = go.Figure(data=[go.Surface(
        x=xa, y=ya, z=za,
        colorscale=scale,
        colorbar=dict(title=dict(text=exp.response_name or "Y", font=FONT),
                      thickness=16, len=0.75),
        contours=dict(
            x=dict(show=True, usecolormap=False, color="rgba(255,255,255,0.45)",
                   width=2, project=dict(x=False)),
            y=dict(show=True, usecolormap=False, color="rgba(255,255,255,0.45)",
                   width=2, project=dict(y=False)),
            z=dict(show=True, usecolormap=True, project=dict(z=True)),
        ),
        hovertemplate="%{x:.4g}<br>%{y:.4g}<br>预测: %{z:.5g}<extra></extra>",
    )])
    px, py, pz = _design_points(model, x_idx, y_idx, fixed_values)
    if px:
        fig.add_trace(go.Scatter3d(
            x=px, y=py, z=pz, mode="markers",
            marker=dict(size=4.5, color="#111827", symbol="circle",
                        line=dict(width=1, color="white")),
            name="实验点（该截面）",
            hovertemplate="%{x:.4g}<br>%{y:.4g}<br>实测: %{z:.5g}<extra></extra>"))

    zmin, zmax = float(np.min(za)), float(np.max(za))
    pad = (zmax - zmin) * 0.15 + 1e-9
    fixed_txt = _fixed_text(factors, x_idx, y_idx, fixed_values)
    fig.update_layout(
        title=dict(text=f"{exp.response_name or 'Y'} = f({factors[x_idx].short_label()}, "
                        f"{factors[y_idx].short_label()})"
                        + (f"　（固定 {fixed_txt}）" if fixed_txt else ""),
                    font=dict(size=15, color="#111827")),
        scene=dict(
            xaxis_title=f"{factors[x_idx].short_label()}({factors[x_idx].unit})"
                        f"<br><i>（{chr(65 + x_idx)}）</i>",
            yaxis_title=f"{factors[y_idx].short_label()}({factors[y_idx].unit})"
                        f"<br><i>（{chr(65 + y_idx)}）</i>",
            zaxis_title=exp.response_name or "Y",
            zaxis=dict(range=[zmin - pad, zmax + pad]),
            camera=dict(eye=dict(x=1.55, y=1.45, z=0.9)),
        ),
        font=FONT,
        height=height, margin=dict(l=10, r=10, b=10, t=60),
        uirevision="keep",
    )
    return pio.to_html(fig, full_html=False, include_plotlyjs=True,
                       config={"displaylogo": False, "responsive": True})


def contour_figure_html(model: RSMModel, x_idx: int, y_idx: int,
                        fixed_values: list, height: int = 620,
                        cmap: str = DEFAULT_CMAP) -> str:
    exp = model.exp
    factors = exp.factor_list()
    scale = resolve_scale(cmap)
    xa, ya, za = surface_grid(model, x_idx, y_idx, fixed_values)

    fig = go.Figure(data=[go.Contour(
        x=xa[0], y=ya[:, 0], z=za,
        colorscale=scale,
        contours=dict(showlabels=True, labelfont=dict(size=11, color="#111827")),
        line=dict(width=0.8, color="rgba(255,255,255,0.6)"),
        colorbar=dict(title=dict(text=exp.response_name or "Y", font=FONT),
                      thickness=16),
        hovertemplate="%{x:.4g}<br>%{y:.4g}<br>预测: %{z:.5g}<extra></extra>",
    )])
    px, py, pz = _design_points(model, x_idx, y_idx, fixed_values)
    if px:
        fig.add_trace(go.Scatter(
            x=px, y=py, mode="markers",
            marker=dict(size=10, color="#111827", symbol="circle-open",
                        line=dict(width=2, color="#111827")),
            name="实验点（该截面）"))

    fixed_txt = _fixed_text(factors, x_idx, y_idx, fixed_values)
    fig.update_layout(
        title=dict(text=f"二维等高线" + (f"　（固定 {fixed_txt}）" if fixed_txt else ""),
                   font=dict(size=15, color="#111827")),
        xaxis=dict(title=f"{factors[x_idx].short_label()}({factors[x_idx].unit})　"
                         f"（{chr(65 + x_idx)}）", gridcolor="#eef1f5", zeroline=False),
        yaxis=dict(title=f"{factors[y_idx].short_label()}({factors[y_idx].unit})　"
                         f"（{chr(65 + y_idx)}）", gridcolor="#eef1f5", zeroline=False),
        font=FONT, height=height,
        margin=dict(l=10, r=10, b=10, t=60),
        uirevision="keep",
    )
    return pio.to_html(fig, full_html=False, include_plotlyjs=True,
                       config={"displaylogo": False, "responsive": True})
