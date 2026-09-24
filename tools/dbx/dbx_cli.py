#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DBX — 数据库工作台的命令行入口。

背景
----
DBX（github.com/t8y2/dbx）是一款 20MB 量级的跨平台数据库工作台，支持 70+ 种库。
它自带一个 Rust 写的 **MCP server**（22 个工具），但那个 server 只会说 MCP 协议，
没有给人用的命令行。本文件就是补这一层：把 MCP 包成一个顺手的 CLI，
于是同一套能力既能被 AI 通过 MCP 调用，也能 `geshell dbx ...` 直接敲。

它走的仍是 DBX 自己的连接存储（`dbx_add_connection` 写进去的连接，
桌面端也能看到），所以两端、两种入口共享同一份连接配置。

用法
----
  dbx --list                                  # 列出已配置的连接
  dbx -c "SELECT * FROM users" -n mysql-prod  # 执行查询
  dbx -c "SELECT 1" -n prod -d mydb           # 指定库
  dbx --tables -n prod                        # 列库中的表
  dbx --describe users -n prod                # 看表结构
  dbx --add mysql-prod --type mysql --host 10.0.0.5 \\
      --user root --password p@ss --database app
  dbx --remove mysql-prod
  dbx --serve                                 # 直接跑原始 MCP server（调试用）

授权提醒：仅可用于你拥有明确授权的目标。
"""
import argparse
import json
import os
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = ".exe" if os.name == "nt" else ""
BINARY = os.path.join(HERE, "dbx-mcp" + EXE)


class DbxMcp:
    """DBX MCP server 的最小客户端（stdio + JSON-RPC）。"""

    def __init__(self, data_dir=None, timeout=60):
        if not os.path.exists(BINARY):
            raise FileNotFoundError(
                f"未找到 DBX 的 MCP server: {BINARY}\n"
                f"      装它：python3 scripts/provision_tools.py --tools dbx")
        env = dict(os.environ)
        if data_dir:
            env["DBX_DATA_DIR"] = data_dir
        self.timeout = timeout
        self.proc = subprocess.Popen(
            [BINARY], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, encoding="utf-8", errors="replace", bufsize=1, env=env)
        self._id = 0
        self._lock = threading.Lock()
        self._err = []
        threading.Thread(target=self._drain_err, daemon=True).start()
        self._call("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "geshell-dbx", "version": "1"}})
        self._notify("notifications/initialized")

    def _drain_err(self):
        for line in self.proc.stderr:
            self._err.append(line.rstrip("\n"))

    def _send(self, obj):
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def _notify(self, method, params=None):
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def _call(self, method, params):
        with self._lock:
            self._id += 1
            rid = self._id
            self._send({"jsonrpc": "2.0", "id": rid, "method": method,
                        "params": params})
            while True:
                line = self.proc.stdout.readline()
                if not line:
                    tail = "\n".join(self._err[-6:])
                    raise RuntimeError(f"DBX MCP 进程结束了。stderr:\n{tail}")
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("id") == rid:
                    if "error" in d:
                        raise RuntimeError(d["error"].get("message", str(d["error"])))
                    return d.get("result") or {}

    def tool(self, tool_name, **args):
        """调用一个 MCP 工具，返回文本结果；工具自身报错则抛异常。

        参数名不能叫 `name`——调用方常要传 `name=...`（dbx_add_connection、
        dbx_remove_connection 的入参就叫 name），会与本形参撞成
        `got multiple values for argument 'name'`。
        """
        res = self._call("tools/call", {"name": tool_name, "arguments": args})
        text = "".join(c.get("text", "") for c in (res.get("content") or []))
        if res.get("isError"):
            raise RuntimeError(text.strip() or f"{tool_name} 执行失败")
        return text

    def close(self):
        try:
            self.proc.terminate()
        except Exception:
            pass


def _target(args):
    """把 -n/-d 收成一个 dict，DBX 的多数工具用 connection_name + database。"""
    kw = {}
    if getattr(args, "connection", None):
        kw["connection_name"] = args.connection
    if getattr(args, "database", None):
        kw["database"] = args.database
    return kw


def main():
    ap = argparse.ArgumentParser(
        description="DBX 数据库工作台 —— 命令行入口（背后是它自带的 MCP server）",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--sql", help="要执行的 SQL")
    ap.add_argument("-f", "--file", help="从文件读 SQL")
    ap.add_argument("-n", "--connection", help="连接名（见 --list）")
    ap.add_argument("-d", "--database", help="库名")
    ap.add_argument("--list", action="store_true", help="列出已配置的连接")
    ap.add_argument("--tables", action="store_true", help="列出表")
    ap.add_argument("--describe", metavar="TABLE", help="查看表结构")
    ap.add_argument("--databases", action="store_true", help="列出该连接下的库")
    ap.add_argument("--add", metavar="NAME", help="新增连接")
    ap.add_argument("--remove", metavar="NAME", help="删除连接")
    ap.add_argument("--type", dest="db_type", help="--add 用：库类型，如 mysql/sqlite/redis")
    ap.add_argument("--host", help="--add 用：主机（SQLite 填文件路径）")
    ap.add_argument("--port", type=int, help="--add 用：端口")
    ap.add_argument("--user", help="--add 用：用户名")
    ap.add_argument("--password", help="--add 用：密码")
    ap.add_argument("--data-dir", help="DBX 数据目录（默认用它自己的；"
                                      "设了就不共享桌面端的连接）")
    ap.add_argument("--serve", action="store_true",
                    help="不用包装层，直接跑原始 MCP server（调试用）")
    args = ap.parse_args()

    if args.serve:
        # 直接把 stdin/stdout 交给原始 server，便于用 MCP 客户端连
        env = dict(os.environ)
        if args.data_dir:
            env["DBX_DATA_DIR"] = args.data_dir
        return subprocess.call([BINARY], env=env)

    try:
        cli = DbxMcp(data_dir=args.data_dir)
    except (FileNotFoundError, RuntimeError) as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 2

    try:
        if args.add:
            if not (args.db_type and args.host):
                ap.error("--add 需要 --type 与 --host（SQLite 的 host 填文件路径）")
            kw = {"name": args.add, "db_type": args.db_type, "host": args.host}
            for k in ("port", "user", "password", "database"):
                v = getattr(args, k, None)
                if v:
                    kw[k] = v
            print(cli.tool("dbx_add_connection", **kw))
            return 0
        if args.remove:
            # 入参叫 connection_name，不是 name
            print(cli.tool("dbx_remove_connection", connection_name=args.remove))
            return 0
        if args.list:
            print(cli.tool("dbx_list_connections"))
            return 0
        if args.databases:
            print(cli.tool("dbx_list_databases", **_target(args)))
            return 0
        if args.tables:
            print(cli.tool("dbx_list_tables", **_target(args)))
            return 0
        if args.describe:
            print(cli.tool("dbx_describe_table", table=args.describe, **_target(args)))
            return 0

        sql = args.sql
        if args.file:
            with open(args.file, encoding="utf-8", errors="replace") as f:
                sql = f.read()
        if sql:
            print(cli.tool("dbx_execute_query", sql=sql, **_target(args)))
            return 0

        ap.print_help()
        return 0
    except RuntimeError as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 1
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
