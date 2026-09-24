#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zeroxf 工具箱 · 全量验证

一条命令检查工具箱是否完整可用。跑完给出「通过 / 警告 / 失败」的汇总。

    python3 scripts/verify_all.py            # 全部检查
    python3 scripts/verify_all.py --quick    # 跳过耗时项（MCP 往返、webshell 回归）

设计原则
--------
* **只读**：不改仓库、不装东西、不联网（唯一例外是 Release 资产可达性探测，
  可用 --offline 跳过）。
* **可选依赖降级为「跳过」而非「失败」**：没装 php 就跳过 webshell 回归，
  没装 Burp 就跳过 MCP 接线检查——这是环境差异，不是工具箱坏了。
* **区分「预期内缺失」与「真异常」**：前者的判据写在 EXPECTED_MISSING 里，
  出现时记警告；出现别的缺失才是失败。
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(BASE, "tools")
TOOLS_FILE = os.path.join(BASE, "config", "tools.json")
VENV_PY = os.path.join(TOOLS_DIR, "_venv", "Scripts" if os.name == "nt" else "bin",
                       "python" + (".exe" if os.name == "nt" else ""))

# 预期内缺失：不是工具箱坏了，而是授权/分发/平台限制。
# 值 = 简短原因，出现在就绪度缺失里时记「警告」而非「失败」。
EXPECTED_MISSING = {
    # fastjson / log4j 原先在这里——它们的 jar 无公开源，是两条空壳注册项。
    # 现在两条都指向自研的 javadeser CLI（协议自己实现，不依赖那两份 jar），
    # 所以**不该再当作预期内缺失**：真缺了就是故障。
    # hydra 原先在这里（Windows 无官方构建）。现在该条目指向 tools/brute/ 的
    # 调度器——Windows 上自动落到 netexec，两端都有爆破能力，故不再算预期缺失。
    "oracle": "仅 Windows 端缺失：官方只对登录用户提供 Windows 包（用 oracle-py 替代）",
    "cobaltstrike4.9": "商业软件，需自备（替代：sliver）",
    "BurpSuite": "商业软件，需自备（AI 走 MCP 接入）",
    "蚁剑": "未随工具箱分发（上游只发源码、无二进制；协议由 webshell 覆盖）",
}

OK, WARN, FAIL, SKIP = "OK", "WARN", "FAIL", "SKIP"
_results = []


def rec(level, group, msg):
    _results.append((level, group, msg))
    tag = {OK: "[OK]  ", WARN: "[警告]", FAIL: "[失败]", SKIP: "[跳过]"}[level]
    print(f"  {tag} {msg}")


def section(title):
    print(f"\n== {title} ==")


