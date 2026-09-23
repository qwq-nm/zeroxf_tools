#!/usr/bin/env python3
"""Small GUI chooser for RedisEXP and Redis综合利用."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import ttk


BASE_DIR = Path(__file__).resolve().parent
TOOLS_DIR = BASE_DIR.parent
REDISEXP_DIR = TOOLS_DIR / "RedisEXP"
REDISTOOLS_DIR = TOOLS_DIR / "redis_tools_GUI"
REDISEXP_PY = REDISEXP_DIR / "../../venv/bin/python"
REDISTOOLS_PY = REDISTOOLS_DIR / "venv" / "bin" / "python"
THIS_PY = Path(sys.executable)


def open_terminal(command: str) -> None:
    fd, path = tempfile.mkstemp(prefix="redis_", suffix=".command")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n")
        f.write(command + "\n")
        f.write("echo\nread -n 1 -s -r -p '按任意键关闭...'\n")
    os.chmod(path, 0o755)
    subprocess.run(["open", "-a", "Terminal", path], check=False)


class RedisLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Redis工具")
        self.root.geometry("560x240")
        self.root.resizable(False, False)
        self.host = tk.StringVar(value="127.0.0.1")
        self.port = tk.StringVar(value="6379")
        self.password = tk.StringVar()
        self.status = tk.StringVar(value="就绪")
        self._build()

    def run(self):
        self.root.mainloop()

    def _build(self):
        frame = ttk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=14, pady=14)
        frame.columnconfigure(1, weight=1)
        pad = {"padx": 8, "pady": 6}

        ttk.Label(frame, text="Redis 统一入口", font=("Arial", 16, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", **pad
        )
        ttk.Label(frame, text="RedisEXP 偏脚本化，Redis综合利用 GUI 功能更完整。").grid(
            row=1, column=0, columnspan=4, sticky="w", **pad
        )

        ttk.Label(frame, text="目标").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.host, width=18).grid(row=2, column=1, sticky="ew", **pad)
        ttk.Label(frame, text="端口").grid(row=2, column=2, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.port, width=8).grid(row=2, column=3, sticky="ew", **pad)

        ttk.Label(frame, text="密码").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.password, show="*").grid(row=3, column=1, columnspan=3, sticky="ew", **pad)

        ttk.Button(frame, text="Redis综合利用 GUI", command=self.redis_tools).grid(row=4, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Button(frame, text="RedisEXP GUI", command=self.redis_exp_gui).grid(row=4, column=2, sticky="ew", **pad)
        ttk.Button(frame, text="RedisEXP CLI", command=self.redis_exp_cli).grid(row=4, column=3, sticky="ew", **pad)
        ttk.Label(frame, textvariable=self.status).grid(row=5, column=0, columnspan=4, sticky="w", **pad)

    def redis_tools(self):
        subprocess.Popen(
            [str(REDISTOOLS_PY), "redis_tools.py"],
            cwd=str(REDISTOOLS_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.status.set("Redis综合利用 GUI 已启动")

    def redis_exp_gui(self):
        subprocess.Popen(
            [str((REDISEXP_DIR / "../../venv/bin/python").resolve()), "redis_exp_gui.py"],
            cwd=str(REDISEXP_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.status.set("RedisEXP GUI 已启动")

    def redis_exp_cli(self):
        args = ["exp"]
        command = f"cd '{BASE_DIR}' && '{THIS_PY}' redis_cli.py {' '.join(map(repr, args))}"
        open_terminal(command)
        self.status.set("RedisEXP CLI 已在终端打开")


if __name__ == "__main__":
    RedisLauncher().run()
