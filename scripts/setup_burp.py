#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Burp Suite 接入 Claude Code 的 MCP —— 一键「发现 + 接线」。

Burp 是 PortSwigger 的商业软件，其二进制不适合随本仓库分发（体积 + 授权），
所以本脚本只做「发现与接线」，Burp 本体需要你自己准备：

  1. 探测 Burp 安装位置（多个候选路径，支持 Windows 与 WSL 两端运行）
  2. 定位 Burp MCP 扩展自动释放的 proxy jar
  3. 检查 Java 版本（Burp 2026.x 需要 Java 21+）
  4. 修正绿色版启动脚本，让它用正确的 JDK
     （踩坑点：系统 PATH 里常有旧 JDK 8，Burp 会起不来或闪退）
  5. 生成 MCP 配置写入 ~/.claude.json（自动识别两端差异）
  6. 实连验证：跑一次 tools/list，报告拿到多少个工具

用法：
  python3 scripts/setup_burp.py                     # 自动探测并配置
  python3 scripts/setup_burp.py --burp-dir <路径>   # 手动指定 Burp 目录
  python3 scripts/setup_burp.py --print-only        # 只打印配置，不写入
  python3 scripts/setup_burp.py --verify-only       # 只做连通性验证
"""
import argparse
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAUDE_JSON = os.path.expanduser("~/.claude.json")
MCP_NAME = "burp"
DEFAULT_SSE = "http://127.0.0.1:9876"

IS_WSL = "microsoft" in platform.uname().release.lower()


def _c(text, code):
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text


def ok(msg):    print(_c("  ✓ ", "32") + msg)
def warn(msg):  print(_c("  ! ", "33") + msg)
def bad(msg):   print(_c("  ✗ ", "31") + msg)
def info(msg):  print("    " + msg)


# ---------- 路径工具 ----------

def win_users_dir():
    """返回 Windows 用户目录在两种环境下的可访问路径。"""
    if os.name == "nt":
        return os.environ.get("USERPROFILE", "")
    # WSL：/mnt/c/Users/<名>
    for m in glob.glob("/mnt/c/Users/*"):
        name = os.path.basename(m)
        if name.lower() in ("public", "default", "default user", "all users"):
            continue
        if os.path.isdir(os.path.join(m, "AppData")):
            return m
    return ""


def to_win_path(p):
    """把 /mnt/c/... 转成 C:\\...；已是 Windows 路径则原样返回。"""
    if not p:
        return p
    if os.name == "nt":
        return p
    m = re.match(r"^/mnt/([a-zA-Z])/(.*)$", p)
    if m:
        return f"{m.group(1).upper()}:\\" + m.group(2).replace("/", "\\")
    return p


# ---------- 探测 ----------

def find_burp(user_dir=None):
    """在常见位置寻找 Burp 安装目录，返回 (目录, burp jar 路径)。"""
    cands = []

    if os.name == "nt":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        cands += [
            os.path.join(pf, "BurpSuitePro"),
            os.path.join(pf, "BurpSuiteCommunity"),
        ]
        for drive in ("C", "D", "E", "F"):
            cands += glob.glob(rf"{drive}:\*\BurpSuite*")
            cands += glob.glob(rf"{drive}:\*\*\BurpSuite*")
            cands += glob.glob(rf"{drive}:\*\*\*\BurpSuite*")
    else:
        ud = user_dir or win_users_dir()
        base = os.path.dirname(ud) if ud else ""
        for drive in ("c", "d", "e", "f"):
            cands += glob.glob(f"/mnt/{drive}/*/BurpSuite*")
            cands += glob.glob(f"/mnt/{drive}/*/*/BurpSuite*")
            cands += glob.glob(f"/mnt/{drive}/*/*/*/BurpSuite*")
        if base:
            pass

    # 在这些目录（含子目录）里找 burpsuite_pro*.jar
    for d in cands:
        if not os.path.isdir(d):
            continue
        jars = glob.glob(os.path.join(d, "burpsuite_pro*.jar"))
        jars += glob.glob(os.path.join(d, "*", "burpsuite_pro*.jar"))
        if jars:
            return d, jars[0]
    return None, None


def find_proxy_jar(user_dir=None):
    """定位 Burp MCP 扩展释放的 proxy jar。"""
    ud = user_dir or win_users_dir()
    if ud:
        p = os.path.join(ud, "AppData", "Roaming", "BurpSuite",
                         "mcp-proxy", "mcp-proxy-all.jar")
        if os.path.exists(p):
            return p
    # Windows 原生
    if os.name == "nt":
        p = os.path.join(os.environ.get("APPDATA", ""), "BurpSuite",
                         "mcp-proxy", "mcp-proxy-all.jar")
        if os.path.exists(p):
            return p
    return None


def find_java(min_ver=21):
    """找一个版本 >= min_ver 的 Java（Windows 侧优先）。返回 (exe, 版本)。"""
    cands = []
    if os.name == "nt":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        cands += glob.glob(os.path.join(pf, "Java", "jdk-*", "bin", "java.exe"))
        cands += glob.glob(os.path.join(pf, "Java", "jdk*", "bin", "java.exe"))
        cands.append(shutil.which("java"))
    else:
        # WSL：优先 Windows 侧的 JDK（因为 Burp 在 Windows 跑）
        cands += glob.glob("/mnt/c/Program Files/Java/jdk-*/bin/java.exe")
        cands += glob.glob("/mnt/*/java/bin/java.exe")
        cands.append(shutil.which("java"))

    for exe in cands:
        if not exe or not os.path.exists(exe):
            continue
        try:
            r = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=30)
            out = (r.stderr or "") + (r.stdout or "")
            m = re.search(r'version "(\d+)', out)
            if m and int(m.group(1)) >= min_ver:
                return exe, m.group(1)
        except Exception:
            continue
    return None, None


# ---------- 修正绿色版启动脚本 ----------

def fix_launcher(burp_dir, java_exe):
    """把绿色版启动脚本里的 PATH 指向可用 JDK。

    背景：这类绿色包的 .bat 直接调用裸命令 javaw.exe，而系统 PATH 里往往
    是旧版 JDK（如 8），Burp 2026.x 需要 21+，于是双击没反应或闪退。
    这里在脚本开头注入 JAVA_HOME/PATH，不改系统环境。
    """
    if not java_exe:
        return False

    java_bin = os.path.dirname(java_exe)
    java_home = os.path.dirname(java_bin)

    # Windows 形式的目标目录（供 .bat 使用）
    jh_win = to_win_path(java_home)

    targets = []
    for pat in ("BurpSuitePro*.bat", "burpsuitePro*.bat", "*.bat"):
        targets += glob.glob(os.path.join(burp_dir, pat))
    targets = [t for t in dict.fromkeys(targets)
               if os.path.basename(t).lower().startswith(("burpsuitepro", "burpsuiteproen"))]
    if not targets:
        return False

    changed = 0
    for t in targets:
        raw = open(t, "rb").read()
        enc = "gbk"
        try:
            text = raw.decode("gbk")
        except UnicodeDecodeError:
            enc = "utf-8"
            text = raw.decode("utf-8", errors="replace")

        if "zeroxf" in text or "JAVA_HOME" in text:
            info(f"已配置过，跳过: {os.path.basename(t)}")
            continue

        inject = (f'rem --- zeroxf: Burp 需要 Java {os.path.basename(java_home)}，'
                  f'此处显式指定，避开 PATH 里的旧 JDK ---\r\n'
                  f'set "JAVA_HOME={jh_win}"\r\n'
                  f'set "PATH=%JAVA_HOME%\\bin;%PATH%"\r\n')

        idx = text.lower().find("@echo off")
        if idx < 0:
            continue
        end = text.find("\n", idx) + 1
        text = text[:end] + inject + text[end:]

        # 备份 + 写回（保持原编码与 CRLF）
        if not os.path.exists(t + ".bak"):
            shutil.copy(t, t + ".bak")
        open(t, "wb").write(text.encode(enc, errors="replace"))
        ok(f"已修正启动脚本: {os.path.basename(t)}（原文件备份为 .bak）")
        changed += 1
    return changed > 0


# ---------- MCP 配置 ----------

def build_mcp_config(java_exe, proxy_jar, sse_url):
    """生成 mcpServers 条目。两端差异：WSL 必须用 Windows 的 java.exe，
    这样 proxy 进程跑在 Windows 侧，连 127.0.0.1 才是 Burp 所在的那台。"""
    if os.name == "nt":
        cmd = java_exe
        args = ["-jar", proxy_jar, "--sse-url", sse_url]
    else:
        # 关键：用 Windows 的 java.exe（进程在 Windows 上），而不是 WSL 的 java
        cmd = java_exe
        args = ["-jar", to_win_path(proxy_jar), "--sse-url", sse_url]
    return {"command": cmd, "args": args}


def write_config(cfg, print_only=False):
    if print_only:
        info(json.dumps({MCP_NAME: cfg}, ensure_ascii=False, indent=2))
        return
    data = {}
    if os.path.exists(CLAUDE_JSON):
        try:
            data = json.load(open(CLAUDE_JSON, encoding="utf-8"))
        except Exception:
            data = {}
        shutil.copy(CLAUDE_JSON, CLAUDE_JSON + ".bak")
        ok(f"已备份 {CLAUDE_JSON} → .bak")
    data.setdefault("mcpServers", {})[MCP_NAME] = cfg
    json.dump(data, open(CLAUDE_JSON, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    ok(f"已写入 MCP 配置（名称: {MCP_NAME}）")
    info("当前 mcpServers: " + ", ".join(data["mcpServers"].keys()))


# ---------- 验证 ----------

def verify(java_exe, proxy_jar, sse_url):
    """跑一次 MCP 握手，报告能拿到多少工具。"""
    reqs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "setup_burp", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]
    inp = "\n".join(json.dumps(r) for r in reqs) + "\n"
    jar = proxy_jar if os.name == "nt" else to_win_path(proxy_jar)
    try:
        p = subprocess.run([java_exe, "-jar", jar, "--sse-url", sse_url],
                           input=inp, capture_output=True, text=True, timeout=90)
    except Exception as e:
        bad(f"验证失败（无法启动 proxy）: {e}")
        return False

    for line in (p.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            m = json.loads(line)
        except Exception:
            continue
        if m.get("id") == 2:
            tools = m.get("result", {}).get("tools", [])
            ok(f"连通成功，Burp 暴露 {len(tools)} 个工具")
            for t in tools[:6]:
                info(f"- {t['name']}")
            if len(tools) > 6:
                info(f"... 其余 {len(tools) - 6} 个")
            return True

    err = ((p.stderr or "") + (p.stdout or "")).strip().splitlines()
    bad("未能完成握手。最后几行输出：")
    for l in err[-4:]:
        info(l[:110])
    info("")
    info("排查：① Burp 是否在运行 ② MCP 扩展是否启用 ③ 端口是否 9876")
    return False


# ---------- 主流程 ----------

def main():
    ap = argparse.ArgumentParser(description="把 Burp Suite 接入 Claude Code 的 MCP")
    ap.add_argument("--burp-dir", help="手动指定 Burp 安装目录")
    ap.add_argument("--sse-url", default=DEFAULT_SSE)
    ap.add_argument("--print-only", action="store_true", help="只打印配置，不写入")
    ap.add_argument("--verify-only", action="store_true", help="只验证连通性")
    args = ap.parse_args()

    print(_c("== Burp MCP 配置 ==\n", "36"))
    print(f"  运行环境: {'WSL' if IS_WSL else platform.system()}")

    # 1. Java
    java_exe, java_ver = find_java(21)
    if java_exe:
        ok(f"Java {java_ver}: {java_exe}")
    else:
        bad("未找到 Java 21+（Burp 2026.x 必需）")
        info("安装方式：winget install EclipseAdoptium.Temurin.21.JDK")
        info("或使用 Burp 绿色包内自带的 jdk-21_windows-x64_bin.exe（双击安装）")
        return 1

    # 2. proxy jar
    proxy = find_proxy_jar()
    if proxy:
        ok(f"proxy jar: {proxy}")
    else:
        bad("未找到 mcp-proxy-all.jar")
        info("它由 Burp 的 MCP 扩展自动释放。请先启动一次 Burp，")
        info("在 MCP 标签点击「解压服务器代理 jar」，然后重跑本脚本。")
        return 1

    # 3. Burp 本体（用于修启动脚本；找不到也不阻塞配置 MCP）
    burp_dir, burp_jar = (None, None)
    if args.burp_dir:
        burp_dir = args.burp_dir
        jars = glob.glob(os.path.join(burp_dir, "**", "burpsuite_pro*.jar"), recursive=True)
        burp_jar = jars[0] if jars else None
    else:
        burp_dir, burp_jar = find_burp()
    if burp_jar:
        ok(f"Burp: {burp_dir}")
    else:
        warn("未自动找到 Burp 安装目录（不影响 MCP 配置，但不修启动脚本）")
        info("可用 --burp-dir 手动指定")

    # 4. 修正绿色版启动脚本
    if burp_jar:
        fix_launcher(os.path.dirname(burp_jar), java_exe)

    # 5. 写 MCP 配置
    cfg = build_mcp_config(java_exe, proxy, args.sse_url)
    print()
    print("  将写入的 MCP 配置：")
    write_config(cfg, print_only=args.print_only)

    if args.print_only:
        return 0

    # 6. 验证
    print()
    print("  连通性验证（需要 Burp 正在运行）：")
    okall = verify(java_exe, proxy, args.sse_url)

    print()
    if okall:
        ok("完成。重启 Claude Code 后，burp MCP 即可用。")
    else:
        warn("配置已写入，但连通性验证未通过——Burp 可能没开。")
        info("启动 Burp 后重跑: python3 scripts/setup_burp.py --verify-only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