def run(cmd, cwd=None, timeout=120):
    """跑一条命令并捕获输出。

    **必须显式指定 utf-8**：Windows 上 `text=True` 会按 ANSI 代码页（中文
    环境是 GBK）解码，而工具箱的输出是 UTF-8（带 ✓/✗ 和中文）。不指定的话
    解码抛 UnicodeDecodeError，stdout 直接变成 None，后续全部报
    `'NoneType' has no attribute 'splitlines'`——症状离根因很远，很难查。
    """
    return subprocess.run(cmd, cwd=cwd or BASE, capture_output=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def py():
    """优先用工具箱自带的 venv python，保证依赖一致。"""
    return VENV_PY if os.path.exists(VENV_PY) else sys.executable


def geshell(*args):
    """构造调用 geshell 的 argv。

    两端的入口**不是同一个文件**：POSIX 是 `geshell`（bash 脚本），
    Windows 是 `geshell.cmd`。在 Windows 上直接执行 `geshell` 会报
    `WinError 193 不是有效的 Win32 应用程序`；而 .cmd 需要经 cmd.exe 启动。
    """
    if os.name == "nt":
        gs = os.path.join(BASE, "geshell.cmd")
        return [os.environ.get("COMSPEC", "cmd.exe"), "/c", gs, *args]
    return [os.path.join(BASE, "geshell"), *args]


def load_tools():
    with open(TOOLS_FILE, encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------
# 1. 仓库
# --------------------------------------------------------------------------
def check_repo():
    section("1. 仓库状态")
    try:
        head = run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()
        rec(OK, "repo", f"HEAD = {head}")
    except Exception as e:
        rec(FAIL, "repo", f"不是 git 仓库或 git 不可用: {e}")
        return
    r = run(["git", "status", "--porcelain"])
    dirty = [l for l in r.stdout.splitlines() if l.strip()]
    if dirty:
        rec(WARN, "repo", f"工作区有 {len(dirty)} 处未提交改动")
    else:
        rec(OK, "repo", "工作区干净")
    # 关键：源码类工具在 .gitignore 白名单里，必须真的被追踪
    tracked = set(run(["git", "ls-files"]).stdout.split())
    src_tools = ["tools/webshell/webshell_cli.py", "tools/revshell/revshell_cli.py",
                 "tools/oracle-py/oracle_cli.py", "tools/sstikit/ssti_cli.py",
                 "tools/springkit/spring_cli.py", "tools/ruoyikit/ruoyi_cli.py"]
    missing = [t for t in src_tools if t not in tracked]
    if missing:
        rec(FAIL, "repo", f"源码工具未被 git 追踪（clone 后会消失）: {missing}")
    else:
        rec(OK, "repo", f"源码工具均已入库（抽查 {len(src_tools)} 个）")
    if "config/tools.json" not in tracked:
        rec(FAIL, "repo", "config/tools.json 未入库 —— clone 下来会是个空壳")
    else:
        rec(OK, "repo", "config/tools.json 已入库")


# --------------------------------------------------------------------------
# 2. 注册表一致性（四个入口必须数得出同一个数）
# --------------------------------------------------------------------------
def check_registry(quick):
    section("2. 工具注册表一致性")
    tools = load_tools()
    total = len(tools)
    callable_n = sum(1 for t in tools if t.get("ai_callable"))
    rec(OK, "reg", f"tools.json: {total} 个工具，其中 {callable_n} 个 AI 可调用")

    # geshell list
    r = run(geshell("list"))
    listed = sum(1 for l in r.stdout.splitlines() if "✓" in l or "✗" in l)
    if listed == total:
        rec(OK, "reg", f"geshell list 一致（{listed}）")
    else:
        rec(FAIL, "reg", f"geshell list 数出 {listed}，与 tools.json 的 {total} 不一致")

    # ai/tools.md
    md = os.path.join(BASE, "ai", "tools.md")
    if os.path.exists(md):
        with open(md, encoding="utf-8") as f:
            n = sum(1 for l in f if l.startswith("### "))
        if n == total:
            rec(OK, "reg", f"ai/tools.md 一致（{n} 条）")
        else:
            rec(WARN, "reg", f"ai/tools.md 有 {n} 条，与 {total} 不符；跑 `geshell gendocs`")
    else:
        rec(WARN, "reg", "ai/tools.md 不存在；跑 `geshell gendocs`")

    # MCP tools/list
    if quick:
        rec(SKIP, "reg", "MCP tools/list（--quick 跳过）")
        return tools
    reqs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "verify", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]
    try:
        p = subprocess.run([py(), os.path.join(BASE, "ai", "mcp_server.py")],
                           input="\n".join(json.dumps(r) for r in reqs) + "\n",
                           capture_output=True, encoding="utf-8", errors="replace",
                           timeout=60, cwd=BASE)
        got = None
        for line in p.stdout.splitlines():
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("id") == 2:
                got = len(d["result"]["tools"])
        if got == callable_n:
            rec(OK, "reg", f"MCP tools/list 一致（{got}）")
        else:
            rec(FAIL, "reg", f"MCP tools/list 数出 {got}，与 {callable_n} 不一致")
    except Exception as e:
        rec(FAIL, "reg", f"MCP 握手失败: {type(e).__name__}: {e}")
    return tools


# --------------------------------------------------------------------------
# 3. 就绪度
# --------------------------------------------------------------------------
def check_readiness(tools):
    section("3. 工具就绪度（入口文件是否存在 / 裸命令是否在 PATH）")
    sys.path.insert(0, BASE)
    try:
        from ai import cli_runner
        from ai import launch as launch_mod
    except Exception as e:
        rec(FAIL, "ready", f"无法导入 ai.cli_runner: {e}")
        return
    import shutil
    # 注意：必须用 get_all_tools()，它给的是**已拼好 BASE** 的绝对路径。
    # 直接读 tools.json 拿到的是 /tools/xxx 这种仓库内相对路径，而
    # _resolve_path 内部会 abspath() —— 那会解析到文件系统根，全部误报缺失。
    try:
        ai_tools = [t for t in launch_mod.get_all_tools()
                    if launch_mod.is_cli_callable(t)]
    except Exception as e:
        rec(FAIL, "ready", f"get_all_tools() 失败: {e}")
        return
    ready, missing = [], []
    for t in ai_tools:
        p = str(t.get("path", "") or "")
        if not p:
            missing.append(t["name"]); continue
        bare = not ("/" in p or "\\" in p)
        try:
            x = p if bare else cli_runner._resolve_path(t, p)
        except Exception:
            x = None
        hit = bool(x) and (os.path.exists(x) or (bare and shutil.which(p)))
        (ready if hit else missing).append(t["name"])

    unexpected = [n for n in missing if n not in EXPECTED_MISSING]
    expected = [n for n in missing if n in EXPECTED_MISSING]
    if unexpected:
        rec(FAIL, "ready", f"就绪 {len(ready)}/{len(ai_tools)}；"
                           f"**非预期缺失** {unexpected}")
    else:
        rec(OK, "ready", f"就绪 {len(ready)}/{len(ai_tools)}")
    for n in expected:
        rec(WARN, "ready", f"{n} 缺失（预期内）：{EXPECTED_MISSING[n]}")


# --------------------------------------------------------------------------
# 4. 分发包完整性
# --------------------------------------------------------------------------
def check_dist():
    section("4. 分发包完整性")
    # 1) 随 git 分发的源码工具
    src = {
        "webshell": "tools/webshell/webshell_cli.py",
        "revshell": "tools/revshell/revshell_cli.py",
        "oracle-py": "tools/oracle-py/oracle_cli.py",
        "ssti": "tools/sstikit/ssti_cli.py",
        "spring": "tools/springkit/spring_cli.py",
        "ruoyi": "tools/ruoyikit/ruoyi_cli.py",
        "redis": "tools/rediskit/redis_cli.py",
        "tomcat": "tools/tomcatscanpro/TomcatScanPro.py",
        "dedecmscan": "tools/dedecmscan/dedescan.py",
        "avoidkilling": "tools/avoidkilling/main.py",
        "docem": "tools/docem/docem_cli.py",
        "dirsearch": "tools/dirsearch/dirsearch.py",
    }
    go = [k for k, v in src.items() if os.path.exists(os.path.join(BASE, v))]
    if len(go) == len(src):
        rec(OK, "dist", f"随 git 分发的源码工具到位（{len(go)}/{len(src)}）")
    else:
        bad = [k for k, v in src.items() if not os.path.exists(os.path.join(BASE, v))]
        rec(FAIL, "dist", f"源码工具缺失: {bad}")

    # 2) jar 包（走 Release 还原）
    jars = {"shiro": "shiro/shiro_attack.jar", "struts2": "struts2/struts2_exp.jar",
            "weblogic": "weblogic/WeblogicTool.jar", "thinkphp": "thinkphp/ThinkphpGUI.jar",
            "nacos": "nacos/nacos-exploit.jar", "jenkins": "jenkins/JenkinsExploit.jar",
            "xxl-job": "xxljob/xxl-job-attack.jar", "jeecg": "jeecg/jeecgExploitss.jar",
            "dbcombo": "dbcombo/DBUtil.jar", "iwannagetall": "iwannagetall/IWannaGetAll.jar",
            "hyacinth": "hyacinth/hyacinth.jar", "godzilla": "godzilla/godzilla.jar",
            "behinder": "behinder/Behinder.jar", "heapdump": "heapdump/JDumpSpider.jar"}
    have = [k for k, v in jars.items() if os.path.exists(os.path.join(TOOLS_DIR, v))]
    if len(have) == len(jars):
        rec(OK, "dist", f"jar 类工具到位（{len(have)}/{len(jars)}）")
    else:
        lack = [k for k in jars if k not in have]
        rec(WARN, "dist", f"jar 类工具缺 {len(lack)} 个: {lack}；"
                          f"跑 `python3 scripts/provision_tools.py --jars`")

    # 3) 便携 JDK
    jd = os.path.join(BASE, "Java_path")
    if os.path.isdir(jd):
        vers = sorted(d for d in os.listdir(jd) if os.path.isdir(os.path.join(jd, d)))
        rec(OK, "dist", f"便携 JDK: {', '.join(vers) or '（空）'}")
    else:
        rec(WARN, "dist", "Java_path/ 不存在；跑 `provision_tools.py --jdk`")

    # 4) venv 与关键依赖
    if os.path.exists(VENV_PY):
        mods = []
        for m in ("PyQt6.QtWidgets", "requests", "Crypto.Cipher.AES"):
            r = subprocess.run([VENV_PY, "-c", f"import {m}"],
                               capture_output=True)
            mods.append((m, r.returncode == 0))
        lack = [m for m, okk in mods if not okk]
        if lack:
            rec(WARN, "dist", f"venv 缺依赖: {lack}（PyQt6→--gui，其余→--webshell-deps）")
        else:
            rec(OK, "dist", "venv 依赖齐备（PyQt6 / requests / pycryptodome）")
    else:
        rec(WARN, "dist", "tools/_venv 不存在；跑 `provision_tools.py --gui`")


# --------------------------------------------------------------------------
# 5. Release 资产可达性
# --------------------------------------------------------------------------
def check_release(offline):
    """检查 Release 资产。

    要注意区分两种情况——它们的处置完全不同：
      * 资产**不存在**（被删/fork 后不跟随）→ 得手动准备
      * 资产在、但**本机连不上 github.com** → 换网络/代理即可
    第二跳的 download 域名走的是 github.com（会 302 到 objects.githubusercontent.com），
    而 github.com 在部分网络下会被链路干扰（TCP 通、TLS 超时）。
    这时改问 api.github.com 仍然能确认资产是否存在。
    """
    section("5. Release 资产可达性")
    if offline:
        rec(SKIP, "release", "（--offline 跳过）")
        return

    cache = os.path.join(BASE, ".buildtools", "zeroxf-jar-tools-v1.tar.gz")
    if os.path.exists(cache):
        rec(OK, "release", f"本地已有缓存（{os.path.getsize(cache) / 1048576:.0f} MB），"
                           f"本次安装无需下载")

    url = ("https://github.com/qwq-nm/zeroxf_tools/releases/download/"
           "jar-tools-v1/zeroxf-jar-tools-v1.tar.gz")
    net_err = None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "verify_all",
                                                   "Range": "bytes=0-1"})
        with urllib.request.urlopen(req, timeout=90) as r:
            magic = r.read(2)
            total = r.headers.get("Content-Range", "?")
        if magic[:2] == b"\x1f\x8b":
            rec(OK, "release", f"jar-tools-v1 可下载（gzip 有效；{total}）")
            return
        rec(WARN, "release", f"资产可达但内容不像 gzip: {magic!r}")
        return
    except Exception as e:
        net_err = e

    # 下载失败：用可达的 API 域名判断到底是「资产没了」还是「网络不通」
    try:
        api = ("https://api.github.com/repos/qwq-nm/zeroxf_tools/"
               "releases/tags/jar-tools-v1")
        req = urllib.request.Request(api, headers={"User-Agent": "verify_all"})
        with urllib.request.urlopen(req, timeout=45) as r:
            d = json.loads(r.read().decode())
        assets = d.get("assets", [])
        if assets:
            a = assets[0]
            rec(WARN, "release",
                f"资产存在（{a['name']}，{a['size'] / 1048576:.0f} MB，"
                f"state={a['state']}），但本机下不动："
                f"{type(net_err).__name__}。"
                f"这是**网络问题不是资产问题**——"
                f"github.com 常被链路干扰（TCP 通、TLS 超时），"
                f"换网络/代理再试；已装好的机器不受影响")
        else:
            rec(FAIL, "release", "Release 存在但**没有任何资产** —— "
                                 "`--jars` 会失败，需要重新上传")
    except Exception as e2:
        rec(FAIL, "release",
            f"资产探测失败且 API 也查不到（{type(net_err).__name__} / "
            f"{type(e2).__name__}）—— 离线环境可加 --offline 跳过")


