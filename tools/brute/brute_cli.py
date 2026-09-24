#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""密码爆破 —— 统一入口，背后按平台自动选后端。

为什么有这个工具
----------------
hydra 是爆破的默认选择，但它**只有类 Unix 版本**，官方从未发布 Windows 构建
（winget 源里那个同名的 HydraLauncher 是游戏启动器，与渗透无关）。于是
Windows 端一直缺爆破能力，文档里只能让用户自己去写 nmap NSE 脚本。

但工具箱里本来就有 **NetExec（`nxc`）**，它支持 ftp/ssh/rdp/smb/mssql/ldap/
winrm/vnc 等协议的凭据喷洒，且两端都能装。所以这里做一个薄调度：
**有 hydra 就用 hydra，没有就落到 nxc**，对外是一套参数。

这不是把 nxc 伪装成 hydra —— 用 `--show` 或 `--backend` 都能看到实际跑的是谁，
`geshell info hydra` 的描述里也写明了。

用法
----
  brute --service ssh --target 10.0.0.5 -u root --passwords pass.txt
  brute --service smb --target 10.0.0.5 -u users.txt -p pass.txt --show
  brute --service rdp --target 10.0.0.5 -u admin -p 'P@ssw0rd' --backend nxc
  brute --list                       # 列出可用服务与当前后端

授权提醒：仅可用于你拥有明确授权的目标。爆破会在目标日志里留下大量失败记录。
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))

# 通用服务名 → 各后端的写法。None = 该后端不支持这个协议。
# 只列两端各自真正支持的：hydra 没有 winrm，nxc 没有 mysql。
SERVICES = {
    "ssh":      {"hydra": "ssh",      "nxc": "ssh"},
    "ftp":      {"hydra": "ftp",      "nxc": "ftp"},
    "rdp":      {"hydra": "rdp",      "nxc": "rdp"},
    "smb":      {"hydra": "smb",      "nxc": "smb"},
    "mssql":    {"hydra": "mssql",    "nxc": "mssql"},
    "ldap":     {"hydra": "ldap2",    "nxc": "ldap"},
    "vnc":      {"hydra": "vnc",      "nxc": "vnc"},
    "winrm":    {"hydra": None,       "nxc": "winrm"},
    "wmi":      {"hydra": None,       "nxc": "wmi"},
    "nfs":      {"hydra": None,       "nxc": "nfs"},
    "mysql":    {"hydra": "mysql",    "nxc": None},
    "postgres": {"hydra": "postgres", "nxc": None},
    "redis":    {"hydra": "redis",    "nxc": None},
    "smtp":     {"hydra": "smtp",     "nxc": None},
    "imap":     {"hydra": "imap",     "nxc": None},
}


def find_backend(name):
    """找后端的可执行文件。先看工具箱自带的 venv（nxc 装在那），再看 PATH。"""
    if name == "hydra":
        return shutil.which("hydra")
    if name == "nxc":
        for cand in (
            os.path.join(BASE, "tools", "_venv", "Scripts", "nxc.exe"),
            os.path.join(BASE, "tools", "_venv", "bin", "nxc"),
            os.path.join(BASE, "tools", "_netexec_venv", "bin", "nxc"),
        ):
            if os.path.exists(cand):
                return cand
        return shutil.which("nxc") or shutil.which("netexec")
    return None


def cred_flags(single, plural):
    """单值走 -x，文件走 --xs。文件用相对/绝对路径都行。"""
    return single, plural


def build_hydra(svc, args):
    cmd = [args._hydra]
    if args.user:
        cmd += ["-l", args.user]
    elif args.users:
        cmd += ["-L", args.users]
    if args.password:
        cmd += ["-p", args.password]
    elif args.passwords:
        cmd += ["-P", args.passwords]
    if not (args.user or args.users) or not (args.password or args.passwords):
        raise ValueError("hydra 需要同时给出用户名与密码（各可以是单值或文件）")
    cmd += ["-t", str(args.threads)]
    if args.port:
        cmd += ["-s", str(args.port)]
    if args.stop_on_first:
        cmd += ["-f"]
    cmd += ["-V", f"{svc}://{args.target}"]
    return cmd


