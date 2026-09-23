#!/usr/bin/env python3
"""docem GUI — Office文档 XXE/XSS Payload 注入工具图形界面"""

import os
import sys
import glob
import subprocess
import threading
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

DIR = Path(__file__).resolve().parent
PYTHON = str(DIR / "venv/bin/python")
DOCEM = str(DIR / "docem.py")
PAYLOADS_DIR = DIR / "payloads"
SAMPLES_DIR = DIR / "samples" / "marked"
MAGIC_SYMBOL = "XXCb8bBA9XX"

# ── 主题常量 ──────────────────────────────────────────────────

BG_DEEP     = "#000000"
BG_PANEL    = "#1c1c1e"
BG_CARD     = "#2c2c2e"
BG_INPUT    = "#2c2c2e"
BORDER      = "#3a3a3c"
FROST_SURF  = "#323236"
FROST_BORDER= "#3c3c3e"

ACCENT      = "#e63946"
ACCENT_DIM  = "#5a1520"
ACCENT_GLOW = "#ff1a2e"
GREEN       = "#30d158"
TEXT         = "#98989d"
TEXT_DIM     = "#636366"
TEXT_BRIGHT  = "#ffffff"

R_BTN  = 7
R_INPUT = 10
R_CARD  = 12


def _f(size, bold=False):
    return ("pingfang sc", size, "bold" if bold else "normal")


FONT_TITLE = _f(16, True)
FONT_HEAD  = _f(13, True)
FONT_BODY  = _f(12)
FONT_SMALL = _f(11)
FONT_TINY  = _f(10)
FONT_BTN   = _f(12, True)
FONT_LOG   = ("menlo", 11)


# ── 主界面 ────────────────────────────────────────────────────

