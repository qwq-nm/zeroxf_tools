#!/usr/bin/env python3
"""Small GUI for choosing Fenjing, SSTImap, or auto SSTI mode."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


BASE_DIR = Path(__file__).resolve().parent
TOOLS_DIR = BASE_DIR.parent
FENJING_DIR = TOOLS_DIR / "Fenjing"
SSTIMAP_DIR = TOOLS_DIR / "SSTImap"
FENJING_PY = FENJING_DIR / "venv" / "bin" / "python"
SSTIMAP_PY = SSTIMAP_DIR / "venv" / "bin" / "python"
THIS_PY = Path(sys.executable)


def open_terminal(command: str) -> None:
    fd, path = tempfile.mkstemp(prefix="ssti_", suffix=".command")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n")
        f.write(command)
        f.write("\n")
        f.write("echo\nread -n 1 -s -r -p '按任意键关闭...'\n")
    os.chmod(path, 0o755)
    subprocess.run(["open", "-a", "Terminal", path], check=False)


class SSTILauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SSTI工具")
        self.root.geometry("560x300")
        self.root.resizable(False, False)

        self.url = tk.StringVar()
        self.proxy = tk.StringVar()
        self.status = tk.StringVar(value="就绪")

        self._build()

    def run(self):
        self.root.mainloop()

    def _build(self):
        pad = {"padx": 14, "pady": 6}
        frame = ttk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="SSTI 统一入口", font=("Arial", 16, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", **pad
        )
        ttk.Label(frame, text="Fenjing 适合 Jinja/WAF，SSTImap 适合通用模板引擎兜底。").grid(
            row=1, column=0, columnspan=3, sticky="w", **pad
        )

        ttk.Label(frame, text="目标URL").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.url).grid(row=2, column=1, columnspan=2, sticky="ew", **pad)

        ttk.Label(frame, text="代理").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.proxy).grid(row=3, column=1, columnspan=2, sticky="ew", **pad)

        ttk.Button(frame, text="Fenjing WebUI", command=self.fenjing_webui).grid(
            row=4, column=0, sticky="ew", **pad
        )
        ttk.Button(frame, text="SSTImap 终端", command=self.sstimap_terminal).grid(
            row=4, column=1, sticky="ew", **pad
        )
        ttk.Button(frame, text="自动模式", command=self.auto_mode).grid(
            row=4, column=2, sticky="ew", **pad
        )

        ttk.Label(frame, text="自动模式会先运行 Fenjing scan，失败后切换 SSTImap。").grid(
            row=5, column=0, columnspan=3, sticky="w", **pad
        )
        ttk.Label(frame, textvariable=self.status).grid(row=6, column=0, columnspan=3, sticky="w", **pad)

    def fenjing_webui(self):
        subprocess.Popen(
            [str(FENJING_PY), "fenjing_gui.py"],
            cwd=str(FENJING_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.status.set("Fenjing WebUI 正在启动")

    def sstimap_terminal(self):
        url = self.url.get().strip()
        proxy = self.proxy.get().strip()
        args = []
        if url:
            args += ["-u", url]
        if proxy:
            args += ["-p", proxy]
        command = f"cd '{SSTIMAP_DIR}' && '{SSTIMAP_PY}' sstimap.py {' '.join(map(repr, args))}"
        open_terminal(command)
        self.status.set("SSTImap 终端已打开")

    def auto_mode(self):
        url = self.url.get().strip()
        if not url:
            messagebox.showwarning("缺少目标", "自动模式需要填写目标URL。")
            return
        proxy = self.proxy.get().strip()
        args = ["auto", "-u", url]
        if proxy:
            args += ["--proxy", proxy]
        command = f"cd '{BASE_DIR}' && '{THIS_PY}' ssti_cli.py {' '.join(map(repr, args))}"
        open_terminal(command)
        self.status.set("自动模式已在终端打开")


if __name__ == "__main__":
    SSTILauncher().run()
