#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""天狐工具箱 stdio MCP Server —— 让 AI 以 MCP 工具形式调用 geshell 工具。

走标准 stdio JSON-RPC（与用户现有 nmap/Playwright MCP 一致）：
- tools/list  → 列出所有 AI 可调用工具（工具名 tool_<normalized>）
- tools/call  → 执行工具（args: ["参数..."]），返回 stdout/stderr
"""
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ai import cli_runner  # noqa: E402
from ai import fuzzy  # noqa: E402
from ai import launch  # noqa: E402


def _tools_list() -> dict:
    tools = []
    for t in launch.get_all_tools():
        if not launch.is_cli_callable(t):
            continue
        name = "tool_" + launch.call_name(t)
        desc = str(t.get("description", "") or "")
        if t.get("risk"):
            desc = f"[risk:{t.get('risk')}] {desc}"
        tools.append({
            "name": name,
            "description": desc,
            "inputSchema": {
                "type": "object",
                "properties": {
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "传给工具的命令行参数，如 [\"-sV\", \"-p\", \"22,80\", \"127.0.0.1\"]",
                    }
                },
                "required": ["args"],
            },
        })
    return {"tools": tools}


def _tools_call(params: dict) -> dict:
    name = str(params.get("name", ""))
    args = params.get("arguments") or {}
    raw_args = args.get("args") or []
    if isinstance(raw_args, str):
        raw_args = raw_args.split()
    raw_args = [str(a) for a in raw_args]

    if not name.startswith("tool_"):
        return _err_result(f"未知工具: {name}")
    lookup = name[len("tool_"):]

    tool = fuzzy.find_tool(launch.get_all_tools(), lookup)
    if not tool:
        return _err_result(f"未找到工具: {lookup}")
    if not launch.is_cli_callable(tool):
        return _err_result(f"{tool.get('name')} 是 GUI/网页工具，不可由 AI 调用")

    built = cli_runner.build_command(tool, raw_args)
    if built.get("kind") == "gui":
        return _err_result("GUI 工具不支持 MCP 调用")
    if built.get("kind") == "web":
        rc = cli_runner.open_web(built.get("url"))
        return {"content": [{"type": "text", "text": f"已打开网页 {built.get('url')} (rc={rc})"}]}
    if built.get("err"):
        return _err_result(built["err"])

    rc, out, err = cli_runner.execute(built["cmd"], built.get("cwd"),
                                      built.get("env") or os.environ.copy(),
                                      capture=True, timeout=600)
    text = out or ""
    if err:
        text += ("\n[stderr]\n" if text else "") + err
    text += f"\n[exit code: {rc}]"
    return {"content": [{"type": "text", "text": text}]}


def _err_result(msg: str) -> dict:
    return {
        "isError": True,
        "content": [{"type": "text", "text": str(msg)}],
    }


def _respond(msg_id, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result}, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _respond_error(msg_id, code, message):
    sys.stdout.write(json.dumps({
        "jsonrpc": "2.0", "id": msg_id,
        "error": {"code": code, "message": message},
    }, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> int:
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                continue

            method = req.get("method", "")
            msg_id = req.get("id")

            if method == "initialize":
                _respond(msg_id, {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "tianhu-geshell", "version": "4.0-ai"},
                })
            elif method == "notifications/initialized":
                continue
            elif method == "ping":
                _respond(msg_id, {})
            elif method == "tools/list":
                _respond(msg_id, _tools_list())
            elif method == "tools/call":
                result = _tools_call(req.get("params") or {})
                _respond(msg_id, result)
            else:
                _respond_error(msg_id, -32601, f"Method not found: {method}")
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
