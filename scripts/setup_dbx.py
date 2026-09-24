#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 DBX 的 MCP server 接进 Claude Code（或任何 MCP 客户端）。

为什么要这一步
--------------
DBX 自带的 MCP server 装了不等于能用——它还得到 MCP 客户端的配置里注册，
客户端启动时才会把它拉起来。这个脚本做「发现 → 验证 → 写入 → 报告」四件事。

与 Burp 那个脚本的区别：Burp 要你先装商业软件、还要手动开扩展，这里只要
`provision_tools.py --tools dbx` 装好二进制即可——**不需要 Node，也不需要
DBX 桌面应用**（原生模式的库由那一个二进制直接连）。

用法
----
  python3 scripts/setup_dbx.py                # 配置 + 验证
  python3 scripts/setup_dbx.py --verify-only  # 只验证不写配置
  python3 scripts/setup_dbx.py --remove       # 从配置里移除
  python3 scripts/setup_dbx.py --data-dir D   # 指定 DBX 数据目录
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = ".exe" if os.name == "nt" else ""
BINARY = os.path.join(BASE, "tools", "dbx", "dbx-mcp" + EXE)
CLAUDE_JSON = os.path.join(os.path.expanduser("~"), ".claude.json")
SERVER_KEY = "dbx"


def _c(s, code):
    return f"\033[{code}m{s}\033[0m" if sys.stdout.isatty() else s


def ok(msg):
    print(_c("  [OK] ", "32") + msg)


def warn(msg):
    print(_c("  [警告] ", "33") + msg)


def bad(msg):
    print(_c("  [失败] ", "31") + msg)


def probe(data_dir=None, timeout=30):
    """跟二进制做一次真实 MCP 往返，返回 (工具数, 工具名列表)。失败抛异常。"""
    if not os.path.exists(BINARY):
        raise FileNotFoundError(
            f"未找到 {BINARY}\n"
            f"      装它：python3 scripts/provision_tools.py --tools dbx")
    env = dict(os.environ)
    if data_dir:
        env["DBX_DATA_DIR"] = data_dir
    p = subprocess.Popen([BINARY], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, encoding="utf-8", errors="replace", bufsize=1, env=env)
    lines = []
    threading.Thread(target=lambda: [lines.append(l) for l in p.stdout],
                     daemon=True).start()

    def send(obj):
        p.stdin.write(json.dumps(obj) + "\n")
        p.stdin.flush()

    def wait(rid, secs):
        end = time.time() + secs
        while time.time() < end:
            for l in list(lines):
                try:
                    d = json.loads(l)
                except ValueError:
                    continue
                if d.get("id") == rid:
                    return d
            time.sleep(0.1)
        return None

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                         "clientInfo": {"name": "setup_dbx", "version": "1"}}})
        init = wait(1, timeout)
        if not init:
            raise RuntimeError("initialize 无响应（二进制可能不是 MCP server）")
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tl = wait(2, timeout)
        if not tl:
            raise RuntimeError("tools/list 无响应")
        tools = [t["name"] for t in tl["result"]["tools"]]
        return len(tools), tools
    finally:
        try:
            p.terminate()
        except Exception:
            pass


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except ValueError as e:
        raise RuntimeError(f"{path} 不是合法 JSON：{e}")


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser(description="把 DBX 的 MCP server 接进 MCP 客户端")
    ap.add_argument("--verify-only", action="store_true", help="只验证，不写配置")
    ap.add_argument("--remove", action="store_true", help="从配置里移除")
    ap.add_argument("--data-dir", help="DBX 数据目录（默认用它自己的）")
    ap.add_argument("--config", default=CLAUDE_JSON,
                    help=f"MCP 客户端配置路径（默认 {CLAUDE_JSON}）")
    args = ap.parse_args()

    print("== setup_dbx ==")

    # 1. 发现
    if not os.path.exists(BINARY):
        bad(f"未找到 DBX 的 MCP server: {BINARY}")
        print("      装它：python3 scripts/provision_tools.py --tools dbx")
        return 1
    ok(f"找到 {BINARY}（{os.path.getsize(BINARY) // 1048576} MB）")
    if shutil.which("node") is None:
        ok("本机没有 Node —— 不影响，这个二进制是自足的")

    # 2. 验证（真连一次，不是看文件在不在）
    try:
        n, tools = probe(args.data_dir)
        ok(f"MCP 往返成功：{n} 个工具")
        print("      " + "、".join(tools[:8]) + ("…" if n > 8 else ""))
    except Exception as e:
        bad(f"MCP 验证失败：{type(e).__name__}: {e}")
        return 1

    if args.verify_only:
        return 0

    # 3. 写配置
    try:
        cfg = load_json(args.config)
    except RuntimeError as e:
        bad(str(e))
        return 1
    servers = cfg.setdefault("mcpServers", {})

    if args.remove:
        if SERVER_KEY in servers:
            del servers[SERVER_KEY]
            write_json(args.config, cfg)
            ok(f"已从 {args.config} 移除 MCP 配置「{SERVER_KEY}」")
        else:
            warn("配置里本来就没有 dbx 条目")
        return 0

    entry = {"command": BINARY, "args": []}
    if args.data_dir:
        entry["env"] = {"DBX_DATA_DIR": args.data_dir}
    entry["description"] = "DBX 数据库工作台：查库/看表结构/执行 SQL（22 个工具）"
    servers[SERVER_KEY] = entry
    write_json(args.config, cfg)
    ok(f"已写入 {args.config} 的 mcpServers.{SERVER_KEY}")

    print()
    print("  接下来：")
    print("    1. **重启 Claude Code** —— MCP 配置是启动时加载的")
    print("    2. 用之前先在 DBX 里配好连接，或让 AI 调 dbx_add_connection 加")
    print("    3. 写操作默认被拦（只读策略）。要放开在 DBX 设置 → MCP 里调，")
    print("       那是安全边界，别为了图省事直接开到完全访问")
    return 0


if __name__ == "__main__":
    sys.exit(main())
