#!/usr/bin/env python3
"""Compact GUI launcher for merged Spring tools."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import ttk


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
SPRING_SCAN_DIR = PROJECT_ROOT / "组件框架" / "Spring_Scan"
SPRINGBOOT_DIR = PROJECT_ROOT / "组件框架" / "SpringBoot-Scan"
CLOUDSEC_DIR = PROJECT_ROOT / "重点系统" / "cloudSec"
CLOUDCAT_DIR = PROJECT_ROOT / "重点系统" / "cloudcat"
JAR_LAUNCHER = PROJECT_ROOT / "lib" / "launch_jar.py"
THIS_PY = Path(sys.executable)
SPRINGBOOT_PY = SPRINGBOOT_DIR / "venv" / "bin" / "python"


def open_terminal(command: str) -> None:
    fd, path = tempfile.mkstemp(prefix="spring_", suffix=".command")
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        file.write("#!/bin/bash\n")
        file.write(command + "\n")
        file.write("echo\nread -n 1 -s -r -p '按任意键关闭...'\n")
    os.chmod(path, 0o755)
    subprocess.run(["open", "-a", "Terminal", path], check=False)


class SpringLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Spring工具")
        self.root.geometry("620x280")
        self.root.resizable(False, False)
        self.url = tk.StringVar()
        self.proxy = tk.StringVar()
        self.status = tk.StringVar(value="就绪")
        self._build()

    def _build(self):
        frame = ttk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=14, pady=14)
        pad = {"padx": 8, "pady": 6}

        ttk.Label(frame, text="Spring 统一入口", font=("Arial", 16, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", **pad
        )
        ttk.Label(frame, text="合并 Spring Scan、SpringBoot-Scan、CloudSec、CloudCat。").grid(
            row=1, column=0, columnspan=4, sticky="w", **pad
        )

        ttk.Label(frame, text="目标URL").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.url).grid(row=2, column=1, columnspan=3, sticky="ew", **pad)

        ttk.Label(frame, text="代理").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(frame, textvariable=self.proxy).grid(row=3, column=1, columnspan=3, sticky="ew", **pad)

        ttk.Button(frame, text="Spring Scan", command=lambda: self._launch_jar(SPRING_SCAN_DIR, "YYBaby_v1.0_Spring_Scan.jar", "jdk8", "Spring Scan")).grid(
            row=4, column=0, sticky="ew", **pad
        )
        ttk.Button(frame, text="SpringBoot CLI", command=self._springboot_cli).grid(
            row=4, column=1, sticky="ew", **pad
        )
        ttk.Button(frame, text="CloudSec", command=lambda: self._launch_jar(CLOUDSEC_DIR, "cloudSec-1.2.2-SNAPSHOT.jar", "jdk8", "CloudSec")).grid(
            row=4, column=2, sticky="ew", **pad
        )
        ttk.Button(frame, text="CloudCat", command=lambda: self._launch_jar(CLOUDCAT_DIR, "CloudCat-1.7-jar-with-dependencies.jar", "jdk8", "CloudCat")).grid(
            row=4, column=3, sticky="ew", **pad
        )

        ttk.Label(frame, textvariable=self.status).grid(row=5, column=0, columnspan=4, sticky="w", **pad)
        for idx in range(4):
            frame.columnconfigure(idx, weight=1)

    def _launch_jar(self, cwd: Path, jar: str, jdk: str, label: str):
        subprocess.Popen(
            [str(THIS_PY), str(JAR_LAUNCHER), "--cwd", str(cwd), "--jar", jar, "--jdk", jdk],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.status.set(f"{label} 正在启动")

    def _springboot_cli(self):
        args = []
        url = self.url.get().strip()
        proxy = self.proxy.get().strip()
        if url:
            args += ["-u", url]
        if proxy:
            args += ["-p", proxy]
        if not args:
            args = ["--help"]
        command = (
            f"cd {shlex.quote(str(SPRINGBOOT_DIR))} && "
            f"source {shlex.quote(str(SPRINGBOOT_DIR / 'venv' / 'bin' / 'activate'))} && "
            f"{shlex.quote(str(SPRINGBOOT_PY))} SpringBoot-Scan.py "
            + " ".join(shlex.quote(arg) for arg in args)
        )
        open_terminal(command)
        self.status.set("SpringBoot-Scan CLI 已在终端打开")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    SpringLauncher().run()
