#!/usr/bin/env python3
"""Unified SSTI launcher for Fenjing and SSTImap."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
TOOLS_DIR = BASE_DIR.parent
FENJING_DIR = TOOLS_DIR / "Fenjing"
SSTIMAP_DIR = TOOLS_DIR / "SSTImap"
FENJING_PY = FENJING_DIR / "venv" / "bin" / "python"
SSTIMAP_PY = SSTIMAP_DIR / "venv" / "bin" / "python"


HELP = """\
SSTI工具 - Fenjing + SSTImap 统一入口

用法:
  geshell ssti fenjing [Fenjing参数...]
  geshell ssti sstimap [SSTImap参数...]
  geshell ssti auto -u http://target/?name=test [通用参数...]

模式:
  fenjing   Jinja2 SSTI / WAF绕过，适合CTF和Jinja专项
  sstimap   通用模板引擎SSTI检测与利用，适合多引擎兜底
  auto      先运行 Fenjing scan，失败后用 SSTImap 对同一URL检测

示例:
  geshell ssti fenjing scan --url http://target/
  geshell ssti sstimap -u 'http://target/?name=test'
  geshell ssti auto -u 'http://target/?name=test' --proxy http://127.0.0.1:8080
"""


def _run(cmd: list[str], cwd: Path) -> int:
    printable = " ".join(str(x) for x in cmd)
    print(f"[SSTI] {printable}", file=sys.stderr)
    return subprocess.run(cmd, cwd=str(cwd)).returncode


def _fenjing(args: list[str]) -> int:
    if not args:
        args = ["--help"]
    return _run([str(FENJING_PY), "fenjing_cli.py", *args], FENJING_DIR)


def _sstimap(args: list[str]) -> int:
    if not args:
        args = ["--help"]
    return _run([str(SSTIMAP_PY), "sstimap.py", *args], SSTIMAP_DIR)


def _extract_option(args: list[str], *names: str) -> str | None:
    for i, arg in enumerate(args):
        for name in names:
            if arg == name and i + 1 < len(args):
                return args[i + 1]
            if arg.startswith(name + "="):
                return arg.split("=", 1)[1]
    return None


def _sstimap_auto_args(args: list[str]) -> list[str]:
    url = _extract_option(args, "-u", "--url")
    if not url:
        raise ValueError("auto 模式需要 -u/--url")

    mapped = ["-u", url]
    proxy = _extract_option(args, "-p", "--proxy")
    if proxy:
        mapped += ["-p", proxy]

    headers = []
    for i, arg in enumerate(args):
        if arg in ("-H", "--header") and i + 1 < len(args):
            headers.append(args[i + 1])
        elif arg.startswith("--header="):
            headers.append(arg.split("=", 1)[1])
    for header in headers:
        mapped += ["-H", header]

    cookies = []
    for i, arg in enumerate(args):
        if arg in ("-C", "--cookie", "--cookies") and i + 1 < len(args):
            cookies.append(args[i + 1])
        elif arg.startswith("--cookies=") or arg.startswith("--cookie="):
            cookies.append(arg.split("=", 1)[1])
    for cookie in cookies:
        mapped += ["-C", cookie]

    return mapped


def _auto(args: list[str]) -> int:
    try:
        sstimap_args = _sstimap_auto_args(args)
    except ValueError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        print(HELP, file=sys.stderr)
        return 2

    fenjing_args = ["scan", *args]
    rc = _fenjing(fenjing_args)
    if rc == 0:
        return 0
    print("[SSTI] Fenjing 未成功，切换到 SSTImap 通用检测。", file=sys.stderr)
    return _sstimap(sstimap_args)


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(HELP)
        return 0
    mode, rest = argv[0].lower(), argv[1:]
    if mode in {"fenjing", "fj", "jinja"}:
        return _fenjing(rest)
    if mode in {"sstimap", "map", "generic"}:
        return _sstimap(rest)
    if mode in {"auto", "scan"}:
        return _auto(rest)
    print(f"[错误] 未知模式: {argv[0]}", file=sys.stderr)
    print(HELP, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
