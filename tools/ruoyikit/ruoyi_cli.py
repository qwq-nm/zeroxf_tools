#!/usr/bin/env python3
"""Unified CLI for RuoYi tools."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
RUOYI_DIR = PROJECT_ROOT / "重点系统" / "ruoyi"
JAR_LAUNCHER = PROJECT_ROOT / "lib" / "launch_jar.py"
THIS_PY = Path(sys.executable)


HELP = """\
若依工具 - 统一入口

用法:
  geshell ruoyi scan
  geshell ruoyi all
  geshell ruoyi exploit

模式:
  scan     启动 ruoyi-vue-scanner.jar
  all      启动 Ruoyi-All-1.0-SNAPSHOT.jar
  exploit  启动 RuoYiExploitGUI_v1.0.jar

示例:
  geshell ruoyi scan
  geshell ruoyi all
  geshell ruoyi exploit
"""


def _run_jar(jar: str, jdk: str) -> int:
    cmd = [str(THIS_PY), str(JAR_LAUNCHER), "--cwd", str(RUOYI_DIR), "--jar", jar, "--jdk", jdk]
    print("[RuoYi] " + " ".join(cmd), file=sys.stderr)
    return subprocess.run(cmd, cwd=str(PROJECT_ROOT)).returncode


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(HELP)
        return 0
    mode = argv[0].lower()
    if mode in {"scan", "scanner", "ruoyi"}:
        return _run_jar("ruoyi-vue-scanner.jar", "jdk17")
    if mode in {"all", "combo", "ruoyi-all"}:
        return _run_jar("Ruoyi-All-1.0-SNAPSHOT.jar", "jdk8")
    if mode in {"exploit", "gui", "exp"}:
        return _run_jar("RuoYiExploitGUI_v1.0.jar", "jdk8")
    print(f"[错误] 未知模式: {argv[0]}", file=sys.stderr)
    print(HELP, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
