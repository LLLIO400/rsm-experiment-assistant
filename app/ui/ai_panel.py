"""AI 实验助手面板。

分工边界：统计量一律来自软件计算层（statsmodels/scipy）；
AI 只读取「RSM Skill + 实验数据 + 软件计算结果」做解释与建议，不发明统计方法。
未配置 API 时仍可用"内置解读"（确定性模板）。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from PySide6.QtCore import QObject, QThread, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDockWidget,
                               QFormLayout, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QProgressBar, QTextBrowser,
                               QPushButton, QVBoxLayout, QWidget)

from ..core.models import Experiment, load_config, load_skill_text, save_config
from .widgets import section_title, tip_label

PRESET_QUESTIONS = [
    "这个模型靠谱吗？",
    "为什么交互项显著？",
    "这个最优条件能不能直接做？",
    "帮我解释这个响应面。",
    "帮我设计验证实验。",
    "把这次实验整理成实验记录。",
]


class AiWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, cfg: dict, messages: list):
        super().__init__()
        self.cfg = cfg
        self.messages = messages

    def work(self):
        try:
            reply = self._call()
            self.finished.emit(reply)
        except Exception as e:   # noqa: BLE001
            self.failed.emit(str(e))

    def _call(self) -> str:
        base = self.cfg.get("base_url", "").rstrip("/")
        key = self.cfg.get("api_key", "")
        model = self.cfg.get("model", "")
        local = any(s in base for s in ("localhost", "127.0.0.1", "0.0.0.0"))
        if not base or not model:
            raise RuntimeError("尚未配置 API。请点击「设置」填写接口地址和模型名"
                               "（本地 Ollama 可点「填入本地 Ollama 默认」）。")
        if not key and not local:
            raise RuntimeError("云端接口需要填写 API Key；纯本地服务（localhost）可留空。")
        if not key:
            key = "local"   # 本地服务不校验，占位即可
        url = f"{base}/chat/completions"
        payload = json.dumps({
            "model": model,
            "messages": self.messages,
            "temperature": self.cfg.get("temperature", 0.3),
        }).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=300) as resp:  # 本地模型冷启动可能较慢
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


class AiConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 接口设置")
        self.cfg = load_config()
        form = QFormLayout(self)
        self.ed_base = QLineEdit(self.cfg.get("base_url", ""))
        self.ed_key = QLineEdit(self.cfg.get("api_key", ""))
        self.ed_key.setEchoMode(QLineEdit.Password)
        self.ed_model = QComboBox()
        self.ed_model.setEditable(True)
        self.ed_model.setCurrentText(self.cfg.get("model", ""))
        form.addRow("接口地址(base_url)", self.ed_base)
        form.addRow("API Key（本地服务可随便填）", self.ed_key)
        form.addRow("模型名", self.ed_model)
        self.btn_models = QPushButton("获取服务里的模型列表（自动填入下拉框）")
        self.btn_models.clicked.connect(self._fetch_models)
        form.addRow(self.btn_models)
        self.lbl_fetch = tip_label("")
        form.addRow(self.lbl_fetch)

        presets = QHBoxLayout()
        btn_lms = QPushButton("填入 LM Studio 默认")
        btn_lms.setToolTip("LM Studio：打开软件 → 顶部 Developer(开发者) 页签 → 加载对话模型 → "
                          "Start Server（保持运行）")
        btn_lms.clicked.connect(self._fill_lmstudio)
        btn_ollama = QPushButton("填入 Ollama 默认")
        btn_ollama.setToolTip("需要先安装 Ollama 并拉取模型，例如：ollama pull qwen2.5:7b-instruct")
        btn_ollama.clicked.connect(self._fill_ollama)
        presets.addWidget(btn_lms)
        presets.addWidget(btn_ollama)
        wrap = QWidget()
        wrap.setLayout(presets)
        form.addRow(wrap)
        form.addRow(tip_label(
            "兼容 OpenAI /chat/completions 格式。本地方式任选（免费、数据不出电脑）："
            "① LM Studio：打开 → Developer 页签 → 加载一个对话模型 → Start Server，"
            "回这里点「填入 LM Studio 默认」会自动列出模型；"
            "② Ollama：安装后命令行运行 ollama pull qwen2.5:7b-instruct，再点「填入 Ollama 默认」。"
            "云端（DeepSeek/通义/Kimi）也支持：填官方 base_url 和 API Key。"
            "配置保存在软件目录 config.json。"))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def _fill_lmstudio(self):
        self.ed_base.setText("http://localhost:1234/v1")
        self.ed_key.setText("lm-studio")
        self.lbl_fetch.setText("已填入 LM Studio 地址——请先在 LM Studio 里 Start Server，"
                               "正在尝试获取模型列表…")
        self._fetch_models()

    def _fill_ollama(self):
        self.ed_base.setText("http://localhost:11434/v1")
        self.ed_key.setText("local")
        self.ed_model.setCurrentText("qwen2.5:7b-instruct")
        self._fetch_models()

    def _fetch_models(self):
        """查询服务的 /v1/models，把模型名填进下拉框（LM Studio / Ollama / 云端通用）。"""
        import json as _json
        import urllib.request
        base = self.ed_base.text().strip().rstrip("/")
        if not base:
            self.lbl_fetch.setText("请先填写接口地址。")
            return
        req = urllib.request.Request(f"{base}/models")
        key = self.ed_key.text().strip()
        if key:
            req.add_header("Authorization", f"Bearer {key}")
        try:
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
            ids = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
            self.ed_model.clear()
            self.ed_model.addItems(ids)
            if ids:
                self.lbl_fetch.setText(f"✓ 找到 {len(ids)} 个模型，请在「模型名」里选择。")
            else:
                self.lbl_fetch.setText("服务在线但没有返回模型——请先在 LM Studio / Ollama 里加载模型。")
        except Exception as e:   # noqa: BLE001
            self.lbl_fetch.setText(f"✗ 连接失败：{e}。"
                                   f"LM Studio：Developer 页签 → Start Server 后再试。")

    def accept(self):
        self.cfg.update({
            "base_url": self.ed_base.text().strip(),
            "api_key": self.ed_key.text().strip(),
            "model": self.ed_model.currentText().strip(),
        })
        save_config(self.cfg)
        super().accept()


def build_context(exp: Experiment, model, optimum: dict | None, stage: str) -> str:
    """组装给 AI 的上下文：Skill 摘要 + 实验数据 + 软件计算结果。"""
    parts = ["【RSM Skill（实验大脑说明书）摘要】"]
    skill = load_skill_text()
    keep = [ln for ln in skill.splitlines()
            if any(k in ln for k in ("一句话", "最容易忘", "标准流程", "不要跳", "AI 分工",
                                     "单因素", "BBD", "配液", "验证", "失拟", "混合物"))]
    parts.append("\n".join(keep[:40]))

    parts.append("【当前实验数据】")
    parts.append(f"实验名称：{exp.name}；响应值：{exp.response_name}；"
                 f"优化目标：{exp.objective}"
                 + (f"（目标值 {exp.target_value}）" if exp.objective == "target" else ""))
    for i, f in enumerate(exp.factor_list()):
        extra = ""
        if f.volume_mode == "stock" and f.stock_conc:
            extra = f"；母液 {f.stock_conc:g}"
        elif f.volume_mode == "direct":
            extra = "；按体积(μL)直接加入"
        parts.append(f"因素{chr(65 + i)}：{f.name}，范围 {f.low:g}~{f.high:g} {f.unit}"
                     f"（中心 {f.center:g}）{extra}")
    if exp.system.enabled:
        fixed = "，".join(f"{c.name} {c.volume:g}μL" for c in exp.system.fixed_list())
        parts.append(f"反应体系：总体积 {exp.system.total_volume:g}μL；固定组分 {fixed}；"
                     f"补足液 {exp.system.filler_name}；最小移液体积 {exp.system.min_pipette:g}μL")

    parts.append(f"【软件计算结果（当前阶段：{stage}）】")
    if exp.has_design():
        done = exp.n_done()
        parts.append(f"BBD 设计 {len(exp.runs)} 个实验（含 {exp.n_center} 个中心点），已完成 {done} 个。")
    if model is not None:
        sig = "、".join(t["label"] for t in model.terms if t["sig"]) or "无"
        lof = f"{model.lof_p:.3f}" if model.lof_p is not None else "不可计算"
        parts.append(
            f"二次模型：模型P={model.p_model:.4g}，R²={model.r2:.3f}，调整R²={model.adj_r2:.3f}，"
            f"预测R²={model.pred_r2:.3f}，失拟P={lof}，信噪比={model.adeq:.1f}；显著项：{sig}。")
    if optimum is not None:
        fa = exp.factor_list()
        cond = "，".join(f"{chr(65 + i)}={v:.4g}" for i, v in enumerate(optimum["actual"]))
        parts.append(f"预测最优条件：{cond}；预测响应 {optimum['yhat']:.6g}；"
                     f"配液可行性：{'通过' if optimum['feasible'] else '未通过——' + optimum['note']}")
    for v in exp.validations[-3:]:
        parts.append(f"验证记录：预测 {v.predicted:.6g} / 实测 {v.actual:.6g} / 误差 {v.error_pct:.2f}%")
    if not exp.has_design():
        parts.append("（尚未生成 BBD 设计）")
    return "\n".join(parts)


class AiPanel(QWidget):
    """主窗口右侧的 AI 面板；通过 main_window 回调读取当前状态。"""

    def __init__(self, get_state):
        super().__init__()
        self.get_state = get_state     # -> (exp, model, optimum, stage)
        self.thread: QThread | None = None
        self.worker: AiWorker | None = None
        self.history: list = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)

        self.lbl_stage = tip_label("")
        lay.addWidget(self.lbl_stage)

        grid = QGridLayout()
        grid.setSpacing(4)
        for i, q in enumerate(PRESET_QUESTIONS):
            b = QPushButton(q)
            b.setObjectName("chip")
            b.clicked.connect(lambda _=False, s=q: self.ask(s))
            grid.addWidget(b, i // 2, i % 2)
        lay.addLayout(grid)

        self.chat = QTextBrowser()
        self.chat.setReadOnly(True)
        self.chat.setOpenExternalLinks(True)
        self.chat.setStyleSheet("background:#ffffff;border:1px solid #e7eaf0;"
                                "border-radius:12px;padding:8px;")
        self.chat.setPlaceholderText("可以在这里向 AI 提问。AI 只依据：RSM Skill + 本实验数据 + "
                                     "软件计算结果回答。\n未配置 API 时，可点「内置解读」获得"
                                     "由统计结果自动生成的白话解释。")
        lay.addWidget(self.chat, 1)

        bottom = QGridLayout()
        self.ed_input = QLineEdit()
        self.ed_input.setPlaceholderText("输入问题，回车发送…")
        self.ed_input.returnPressed.connect(self.send)
        btn_send = QPushButton("发送")
        btn_send.setObjectName("primary")
        btn_send.clicked.connect(self.send)
        btn_read = QPushButton("内置解读")
        btn_read.setToolTip("不依赖 API：由软件统计结果直接生成本次模型的白话解读")
        btn_read.clicked.connect(self.builtin_interpret)
        btn_cfg = QPushButton("设置")
        btn_cfg.clicked.connect(self.open_config)
        self.lbl_busy = tip_label("")
        self.bar_busy = QProgressBar()
        self.bar_busy.setRange(0, 0)          # 不确定进度：来回滚动
        self.bar_busy.setTextVisible(False)
        self.bar_busy.setFixedHeight(6)
        self.bar_busy.hide()
        self._busy_timer = QTimer(self)
        self._busy_t0 = 0.0
        self._busy_timer.timeout.connect(self._tick_busy)
        bottom.addWidget(self.ed_input, 0, 0, 1, 2)
        bottom.addWidget(btn_send, 1, 0)
        bottom.addWidget(btn_read, 1, 1)
        bottom.addWidget(btn_cfg, 1, 2)
        bottom.addWidget(self.lbl_busy, 2, 0, 1, 3)
        lay.addWidget(self.bar_busy)
        lay.addLayout(bottom)

    # ---------- UI ----------
    def refresh_stage(self, stage: str):
        exp, model, _, _ = self.get_state()
        self.lbl_stage.setText(f"当前实验：{exp.name}　|　当前阶段：{stage}")

    def append_chat(self, who: str, text: str):
        bg = {"你": "#eef2ff", "AI": "#f8fafc", "软件": "#fffbeb"}.get(who, "#f8fafc")
        nc = {"你": "#4338ca", "AI": "#0f766e", "软件": "#b45309"}.get(who, "#374151")
        body = text.replace(chr(10), "<br>")
        self.chat.append(
            f'<table width="100%" cellspacing="0" cellpadding="8"><tr>'
            f'<td bgcolor="{bg}">'
            f'<span style="color:{nc};"><b>{who}</b></span>&nbsp;&nbsp;{body}'
            f'</td></tr></table><br>')

    # ---------- 动作 ----------
    def ask(self, question: str):
        self.ed_input.setText(question)
        self.send()

    def send(self):
        q = self.ed_input.text().strip()
        if not q:
            return
        self.append_chat("你", q)
        self.ed_input.clear()
        exp, model, optimum, stage = self.get_state()
        skill = load_skill_text()
        context = build_context(exp, model, optimum, stage)
        messages = [
            {"role": "system",
             "content": "你是响应面法（RSM/BBD）实验助手。你只能依据用户提供的"
                        "《RSM Skill》、实验数据和软件计算结果回答，不得发明统计方法或编造数值。"
                        "统计显著性等一律以给出的计算结果为准。请用中文、面向实验人员的语言回答，"
                        "简洁、直接、可操作。\n\n" + skill[:2600]},
            {"role": "user",
             "content": f"【软件上下文】\n{context}\n\n【我的问题】{q}"},
        ]
        cfg = load_config()
        self.thread = QThread(self)
        self.worker = AiWorker(cfg, messages)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.work)
        self.worker.finished.connect(self._on_reply)
        self.worker.failed.connect(self._on_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.start()
        self.ed_input.setEnabled(False)
        import time as _time
        self._busy_t0 = _time.time()
        self.bar_busy.show()
        self._busy_timer.start(1000)
        self._tick_busy()

    def _on_reply(self, text: str):
        self._done()
        self.append_chat("AI", text)

    def _on_error(self, err: str):
        self._done()
        self.append_chat("AI", f"调用失败：{err}")

    def _tick_busy(self):
        import time as _t
        sec = int(_t.time() - self._busy_t0) if self._busy_t0 else 0
        self.lbl_busy.setText(
            f"AI 正在思考… 已等待 {sec} 秒（本地模型较慢，首次可能 1~2 分钟；"
            f"统计计算均在软件本地完成，不受影响）")

    def _done(self):
        self._busy_timer.stop()
        self.bar_busy.hide()
        self.ed_input.setEnabled(True)
        self.lbl_busy.setText("")

    def builtin_interpret(self):
        from ..core.interp import interpret_model, interpret_optimum
        exp, model, optimum, stage = self.get_state()
        texts = []
        if model is not None:
            texts.append("【模型解读】\n" + interpret_model(exp, model))
        else:
            texts.append("还没有拟合模型：请先完成第三步（输入结果）并点击第四步的「拟合模型」。")
        if optimum is not None:
            texts.append("【最优条件解读】\n" + interpret_optimum(exp, optimum))
        self.append_chat("软件", "\n\n".join(texts))

    def open_config(self):
        dlg = AiConfigDialog(self)
        dlg.exec()


def make_ai_dock(get_state) -> QDockWidget:
    dock = QDockWidget("AI 实验助手")
    panel = AiPanel(get_state)
    panel.setObjectName("aiPanel")
    dock.setWidget(panel)
    dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
    dock.setMinimumWidth(380)
    return dock
