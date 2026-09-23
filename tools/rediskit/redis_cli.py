#!/usr/bin/env python3
"""Unified Redis launcher for RedisEXP and Redis综合利用."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
TOOLS_DIR = BASE_DIR.parent
REDISEXP_DIR = TOOLS_DIR / "RedisEXP"
REDISTOOLS_DIR = TOOLS_DIR / "redis_tools_GUI"
REDISEXP_BIN = REDISEXP_DIR / "RedisEXP"
REDISTOOLS_PY = REDISTOOLS_DIR / "venv" / "bin" / "python"

HELP = """\
Redis工具 - RedisEXP + Redis综合利用 统一入口

用法:
  geshell redis exp [RedisEXP参数...]
  geshell redis tools
  geshell redis gui

模式:
  exp     RedisEXP CLI/二进制，适合脚本化调用
  tools   Redis综合利用GUI，含密码爆破、CLI控制台、写WebShell/SSH/Cron、CVE-2022-0543
  gui     同 tools

示例:
  geshell redis exp -h
  geshell redis tools
"""


def _run(cmd: list[str], cwd: Path) -> int:
    print("[Redis] " + " ".join(str(x) for x in cmd), file=sys.stderr)
    return subprocess.run(cmd, cwd=str(cwd)).returncode


def _exp(args: list[str]) -> int:
    if not args:
        args = ["-h"]
    return _run([str(REDISEXP_BIN), *args], REDISEXP_DIR)


def _tools(_args: list[str]) -> int:
    return _run([str(REDISTOOLS_PY), "redis_tools.py"], REDISTOOLS_DIR)


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(HELP)
        return 0
    mode, rest = argv[0].lower(), argv[1:]
    if mode in {"exp", "redisexp"}:
        return _exp(rest)
    if mode in {"tools", "tool", "gui", "综合"}:
        return _tools(rest)
    print(f"[错误] 未知模式: {argv[0]}", file=sys.stderr)
    print(HELP, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
