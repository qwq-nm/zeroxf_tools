#!/usr/bin/env python3
"""Compact GUI launcher for merged RuoYi tools."""

from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
RUOYI_DIR = PROJECT_ROOT / "重点系统" / "ruoyi"
JAR_LAUNCHER = PROJECT_ROOT / "lib" / "launch_jar.py"
THIS_PY = Path(sys.executable)


class RuoYiLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("若依工具")
        self.root.geometry("560x240")
        self.root.resizable(False, False)
        self.status = tk.StringVar(value="就绪")
        self._build()

    def _build(self):
        frame = ttk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=14, pady=14)
        pad = {"padx": 8, "pady": 6}

        ttk.Label(frame, text="若依统一入口", font=("Arial", 16, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", **pad
        )
        ttk.Label(frame, text="合并扫描器、综合利用和专用 GUI，避免工具箱里重复展示。").grid(
            row=1, column=0, columnspan=3, sticky="w", **pad
        )

        ttk.Button(frame, text="若依扫描器", command=lambda: self._launch("ruoyi-vue-scanner.jar", "jdk17", "若依扫描器")).grid(
            row=2, column=0, sticky="ew", **pad
        )
        ttk.Button(frame, text="Ruoyi-All", command=lambda: self._launch("Ruoyi-All-1.0-SNAPSHOT.jar", "jdk8", "Ruoyi-All")).grid(
            row=2, column=1, sticky="ew", **pad
        )
        ttk.Button(frame, text="利用 GUI", command=lambda: self._launch("RuoYiExploitGUI_v1.0.jar", "jdk8", "若依利用 GUI")).grid(
            row=2, column=2, sticky="ew", **pad
        )

        ttk.Label(frame, textvariable=self.status).grid(row=3, column=0, columnspan=3, sticky="w", **pad)
        for idx in range(3):
            frame.columnconfigure(idx, weight=1)

    def _launch(self, jar: str, jdk: str, label: str):
        subprocess.Popen(
            [str(THIS_PY), str(JAR_LAUNCHER), "--cwd", str(RUOYI_DIR), "--jar", jar, "--jdk", jdk],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.status.set(f"{label} 正在启动")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    RuoYiLauncher().run()
