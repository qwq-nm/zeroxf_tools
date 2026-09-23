#!/usr/bin/env python3
"""Unified CLI for Spring ecosystem tools."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
SPRING_SCAN_DIR = PROJECT_ROOT / "组件框架" / "Spring_Scan"
SPRINGBOOT_DIR = PROJECT_ROOT / "组件框架" / "SpringBoot-Scan"
CLOUDSEC_DIR = PROJECT_ROOT / "重点系统" / "cloudSec"
CLOUDCAT_DIR = PROJECT_ROOT / "重点系统" / "cloudcat"
JAR_LAUNCHER = PROJECT_ROOT / "lib" / "launch_jar.py"
THIS_PY = Path(sys.executable)
SPRINGBOOT_PY = SPRINGBOOT_DIR / "venv" / "bin" / "python"


HELP = """\
Spring工具 - 统一入口

用法:
  geshell spring scan
  geshell spring boot [SpringBoot-Scan参数...]
  geshell spring cloudsec
  geshell spring cloudcat

模式:
  scan      启动 Spring Scan JAR
  boot      运行 SpringBoot-Scan CLI
  cloudsec  启动 CloudSec JAR
  cloudcat  启动 CloudCat JAR

示例:
  geshell spring boot -u http://target:8080
  geshell spring scan
"""


def _run_jar(cwd: Path, jar: str, jdk: str) -> int:
    cmd = [str(THIS_PY), str(JAR_LAUNCHER), "--cwd", str(cwd), "--jar", jar, "--jdk", jdk]
    print("[Spring] " + " ".join(cmd), file=sys.stderr)
    return subprocess.run(cmd, cwd=str(PROJECT_ROOT)).returncode


def _boot(args: list[str]) -> int:
    if not args:
        args = ["--help"]
    cmd = [str(SPRINGBOOT_PY), "SpringBoot-Scan.py", *args]
    print("[Spring] " + " ".join(cmd), file=sys.stderr)
    return subprocess.run(cmd, cwd=str(SPRINGBOOT_DIR)).returncode


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(HELP)
        return 0
    mode, rest = argv[0].lower(), argv[1:]
    if mode in {"scan", "springscan"}:
        return _run_jar(SPRING_SCAN_DIR, "YYBaby_v1.0_Spring_Scan.jar", "jdk8")
    if mode in {"boot", "springboot", "springboot-scan", "springbootscan"}:
        return _boot(rest)
    if mode in {"cloudsec", "sec"}:
        return _run_jar(CLOUDSEC_DIR, "cloudSec-1.2.2-SNAPSHOT.jar", "jdk8")
    if mode in {"cloudcat", "cat"}:
        return _run_jar(CLOUDCAT_DIR, "CloudCat-1.7-jar-with-dependencies.jar", "jdk8")
    print(f"[错误] 未知模式: {argv[0]}", file=sys.stderr)
    print(HELP, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