def build_nxc(svc, args):
    cmd = [args._nxc, svc, args.target]
    # nxc 的 -u/-p 同时接受单值和文件（它自己判断），所以不用分支
    if args.user or args.users:
        cmd += ["-u", args.user or args.users]
    if args.password or args.passwords:
        cmd += ["-p", args.password or args.passwords]
    if args.port:
        cmd += ["--port", str(args.port)]
    if args.threads:
        cmd += ["-t", str(args.threads)]
    if not (args.user or args.users) or not (args.password or args.passwords):
        raise ValueError("需要同时给出用户名与密码（各可以是单值或文件）")
    return cmd


def pick_backend(svc, args):
    """选后端。--backend 可强制；否则 hydra 优先，它更快且参数更熟。"""
    order = ["hydra", "nxc"] if args.backend == "auto" else [args.backend]
    reasons = []
    for name in order:
        if SERVICES[svc][name] is None:
            reasons.append(f"{name} 不支持 {svc}")
            continue
        path = find_backend(name)
        if not path:
            reasons.append(f"未安装 {name}")
            continue
        setattr(args, f"_{name}", path)
        return name, None
    return None, reasons


def main():
    ap = argparse.ArgumentParser(
        description="密码爆破统一入口（自动选 hydra 或 netexec）",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--service", "-s", help="目标协议，如 ssh / ftp / rdp / smb")
    ap.add_argument("--target", "-t", help="目标主机")
    ap.add_argument("-u", "--user", help="用户名（单个）")
    ap.add_argument("--users", help="用户名列表文件")
    ap.add_argument("-p", "--password", help="密码（单个）")
    ap.add_argument("--passwords", help="密码字典文件")
    ap.add_argument("--port", type=int, help="非默认端口")
    ap.add_argument("--threads", type=int, default=4, help="并发数（默认 4，别太猛）")
    ap.add_argument("--stop-on-first", action="store_true",
                    help="命中一组就停（hydra 的 -f）")
    ap.add_argument("--backend", choices=["auto", "hydra", "nxc"], default="auto",
                    help="强制使用某个后端；默认 auto（有 hydra 用 hydra）")
    ap.add_argument("--show", action="store_true", help="只打印将执行的命令")
    ap.add_argument("--list", action="store_true", help="列出服务与当前可用后端")
    args = ap.parse_args()

    if args.list:
        hy, nx = find_backend("hydra"), find_backend("nxc")
        print(f"  hydra: {hy or '未安装'}")
        print(f"  nxc  : {nx or '未安装'}")
        print(f"\n  支持的服务（{len(SERVICES)} 个）:")
        for name, m in SERVICES.items():
            who = "/".join(b for b in ("hydra", "nxc") if m[b])
            print(f"    {name:10s} {who}")
        return 0

    if not args.service or not args.target:
        ap.error("需要 --service 与 --target（服务列表见 --list）")
    svc = args.service.lower()
    if svc not in SERVICES:
        print(f"[错误] 未知服务 {svc!r}。可用: {'、'.join(SERVICES)}", file=sys.stderr)
        return 2

    backend, reasons = pick_backend(svc, args)
    if not backend:
        print(f"[错误] 没有可用于 {svc} 的后端：", file=sys.stderr)
        for r in reasons:
            print(f"       - {r}", file=sys.stderr)
        print(f"       装一个：python3 scripts/provision_tools.py --tools netexec",
              file=sys.stderr)
        return 2

    # 先校验字典文件真的存在。这一步不是多余的：两个后端都会把 `-P/-p` 的值
    # 「是文件就当字典、不是就当字面口令」，路径写错时它们**不报错**，而是
    # 老老实实拿这个文件名去当密码试——静默做错事，比报错难查得多。
    for label, path in (("--users", args.users), ("--passwords", args.passwords)):
        if path and not os.path.isfile(path):
            print(f"[错误] {label} 指向的文件不存在: {path}", file=sys.stderr)
            print(f"       提示：若你本来就想用这个字符串当口令，请改用 "
                  f"{'-u' if label == '--users' else '-p'}。", file=sys.stderr)
            return 2

    try:
        cmd = (build_hydra if backend == "hydra" else build_nxc)(
            SERVICES[svc][backend], args)
    except ValueError as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 2

    print(f"[后端] {backend}  ({getattr(args, f'_{backend}')})")
    print(f"[命令] {' '.join(cmd)}")
    if args.show:
        return 0
    print()
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        return 130
    except OSError as e:
        print(f"[错误] 执行失败: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