class DocemGUI:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("docem — Office文档 XXE/XSS Payload 注入工具")
        self.root.geometry("800x640")
        self.root.minsize(700, 500)
        self.root.configure(fg_color=BG_DEEP)
        ctk.set_appearance_mode("dark")

        self._process = None
        self._build_ui()
        self._load_samples()
        self._load_payloads()

    def run(self):
        self.root.mainloop()

    # ── 构建 ─────────────────────────────────────────────────

    def _build_ui(self):
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self._build_topbar()
        self._build_body()
        self._build_bottom()

    def _build_topbar(self):
        bar = ctk.CTkFrame(self.root, height=48, corner_radius=0, fg_color=BG_PANEL)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)
        ctk.CTkFrame(bar, height=1, fg_color=BORDER).grid(row=1, column=0, columnspan=3, sticky="ew")

        ctk.CTkLabel(bar, text="docem", font=FONT_TITLE, text_color=ACCENT
                      ).grid(row=0, column=0, padx=(16, 0), pady=10)
        ctk.CTkLabel(bar, text="Office文档 XXE/XSS Payload 注入 v1.5",
                      font=FONT_SMALL, text_color=TEXT_DIM
                      ).grid(row=0, column=1, sticky="w", padx=8)

        self._btn_exec = ctk.CTkButton(bar, text="生成", width=80, height=34,
                                        font=FONT_BTN, corner_radius=R_BTN,
                                        fg_color=ACCENT, hover_color=ACCENT_GLOW,
                                        text_color="#ffffff", command=self._execute)
        self._btn_exec.grid(row=0, column=2, padx=(8, 4), pady=8)

        self._btn_stop = ctk.CTkButton(bar, text="停止", width=64, height=34,
                                        font=FONT_BTN, corner_radius=R_BTN,
                                        fg_color=BG_CARD, hover_color="#4a4a4e",
                                        text_color=TEXT, state="disabled",
                                        command=self._stop)
        self._btn_stop.grid(row=0, column=3, padx=(0, 14), pady=8)

    def _build_body(self):
        body = ctk.CTkFrame(self.root, corner_radius=R_CARD,
                             fg_color=FROST_SURF, border_width=1, border_color=FROST_BORDER)
        body.grid(row=1, column=0, sticky="nsew", padx=10, pady=(6, 0))
        body.grid_columnconfigure(1, weight=1)

        # 左侧标签列
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="ns", padx=(16, 0), pady=12)
        left.grid_columnconfigure(0, weight=1)

        labels = ["样本文件", "Payload 类型", "注入模式", "Payload 文件", "输出格式", "Magic Symbol"]
        for i, lbl in enumerate(labels):
            ctk.CTkLabel(left, text=lbl, font=FONT_SMALL, text_color=TEXT,
                         anchor="w", width=100).grid(row=i, column=0, pady=7, sticky="w")

        # 右侧控件列
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 16), pady=12)
        right.grid_columnconfigure(0, weight=1)

        row = 0

        # 样本选择
        sf = ctk.CTkFrame(right, fg_color="transparent")
        sf.grid(row=row, column=0, sticky="ew", pady=4); row += 1
        sf.grid_columnconfigure(0, weight=1)
        self._var_sample = ctk.StringVar()
        self._combo_sample = ctk.CTkOptionMenu(sf, variable=self._var_sample, values=[""],
                                                height=32, font=_f(11), corner_radius=R_INPUT,
                                                fg_color=BG_INPUT, button_color=ACCENT_DIM,
                                                text_color=TEXT_BRIGHT, width=360)
        self._combo_sample.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(sf, text="浏览", width=56, height=32, font=_f(11),
                       corner_radius=R_BTN, fg_color=BG_CARD, hover_color="#4a4a4e",
                       text_color=TEXT, command=self._browse_sample).grid(row=0, column=1)

        # Payload 类型
        self._var_pt = ctk.StringVar(value="xxe")
        ctk.CTkSegmentedButton(right, values=["xxe", "xss"], variable=self._var_pt,
                                font=FONT_SMALL, corner_radius=R_BTN,
                                selected_color=ACCENT_DIM, selected_hover_color=ACCENT,
                                unselected_color=BG_INPUT, unselected_hover_color=ACCENT_DIM,
                                command=self._on_pt_change
                                ).grid(row=row, column=0, sticky="w", pady=4); row += 1

        # 注入模式
        self._var_pm = ctk.StringVar(value="per_document")
        ctk.CTkSegmentedButton(right, values=["per_document", "per_file", "per_place"],
                                variable=self._var_pm,
                                font=FONT_SMALL, corner_radius=R_BTN,
                                selected_color=ACCENT_DIM, selected_hover_color=ACCENT,
                                unselected_color=BG_INPUT, unselected_hover_color=ACCENT_DIM
                                ).grid(row=row, column=0, sticky="w", pady=4); row += 1

        # Payload 文件选择
        pf = ctk.CTkFrame(right, fg_color="transparent")
        pf.grid(row=row, column=0, sticky="ew", pady=4); row += 1
        pf.grid_columnconfigure(0, weight=1)
        self._var_payload = ctk.StringVar()
        self._combo_payload = ctk.CTkOptionMenu(pf, variable=self._var_payload, values=[""],
                                                 height=32, font=_f(11), corner_radius=R_INPUT,
                                                 fg_color=BG_INPUT, button_color=ACCENT_DIM,
                                                 text_color=TEXT_BRIGHT, width=360)
        self._combo_payload.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(pf, text="浏览", width=56, height=32, font=_f(11),
                       corner_radius=R_BTN, fg_color=BG_CARD, hover_color="#4a4a4e",
                       text_color=TEXT, command=self._browse_payload).grid(row=0, column=1)

        # 输出格式
        self._var_sx = ctk.StringVar(value="docx")
        ctk.CTkSegmentedButton(right, values=["docx", "xlsx", "pptx", "odt"],
                                variable=self._var_sx,
                                font=FONT_SMALL, corner_radius=R_BTN,
                                selected_color=ACCENT_DIM, selected_hover_color=ACCENT,
                                unselected_color=BG_INPUT, unselected_hover_color=ACCENT_DIM
                                ).grid(row=row, column=0, sticky="w", pady=4); row += 1

        # Magic symbol (只读)
        ctk.CTkLabel(right, text=MAGIC_SYMBOL, font=_f(12), text_color=GREEN,
                      anchor="w").grid(row=row, column=0, sticky="w", pady=4); row += 1

        # 输出目录
        of = ctk.CTkFrame(right, fg_color="transparent")
        of.grid(row=row, column=0, sticky="ew", pady=4); row += 1
        of.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(of, text="输出目录:", font=FONT_TINY, text_color=TEXT_DIM,
                      anchor="w").pack(side="left", padx=(0, 4))
        ctk.CTkLabel(of, text=str(DIR / "tmp"), font=FONT_TINY, text_color=TEXT,
                      anchor="w").pack(side="left")

    def _build_bottom(self):
        bot = ctk.CTkFrame(self.root, height=180, corner_radius=R_CARD,
                            fg_color=FROST_SURF, border_width=1, border_color=FROST_BORDER)
        bot.grid(row=2, column=0, sticky="ew", padx=10, pady=(6, 10))
        bot.grid_columnconfigure(0, weight=1)
        bot.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(bot, text="输出", font=_f(11, True), text_color=ACCENT
                      ).grid(row=0, column=0, padx=12, pady=(8, 2), sticky="w")

        self._log = ctk.CTkTextbox(bot, font=FONT_LOG, corner_radius=0,
                                    fg_color="transparent", wrap="word", text_color=GREEN)
        self._log.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._log.configure(state="disabled")

    # ── 数据加载 ─────────────────────────────────────────────

    def _load_samples(self):
        samples = []
        if SAMPLES_DIR.exists():
            for p in sorted(SAMPLES_DIR.iterdir()):
                rel = str(p.relative_to(DIR))
                if p.is_dir() or p.suffix in (".docx", ".xlsx", ".pptx", ".odt"):
                    samples.append(rel)
        self._combo_sample.configure(values=samples if samples else ["(无内置样本)"])
        if samples:
            self._var_sample.set(samples[0])

    def _load_payloads(self):
        pt = self._var_pt.get()
        payloads = []
        if PAYLOADS_DIR.exists():
            for p in sorted(PAYLOADS_DIR.glob(f"*{pt}*")):
                payloads.append(str(p.relative_to(DIR)))
            if not payloads:
                for p in sorted(PAYLOADS_DIR.glob("*")):
                    payloads.append(str(p.relative_to(DIR)))
        self._combo_payload.configure(values=payloads if payloads else ["(无payload文件)"])
        if payloads:
            self._var_payload.set(payloads[0])

    def _on_pt_change(self, value):
        self._load_payloads()

    # ── 浏览 ─────────────────────────────────────────────────

    def _browse_sample(self):
        fp = filedialog.askopenfilename(
            title="选择样本文件", initialdir=str(DIR / "samples"),
            filetypes=[("Office文档", "*.docx *.xlsx *.pptx *.odt"), ("所有文件", "*.*")])
        if fp:
            try:
                self._var_sample.set(str(Path(fp).relative_to(DIR)))
            except ValueError:
                self._var_sample.set(fp)

    def _browse_payload(self):
        fp = filedialog.askopenfilename(
            title="选择Payload文件", initialdir=str(PAYLOADS_DIR),
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")])
        if fp:
            try:
                self._var_payload.set(str(Path(fp).relative_to(DIR)))
            except ValueError:
                self._var_payload.set(fp)

    # ── 执行 ─────────────────────────────────────────────────

    def _log_append(self, text):
        self._log.configure(state="normal")
        self._log.insert("end", text)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _execute(self):
        sample = self._var_sample.get().strip()
        pt = self._var_pt.get()
        pm = self._var_pm.get()
        pf = self._var_payload.get().strip()
        sx = self._var_sx.get()

        if not sample:
            messagebox.showwarning("提示", "请选择样本文件")
            return

        sample_path = str(DIR / sample) if not os.path.isabs(sample) else sample
        payload_path = str(DIR / pf) if not os.path.isabs(pf) else pf

        if not os.path.exists(sample_path):
            messagebox.showerror("错误", f"样本文件不存在:\n{sample_path}")
            return
        if not os.path.exists(payload_path):
            messagebox.showerror("错误", f"Payload文件不存在:\n{payload_path}")
            return

        cmd = [PYTHON, DOCEM, "-s", sample_path, "-pt", pt,
               "-pf", payload_path, "-pm", pm, "-sx", sx]

        self._log_append(f"$ {' '.join(cmd)}\n\n")
        self._btn_exec.configure(state="disabled")
        self._btn_stop.configure(state="normal")

        def _run():
            try:
                self._process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    bufsize=1, encoding="utf-8", errors="replace", cwd=str(DIR))
                for line in self._process.stdout:
                    # 跳过交互确认提示，自动继续
                    if "Continue?(y/n)" in line:
                        self._process.stdin.write("y\n")
                        self._process.stdin.flush()
                        self.root.after(0, lambda l=line: self._log_append(l))
                        continue
                    self.root.after(0, lambda l=line: self._log_append(l))
                self._process.wait()
                rc = self._process.returncode
                self.root.after(0, lambda: self._log_append(f"\n[Exit code: {rc}]\n"))
                self.root.after(0, lambda: self._log_append(f"\n输出目录: {DIR / 'tmp'}\n\n"))
            except Exception as e:
                self.root.after(0, lambda: self._log_append(f"[错误] {e}\n"))
            finally:
                self._process = None
                self.root.after(0, self._on_done)

        threading.Thread(target=_run, daemon=True).start()

    def _stop(self):
        if self._process:
            self._process.terminate()
            self._log_append("\n[已终止]\n")

    def _on_done(self):
        self._btn_exec.configure(state="normal")
        self._btn_stop.configure(state="disabled")


if __name__ == "__main__":
    app = DocemGUI()
    app.run()
