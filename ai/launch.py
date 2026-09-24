#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""geshell —— zeroxf 工具箱 AI/CLI 统一入口。

用法：
  geshell list                    # 列出所有工具（按分类分组，AI 可用打 ✓）
  geshell info <工具名>            # 查看单个工具详情
  geshell doctor                  # 环境自检（JDK/依赖/冲突/路径）
  geshell selftest                # 运行回归测试
  geshell gendocs                 # 重新生成 ai/tools.md（AI 参考手册）
  geshell <工具名> [参数...]        # 调用工具

命令名匹配忽略大小写、空格、横线和下划线，支持中文拼音。
"""
import os
import shlex
import shutil
import sys
import tempfile
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config  # noqa: E402  天狐配置层（已补 BASE_DIR 锚定）
from ai import cli_runner  # noqa: E402
from ai import fuzzy  # noqa: E402

RUNS_DIR = os.path.join(BASE_DIR, "output", "runs")
TOOLS_MD = os.path.join(BASE_DIR, "ai", "tools.md")
MAX_RUN_LOGS = 100
MAX_RUN_LOG_DAYS = 30
RISK_LEVELS = ("passive", "active", "exploit", "brute", "tunnel", "post-exploit")


# ---------- 工具加载 ----------

def get_all_tools() -> list:
    """读取 tools.json，跳过 hidden 工具。"""
    tools = []
    for t in config.load_tools():
        if t.get("hidden"):
            continue
        tools.append(t)
    return tools


def is_cli_callable(tool: dict) -> bool:
    """AI 能否直接调用：显式 ai_callable 优先；否则有可执行入口即视为可调。"""
    if "ai_callable" in tool and tool["ai_callable"] is not None:
        return bool(tool["ai_callable"])
    t = str(tool.get("type", ""))
    if t in ("网页", "GUI应用", "GUI", "app"):
        return False
    if t in ("命令行", "cli") or t.startswith("JAVA") or t == "Python" or t.startswith("Python(") \
            or t in ("批处理", "batch", "PowerShell", "powershell", "ps1"):
        return True
    return bool(tool.get("path") or tool.get("url"))


def call_name(tool: dict) -> str:
    """调用名：工具名为 ASCII 命令时用工具名本身；
    工具名是中文标签（如 若依/蚁剑）时用 aliases[0]（真实命令名）。"""
    name = str(tool.get("name", ""))
    if any(ord(ch) > 127 for ch in name):
        aliases = tool.get("aliases") or []
        if aliases:
            return fuzzy.normalize_name(str(aliases[0]))
    return fuzzy.normalize_name(name)


# ---------- list ----------

def list_tools() -> int:
    tools = get_all_tools()
    if not tools:
        print("[提示] config/tools.json 里还没有工具，用 `geshell info` 提示或编辑 config/tools.json。")
        return 0

    # 按分类分组
    cat_order = config.load_categories()
    grouped: dict = {}
    for t in tools:
        grouped.setdefault(str(t.get("category", "") or "未分类"), []).append(t)
    for cat in cat_order:
        grouped.setdefault(cat, [])

    headers = ["工具名", "类型", "AI可用", "风险", "说明"]
    rows = []
    for cat in cat_order + [c for c in grouped if c not in cat_order]:
        items = grouped.get(cat) or []
        if not items:
            continue
        for t in items:
            rows.append([
                str(t.get("name", "")),
                str(t.get("type", "")),
                "✓" if is_cli_callable(t) else "✗",
                str(t.get("risk", "active") or "active"),
                str(t.get("description", ""))[:40],
            ])
    widths = [max(len(str(r[i])) for r in rows + [headers]) for i in range(5)]

    def _fmt(r):
        return "  ".join(str(r[i]).ljust(widths[i]) for i in range(5)).rstrip()

    print(_fmt(headers))
    print("  ".join("-" * w for w in widths))
    last_cat = None
    for cat in cat_order + [c for c in grouped if c not in cat_order]:
        items = grouped.get(cat) or []
        if not items:
            continue
        if cat != last_cat:
            print(f"\n[{cat}]")
            last_cat = cat
        for t in items:
            print(_fmt([
                str(t.get("name", "")),
                str(t.get("type", "")),
                "✓" if is_cli_callable(t) else "✗",
                str(t.get("risk", "active") or "active"),
                str(t.get("description", ""))[:40],
            ]))
    return 0


# ---------- info ----------

def show_info(tool: dict) -> int:
    print(f"名称:     {tool.get('name', '')}")
    aliases = tool.get("aliases") or []
    print(f"别名:     {', '.join(map(str, aliases)) if aliases else '—'}")
    print(f"分类:     {tool.get('category', '')}")
    print(f"类型:     {tool.get('type', '')}")
    print(f"说明:     {tool.get('description', '')}")
    print(f"AI可用:   {'✓' if is_cli_callable(tool) else '✗'}")
    print(f"风险:     {tool.get('risk', 'active') or 'active'}")
    if tool.get("path"):
        print(f"入口:     {tool.get('path', '')}")
    if tool.get("params_pre"):
        print(f"前置参数: {tool.get('params_pre', '')}")
    if tool.get("params"):
        print(f"参数:     {tool.get('params', '')}")
    if tool.get("url"):
        print(f"URL:      {tool.get('url', '')}")
    print(f"调用方式: geshell {call_name(tool)} [参数...]")
    if tool.get("example"):
        print(f"示例:     geshell {tool.get('example')}")
    return 0


# ---------- run ----------

def _cleanup_runs() -> None:
    try:
        if not os.path.isdir(RUNS_DIR):
            return
        dirs = sorted([os.path.join(RUNS_DIR, d) for d in os.listdir(RUNS_DIR)
                       if os.path.isdir(os.path.join(RUNS_DIR, d))], key=os.path.getmtime)
        while len(dirs) > MAX_RUN_LOGS:
            shutil.rmtree(dirs.pop(0), ignore_errors=True)
        for d in dirs:
            try:
                if (datetime.now().timestamp() - os.path.getmtime(d)) > MAX_RUN_LOG_DAYS * 86400:
                    shutil.rmtree(d, ignore_errors=True)
            except OSError:
                pass
    except Exception:
        pass


def _write_meta(meta_path: str, data: dict) -> None:
    def _q(v) -> str:
        s = str(v)
        if " " in s or s == "":
            return '"' + s + '"'
        return s
    with open(meta_path, "w", encoding="utf-8") as f:
        for k, v in data.items():
            f.write(f"{k}: {_q(v)}\n")


def run_tool(tool: dict, user_args: list) -> int:
    built = cli_runner.build_command(tool, user_args)

    if built.get("kind") == "gui":
        print(f"[GUI] 启动 {tool.get('name')}: {built.get('target')}")
        return cli_runner.launch_gui(tool)
    if built.get("kind") == "web":
        print(f"[网页] 打开 {built.get('url')}")
        return cli_runner.open_web(built.get("url"))
    if built.get("err"):
        print(f"[错误] {built['err']}")
        return 1

    cmd = built["cmd"]
    cwd = built.get("cwd")
    env = built.get("env") or os.environ.copy()

    # 运行日志目录
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(RUNS_DIR, f"{ts}_{fuzzy.normalize_name(tool.get('name', ''))}")
    try:
        os.makedirs(run_dir, exist_ok=True)
    except OSError:
        run_dir = os.path.join(tempfile.gettempdir(), "geshell-runs", f"{ts}")
        os.makedirs(run_dir, exist_ok=True)

    with open(os.path.join(run_dir, "command.txt"), "w", encoding="utf-8") as f:
        f.write(shlex.join(cmd) + "\n")

    meta = {
        "tool": tool.get("name", ""),
        "category": tool.get("category", ""),
        "aliases": ",".join(map(str, tool.get("aliases") or [])),
        "risk": tool.get("risk", "active") or "active",
        "cwd": cwd or os.getcwd(),
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "args_mode": tool.get("args_mode", "passthrough"),
    }
    _write_meta(os.path.join(run_dir, "meta.yaml"), meta)

    print(f"[执行] {shlex.join(cmd)}")
    if cwd:
        print(f"[目录] {cwd}")
    print(f"[日志] {run_dir}")

    rc, out, err = cli_runner.execute(cmd, cwd, env, capture=False)

    try:
        with open(os.path.join(run_dir, "stdout.txt"), "w", encoding="utf-8") as f:
            f.write(out)
        with open(os.path.join(run_dir, "stderr.txt"), "w", encoding="utf-8") as f:
            f.write(err)
        meta["returncode"] = rc
        meta["finished_at"] = datetime.now().isoformat(timespec="seconds")
        _write_meta(os.path.join(run_dir, "meta.yaml"), meta)
    except OSError:
        pass

    if rc == 0:
        _bump_weight(tool)

    _cleanup_runs()
    return rc


def _bump_weight(tool: dict) -> None:
    """启动成功 → 使用计数 +1。

    注意落点：写进 `config/weights.json`（已 gitignore），**不是** tools.json。
    tools.json 是被 git 跟踪的共享配置，往里面写每台机器各自的运行时计数，
    会让工作区每启动一次工具就变脏一次（这个坑困扰了双端同步很久）。
    """
    try:
        config.bump_weight(tool)
    except Exception:
        pass


# ---------- doctor ----------

def doctor() -> int:
    errors = 0
    print("== geshell doctor ==")

    # 1. JDK
    try:
        from core.env_manager import EnvManager
        em = EnvManager()
        for ver in ("8", "11"):
            # 用 get_java_exe 而非拼死的 bin/java.exe：类 Unix 下可执行文件没有 .exe 后缀
            exe = em.get_java_exe(ver)
            if exe and os.path.exists(exe):
                print(f"[ok]   JDK {ver}: {os.path.dirname(os.path.dirname(exe))}")
            elif os.name == "nt":
                print(f"[警告] JDK {ver} 未找到（JAVA8/JAVA11 类工具不可用）")
            else:
                java = shutil.which("java")
                if java:
                    print(f"[ok]   系统 java: {java}（非 Windows 环境）")
                else:
                    print(f"[警告] JDK {ver} 未找到（JAVA8/JAVA11 类工具不可用）")
    except Exception as e:
        print(f"[警告] JDK 检测失败: {e}")

    # 2. 工具加载
    tools = get_all_tools()
    print(f"[info] 工具总数: {len(tools)}")
    if not tools:
        print("[错误] config/tools.json 为空或加载失败")
        return 1

    # 3. 调用名冲突
    seen: dict = {}
    for t in tools:
        cname = call_name(t)
        seen.setdefault(cname, []).append(str(t.get("name", "")))
    for cname, names in seen.items():
        if len(names) > 1:
            print(f"[错误] 调用名冲突: {cname} → {', '.join(names)}")
            errors += 1

    # 4. 依赖命令
    for t in tools:
        for dep in (t.get("dependencies") or []):
            if not shutil.which(str(dep)):
                print(f"[警告] {t.get('name')} 依赖缺失: {dep}")

    # 5. 路径存在性 + bat 透传
    missing_path = set()          # 第 6 步据此去重，避免同一原因报两遍
    for t in tools:
        p = str(t.get("path", "") or "")
        if not p:
            continue
        is_bare = not ("/" in p or "\\" in p)
        # 存在性判断要用解析后的路径：Windows 上实际文件带 .exe、venv 是 Scripts/ 而非 bin/，
        # 直接拿 tools.json 里的原始 path（按 Linux 命名书写）比对会满屏误报。
        resolved = p if is_bare else cli_runner._resolve_path(t, p)
        if not is_bare and not os.path.exists(resolved):
            print(f"[警告] {t.get('name')} 路径不存在: {p}")
            missing_path.add(str(t.get("name")))
        if str(t.get("type", "")).strip() in ("批处理", "batch") and not is_bare \
                and os.path.exists(resolved) and p.lower().endswith(".bat"):
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if "%*" not in content and "$@" not in content:
                    print(f"[警告] {t.get('name')} 批处理不透传参数（缺 %*）")
            except OSError:
                pass

    # 6. AI 可调用工具命令可执行性
    for t in tools:
        if not is_cli_callable(t):
            continue
        # 第 5 步已经就「路径不存在」报过这个工具了。同一件事报两遍（oracle 那种
        # 会同时出现「路径不存在」和「入口不存在」）只会让警告数虚高、掩盖真问题。
        if str(t.get("name")) in missing_path:
            continue
        built = cli_runner.build_command(t, ["--help"])
        if built.get("kind") != "cmd" or built.get("err"):
            continue
        cmd0 = built["cmd"][0]
        if os.path.sep in cmd0 or "/" in cmd0 or "\\" in cmd0:
            if not os.path.exists(cmd0):
                print(f"[警告] {t.get('name')} 入口不存在: {cmd0}")
        elif not shutil.which(cmd0):
            print(f"[警告] {t.get('name')} 命令不在 PATH: {cmd0}")

    print("[完成] doctor 检查结束" + (f"，共 {errors} 个错误" if errors else ""))
    return 1 if errors else 0


# ---------- gendocs ----------

def generate_docs() -> int:
    tools = get_all_tools()
    ai_tools = [t for t in tools if is_cli_callable(t)]

    lines = ["# zeroxf 工具箱 AI 参考手册（geshell）", ""]
    lines.append("> 由 `geshell gendocs` 自动生成。工具名匹配忽略大小写、空格、横线、下划线，支持拼音。")
    lines.append("")
    lines.append("## 调用方式")
    lines.append("```bash")
    lines.append("geshell <工具名> [参数...]")
    lines.append("```")
    lines.append("")
    lines.append("## 工具总览（AI 可调用）")
    lines.append("")
    lines.append("| 调用名 | 工具 | 类型 | 风险 | 用途 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for t in ai_tools:
        lines.append(f"| {call_name(t)} | {t.get('name', '')} | {t.get('type', '')} | "
                     f"{t.get('risk', 'active') or 'active'} | {str(t.get('description', ''))[:50]} |")
    lines.append("")

    grouped: dict = {}
    for t in tools:
        grouped.setdefault(str(t.get("category", "") or "未分类"), []).append(t)

    for cat, items in grouped.items():
        lines.append(f"## {cat}")
        lines.append("")
        for t in items:
            cname = call_name(t)
            lines.append(f"### {t.get('name', '')}（{cname}）")
            lines.append("")
            lines.append(f"- 说明：{t.get('description', '')}")
            lines.append(f"- 风险：{t.get('risk', 'active') or 'active'}")
            lines.append(f"- 参数模式：{t.get('args_mode', 'passthrough')}")
            if t.get("aliases"):
                lines.append(f"- 别名：{', '.join(map(str, t['aliases']))}")
            if t.get("example"):
                lines.append(f"- 示例：`geshell {t['example']}`")
            lines.append("")

    with open(TOOLS_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[完成] 已生成 {TOOLS_MD}（{len(ai_tools)} 个 AI 可调用工具）")
    return 0


# ---------- selftest ----------

def run_selftest() -> int:
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "selftest.py")
    p = subprocess_run([sys.executable, script])
    return p


def subprocess_run(cmd: list) -> int:
    import subprocess
    return subprocess.call(cmd, cwd=BASE_DIR)


# ---------- main ----------

def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 0

    first = argv[0]
    rest = argv[1:]

    if first in ("list", "ls", "-l", "--list"):
        return list_tools()
    if first in ("help", "-h", "--help"):
        print(__doc__)
        return 0
    if first in ("info", "-i", "--info"):
        if not rest:
            print("[错误] 用法: geshell info <工具名>")
            return 1
        tool = fuzzy.find_tool(get_all_tools(), rest[0])
        if not tool:
            print(f"[错误] 未找到工具: {rest[0]}（用 geshell list 查看）")
            return 1
        return show_info(tool)
    if first == "doctor":
        return doctor()
    if first == "selftest":
        return run_selftest()
    if first in ("gendocs", "docs"):
        return generate_docs()

    # 其余当作工具调用
    tool = fuzzy.find_tool(get_all_tools(), first)
    if not tool:
        print(f"[错误] 未找到工具: {first}（用 geshell list 查看全部工具）")
        return 1
    if not is_cli_callable(tool):
        print(f"[错误] {tool.get('name')} 是 GUI/网页工具，请手动打开，AI 不可直接调用。")
        return 1
    return run_tool(tool, rest)


if __name__ == "__main__":
    sys.exit(main())
