#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Oracle 数据库客户端（thin 模式，无需 Instant Client）。

替代 sqlplus：Oracle 官方不提供 Windows 版 Instant Client 的免登录下载，
但 python-oracledb 的 **thin 模式是纯 Python 实现**，不需要任何 Oracle
客户端库就能连库——因此在 Windows 端也能用。

用法：
  oracle_cli.py <连接串> -e "SELECT * FROM users WHERE rownum<5"
  oracle_cli.py <连接串> -f query.sql
  oracle_cli.py <连接串>                      # 交互模式（输入 SQL，分号结尾执行）
  oracle_cli.py --help

连接串格式（兼容 sqlplus 风格）：
  user/pass@host:1521/service_name
  user/pass@host:1521/SID
  user/pass@//host:1521/service_name

示例：
  oracle_cli.py scott/tiger@10.0.0.5:1521/orcl -e "select banner from v$version"
  oracle_cli.py scott/tiger@10.0.0.5:1521/orcl -e "select * from users" --csv
"""
import argparse
import csv
import os
import re
import sys

try:
    import oracledb
except ImportError:
    sys.stderr.write(
        "[错误] 缺少 python-oracledb。安装：\n"
        "       tools/_venv/bin/pip install oracledb\n")
    sys.exit(1)


def parse_connect(conn_str):
    """把 sqlplus 风格的连接串拆成 (user, password, dsn)。

    支持：
      user/pass@host:port/service
      user/pass@//host:port/service
      user/pass@host:port/SID
    """
    m = re.match(r"^(?P<user>[^/@]+)(?:/(?P<pwd>[^@]*))?@(?P<dsn>.+)$", conn_str.strip())
    if not m:
        raise ValueError(f"连接串格式无法识别: {conn_str!r}\n"
                         f"应为 user/password@host:port/service")
    user = m.group("user")
    pwd = m.group("pwd") or ""
    dsn = m.group("dsn").lstrip("/")
    return user, pwd, dsn


def dump_cursor(cur, as_csv=False):
    """打印结果集。"""
    cols = [d[0] for d in (cur.description or [])]
    rows = cur.fetchall()
    if as_csv:
        w = csv.writer(sys.stdout)
        w.writerow(cols)
        for r in rows:
            w.writerow(["" if v is None else v for v in r])
        return len(rows)

    if not cols:
        return len(rows)
    # 简易对齐表格
    data = [["" if v is None else str(v) for v in r] for r in rows]
    widths = [max(len(str(cols[i])), *(len(r[i]) for r in data)) if data
              else len(str(cols[i])) for i in range(len(cols))]
    line = "  ".join(str(cols[i]).ljust(widths[i]) for i in range(len(cols)))
    print(line)
    print("  ".join("-" * w for w in widths))
    for r in data:
        print("  ".join(r[i].ljust(widths[i]) for i in range(len(cols))))
    return len(rows)


def run_sql(conn, sql, as_csv=False):
    cur = conn.cursor()
    try:
        cur.execute(sql)
        n = 0
        while True:
            if cur.description:
                n += dump_cursor(cur, as_csv)
            else:
                n = cur.rowcount
                print(f"[OK] 影响 {n} 行")
                break
            if not cur.nextset():
                break
        if not conn.autocommit:
            conn.commit()
        return n
    finally:
        cur.close()


def main():
    ap = argparse.ArgumentParser(
        description="Oracle 客户端（thin 模式，无需 Instant Client）")
    ap.add_argument("connect", nargs="?", help="连接串 user/pass@host:port/service")
    ap.add_argument("-e", "--execute", help="要执行的 SQL")
    ap.add_argument("-f", "--file", help="从文件读取 SQL")
    ap.add_argument("--csv", action="store_true", help="以 CSV 输出")
    ap.add_argument("--tree", action="store_true",
                    help="列出当前用户可见的表")
    args = ap.parse_args()

    if not args.connect:
        ap.print_help()
        return 2

    try:
        user, pwd, dsn = parse_connect(args.connect)
    except ValueError as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 1

    try:
        conn = oracledb.connect(user=user, password=pwd, dsn=dsn)
    except Exception as e:
        print(f"[错误] 连接失败: {e}", file=sys.stderr)
        return 1

    print(f"[OK] 已连接（thin 模式）: {user}@{dsn}")
    try:
        if args.tree:
            run_sql(conn, "SELECT table_name FROM user_tables ORDER BY table_name",
                    args.csv)
            return 0
        if args.file:
            sql = open(args.file, encoding="utf-8", errors="replace").read()
            run_sql(conn, sql.rstrip().rstrip(";"), args.csv)
            return 0
        if args.execute:
            run_sql(conn, args.execute.rstrip().rstrip(";"), args.csv)
            return 0

        # 交互模式
        print("输入 SQL（分号结尾执行，exit 退出）：")
        buf = []
        for line in sys.stdin:
            s = line.strip()
            if s.lower() in ("exit", "quit"):
                break
            if not s:
                continue
            buf.append(s)
            joined = " ".join(buf)
            if joined.endswith(";"):
                try:
                    run_sql(conn, joined.rstrip().rstrip(";"), args.csv)
                except Exception as e:
                    print(f"[错误] {e}", file=sys.stderr)
                buf = []
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