# --------------------------------------------------------------------------
# 6. 自检与回归
# --------------------------------------------------------------------------
def check_selftests(quick):
    section("6. 自检与回归")
    gs = os.path.join(BASE, "geshell.cmd" if os.name == "nt" else "geshell")
    if os.path.exists(gs):
        r = run(geshell("selftest"), timeout=180)
        # unittest 把结果写到 stderr，不是 stdout —— 两边都要看
        out = r.stdout + r.stderr
        if r.returncode == 0 and "OK" in out:
            tail = [l for l in out.splitlines() if l.startswith("Ran")]
            rec(OK, "test", f"geshell selftest 通过（{tail[0] if tail else ''}）")
        else:
            rec(FAIL, "test", f"geshell selftest 失败:\n{out[-400:]}")
        r = run(geshell("doctor"), timeout=180)
        warns = [l for l in r.stdout.splitlines() if "警告" in l]
        rec(OK if len(warns) <= 7 else WARN, "test",
            f"geshell doctor 报 {len(warns)} 条警告（预期 ≤7）")
    else:
        rec(FAIL, "test", "geshell 入口不存在")

    # webshell 三协议回归（需要本机 php）
    if quick:
        rec(SKIP, "test", "webshell 三协议回归（--quick 跳过）")
        return
    php = subprocess.run(["php", "-v"], capture_output=True).returncode == 0 \
        if os.name != "nt" else False
    if not php:
        rec(SKIP, "test", "webshell 三协议回归（本机无 php，跳过）")
        return
    script = os.path.join(BASE, ".buildtools", "ws-research", "selftest_all.sh")
    if not os.path.exists(script):
        rec(SKIP, "test", "webshell 回归脚本不在（开发期脚本，未随仓库分发）")
        return
    r = run(["bash", script], timeout=600)
    last = [l for l in r.stdout.splitlines() if "通过" in l and "失败" in l]
    if r.returncode == 0:
        rec(OK, "test", f"webshell 三协议回归通过（{last[0].strip() if last else ''}）")
    else:
        rec(FAIL, "test", f"webshell 回归失败:\n{r.stdout[-600:]}")


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="zeroxf 工具箱全量验证")
    ap.add_argument("--quick", action="store_true", help="跳过耗时项")
    ap.add_argument("--offline", action="store_true", help="不联网")
    args = ap.parse_args()

    print("=" * 68)
    print(f"zeroxf 工具箱 · 全量验证   平台: {'Windows' if os.name == 'nt' else sys.platform}")
    print(f"仓库: {BASE}")
    print("=" * 68)

    check_repo()
    tools = check_registry(args.quick)
    check_readiness(tools)
    check_dist()
    check_release(args.offline)
    check_selftests(args.quick)

    n_ok = sum(1 for l, _, _ in _results if l == OK)
    n_warn = sum(1 for l, _, _ in _results if l == WARN)
    n_fail = sum(1 for l, _, _ in _results if l == FAIL)
    n_skip = sum(1 for l, _, _ in _results if l == SKIP)

    print("\n" + "=" * 68)
    print(f"汇总：通过 {n_ok}   警告 {n_warn}   失败 {n_fail}   跳过 {n_skip}")
    if n_fail:
        print("\n失败项：")
        for l, g, m in _results:
            if l == FAIL:
                print(f"  - [{g}] {m.splitlines()[0]}")
    if n_warn:
        print("\n警告项（多数是预期内的环境差异，逐条看原因）：")
        for l, g, m in _results:
            if l == WARN:
                print(f"  - [{g}] {m.splitlines()[0]}")
    print("=" * 68)
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
