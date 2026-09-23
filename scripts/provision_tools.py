#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工具打包脚本：把开源工具二进制下载进 tools/，让 geshell 开箱即用。

按当前平台（Linux/Windows/macOS）从官方 GitHub release 拉取二进制，
解压到 tools/<子目录>/<可执行文件>，并自动更新 config/tools.json 的 path。

用法：
  python3 scripts/provision_tools.py [--tools 名称1 名称2 ...] [--jdk] [--gui] [--force]

说明：
- SOURCES 表内是能从官方 release 拉取的开源工具；其余走下方 SPECIAL 分发表里的专用函数
  （sqlmap/netexec/impacket/mongodb/usql/jndi/zap/exploitdb/oracle/xray）。
- --jdk 安装便携 Liberica JDK 8/11/17 到 Java_path/，8 与 11 为 full 版（含 JavaFX），
  供 12 个 jar 类工具使用，无需系统 java。
- --gui 安装 PyQt6 到 tools/_venv，供 main.py/launcher.py 的图形界面使用。
- --jars 还原 14 个 jar 类工具（632 MB，随本仓库的 GitHub Release 分发，见 provision_jars）。
- CobaltStrike/Burp/蚁剑等商业或 GUI 工具不在表内，保持原样，doctor 会提示。
- 同一脚本在 Windows 上重跑一次即可拉取 .exe 版本。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_FILE = os.path.join(BASE_DIR, "config", "tools.json")
TOOLS_DIR = os.path.join(BASE_DIR, "tools")

PLAT = "windows" if os.name == "nt" else ("darwin" if sys.platform == "darwin" else "linux")
EXE = ".exe" if PLAT == "windows" else ""

# 可打包的开源工具：repo + 资产匹配（linux / windows）
SOURCES = {
    "nuclei": {"repo": "projectdiscovery/nuclei",
               "re": r"nuclei_.*_linux_amd64\.zip$", "win_re": r"nuclei_.*_windows_amd64\.zip$",
               "extract": "zip", "subdir": "nuclei", "binary": "nuclei"},
    "httpx": {"repo": "projectdiscovery/httpx",
              "re": r"httpx_.*_linux_amd64\.zip$", "win_re": r"httpx_.*_windows_amd64\.zip$",
              "extract": "zip", "subdir": "httpx", "binary": "httpx"},
    "ffuf": {"repo": "ffuf/ffuf",
             "re": r"ffuf_.*_linux_amd64\.tar\.gz$", "win_re": r"ffuf_.*_windows_amd64\.zip$",
             "extract": "targz", "subdir": "ffuf", "binary": "ffuf"},
    "fscan": {"repo": "shadow1ng/fscan",
              "re": r"fscan_.*_linux_x64$", "win_re": r"fscan_.*_windows_x64\.exe$",
              "extract": "raw", "subdir": "fscan", "binary": "fscan"},
    "dalfox": {"repo": "hahwul/dalfox",
               "re": r"dalfox-.*-linux-x86_64\.tar\.gz$", "win_re": r"dalfox-.*-windows-amd64\.zip$",
               "extract": "targz", "subdir": "dalfox", "binary": "dalfox"},
    "chisel": {"repo": "jpillora/chisel",
               "re": r"chisel_.*_linux_amd64\.gz$", "win_re": r"chisel_.*_windows_amd64\.zip$",
               "extract": "gz", "subdir": "chisel", "binary": "chisel"},
    "frp": {"repo": "fatedier/frp",
            "re": r"frp_.*_linux_amd64\.tar\.gz$", "win_re": r"frp_.*_windows_amd64\.zip$",
            "extract": "targz", "subdir": "frp", "binary": None, "binaries": ["frps", "frpc"]},
    "subfinder": {"repo": "projectdiscovery/subfinder",
                  "re": r"subfinder_.*_linux_amd64\.zip$", "win_re": r"subfinder_.*_windows_amd64\.zip$",
                  "extract": "zip", "subdir": "subfinder", "binary": "subfinder"},
    "naabu": {"repo": "projectdiscovery/naabu",
              "re": r"naabu_.*_linux_amd64\.zip$", "win_re": r"naabu_.*_windows_amd64\.zip$",
              "extract": "zip", "subdir": "naabu", "binary": "naabu"},
    "katana": {"repo": "projectdiscovery/katana",
               "re": r"katana_.*_linux_amd64\.zip$", "win_re": r"katana_.*_windows_amd64\.zip$",
               "extract": "zip", "subdir": "katana", "binary": "katana"},
    "dnsx": {"repo": "projectdiscovery/dnsx",
             "re": r"dnsx_.*_linux_amd64\.zip$", "win_re": r"dnsx_.*_windows_amd64\.zip$",
             "extract": "zip", "subdir": "dnsx", "binary": "dnsx"},
    "uncover": {"repo": "projectdiscovery/uncover",
                "re": r"uncover_.*_linux_amd64\.zip$", "win_re": r"uncover_.*_windows_amd64\.zip$",
                "extract": "zip", "subdir": "uncover", "binary": "uncover"},
    "sqlcmd": {"repo": "microsoft/go-sqlcmd",
               "re": r"sqlcmd-linux-amd64\.tar\.bz2$", "win_re": r"sqlcmd-windows-amd64\.zip$",
               "extract": "tarbz2", "subdir": "sqlcmd", "binary": "sqlcmd"},
    "yasso": {"repo": "sairson/Yasso",
              "re": r"Yasso_linux_x64$", "win_re": r"Yasso_win_x64\.exe$",
              "extract": "raw", "subdir": "yasso", "binary": "Yasso"},
    "urlfinder": {"repo": "pingc0y/URLFinder",
                  "re": r"URLFinder_Linux_x86_64\.tar\.gz$", "win_re": r"URLFinder_Windows_x86_64\.zip$",
                  "extract": "targz", "subdir": "urlfinder", "binary": "URLFinder"},
    "gobuster": {"repo": "OJ/gobuster",
                 "re": r"gobuster_Linux_x86_64\.tar\.gz$", "win_re": r"gobuster_Windows_x86_64\.zip$",
                 "extract": "targz", "subdir": "gobuster", "binary": "gobuster"},
    "sliver": {"repo": "BishopFox/sliver",
               "re": r"sliver-client_linux-amd64$", "win_re": r"sliver-client_windows-amd64\.exe$",
               "extract": "raw", "subdir": "sliver", "binary": "sliver-client"},
    "hashcat": {"repo": "hashcat/hashcat",
                "re": r"hashcat-.*\.7z$", "win_re": r"hashcat-.*\.7z$",
                "extract": "7z", "subdir": "hashcat", "binary": "hashcat",
                "keep_dir": True, "keep_binary": "hashcat.bin"},
}

# 需要被更新的 tools.json 条目名 → (子目录, 二进制名)；frp 拆成 frps/frpc
PATH_MAP = {
    "nuclei": ("nuclei", "nuclei"),
    "httpx": ("httpx", "httpx"),
    "ffuf": ("ffuf", "ffuf"),
    "fscan": ("fscan", "fscan"),
    "dalfox": ("dalfox", "dalfox"),
    "chisel": ("chisel", "chisel"),
    "frps": ("frp", "frps"),
    "frpc": ("frp", "frpc"),
    "sqlmap": ("_venv/bin", "sqlmap"),  # pip 安装，见 provision_sqlmap
}

# 便携 JDK：解压到 Java_path/，目录名沿用 env_manager 内置约定（Java_8_win / Java_11_win）。
#
# 用 BellSoft Liberica 的 "full" 版而非 Temurin：full 版内置 JavaFX，而天狐多数 jar 工具
# 是 JavaFX 写的（shiro/weblogic/thinkphp/jeecg/dbcombo/xxl-job/jenkins），常规 JDK 不含
# JavaFX，运行时报 NoClassDefFoundError: javafx/application/Application。
# Liberica JDK 8 把 JavaFX 放在 jre/lib/ext，扩展类加载器会自动加载，无需 --module-path。
JAVA_PATH_DIR = os.path.join(BASE_DIR, "Java_path")
JDK_TARGETS = {"8": "Java_8_win", "11": "Java_11_win", "17": "Java_17_win"}
LIBERICA_OS = {"linux": "linux", "darwin": "macos", "windows": "windows"}

# mongosh（MongoDB Shell）是直链下载，非 GitHub release；升级时改这里
MONGOSH_VERSION = "2.3.1"

# ---------- 缺失工具的替代品 ----------
# 原工具无法自动获取（商业授权 / 已停止分发 / 原包缺失），用功能等价的免 sudo 开源工具替代：
#   mysql / oracle   → usql（单二进制通用 SQL 客户端，还顺带支持 mssql 等）
#   fastjson / log4j → JNDI-Injection-Exploit（通用 JNDI 注入利用，两者通吃）
#   xray             → OWASP ZAP（被动代理扫描，xray 已停止公开分发）
#   hydra            → patator（多协议在线爆破，pip 安装）
#   netexec          → impacket（协议攻击脚本集，NetExec 本身就基于它）
#   metasploit       → searchsploit（ExploitDB 本地漏洞库检索）
USQL_VERSION = "0.21.5"
JNDI_VERSION = "1.0"
ZAP_VERSION = "2.17.0"   # GitHub API 限流时的兜底版本

# ZAP 要求 Java 17+，而工具类 jar 用的是 JDK 8/11，故用包装脚本把 PATH/JAVA_HOME
# 指向工具箱内置的 JDK 17，避免依赖系统 java。
ZAP_WRAPPER = '''#!/usr/bin/env bash
# zeroxf 包装脚本：ZAP 需要 Java 17+，这里指向工具箱内置的便携 JDK
_here="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
_root="$( cd "${_here}/../.." && pwd )"
if [ -x "${_root}/Java_path/Java_17_win/bin/java" ]; then
  export JAVA_HOME="${_root}/Java_path/Java_17_win"
  export PATH="${JAVA_HOME}/bin:${PATH}"
fi
exec "${_here}/zap.sh" "$@"
'''
ZAP_WRAPPER_BAT = '''@echo off
rem zeroxf 包装脚本：ZAP 需要 Java 17+，指向工具箱内置的便携 JDK
setlocal
set "_HERE=%~dp0"
set "_ROOT=%~dp0..\\.."
if exist "%_ROOT%\\Java_path\\Java_17_win\\bin\\java.exe" (
    set "JAVA_HOME=%_ROOT%\\Java_path\\Java_17_win"
    set "PATH=%JAVA_HOME%\\bin;%PATH%"
)
call "%_HERE%zap.bat" %*
'''

EXPLOITDB_RAW = "https://gitlab.com/exploit-database/exploitdb/-/raw/main"

# searchsploit 启动时必须在脚本同目录找到 .searchsploit_rc，否则直接 exit 1（脚本第 704-710 行）。
# 该文件会被 `source` 执行，所以必须是合法 bash（数组赋值），不能写 "package_array: x" 这种冒号格式。
SEARCHSPLOIT_RC = '''##
## SearchSploit 配置（本文件由 provision_tools.py 自动生成）
## ExploitDB 数据文件与 searchsploit 脚本同目录存放。
##
_ss_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
package_array=("exploitdb" "exploitdb")
path_array+=("${_ss_dir}" "${_ss_dir}")
files_array+=("files_exploits.csv" "files_shellcodes.csv")
'''


def _gh_api(url):
    req = urllib.request.Request(url, headers={"User-Agent": "provision_tools"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _latest_assets(repo):
    d = _gh_api(f"https://api.github.com/repos/{repo}/releases/latest")
    return [a["name"] for a in d.get("assets", [])]


def _download(url, dest, retries=5):
    """流式下载到 dest，支持断点续传。

    远端中途断流时 copyfileobj 会静默读到 EOF 而不报错，留下截断的文件
    （大文件尤其明显，解压时才以 "Unexpected EOF" 暴露）。这里按
    Content-Length 校验完整性；重试时用 Range 请求从断点续传，
    否则 200MB+ 的资产（如 ZAP）在这种网络下几乎不可能一次下完。
    """
    last = None
    for attempt in range(1, retries + 1):
        try:
            have = os.path.getsize(dest) if os.path.exists(dest) else 0
            req = urllib.request.Request(url, headers={"User-Agent": "provision_tools"})
            if have:
                req.add_header("Range", f"bytes={have}-")
            with urllib.request.urlopen(req, timeout=300) as r:
                if have and r.status == 206:
                    # 服务器支持 Range：追加写入，总量 = 已有 + 本次
                    mode = "ab"
                    total = have + int(r.headers.get("Content-Length") or 0)
                else:
                    mode = "wb"      # 不支持 Range（或首次下载）：重头来
                    total = int(r.headers.get("Content-Length") or 0)
                with open(dest, mode) as f:
                    shutil.copyfileobj(r, f)
            got = os.path.getsize(dest)
            if total and got != total:
                done = f"{got}/{total}"
                raise IOError(f"下载不完整 {done} 字节")
            return
        except Exception as e:
            # 416 = Range 越界：本地残留文件已完整（或比远端大），删掉让下次全量重下
            if isinstance(e, urllib.error.HTTPError) and e.code == 416 and os.path.exists(dest):
                try:
                    os.remove(dest)
                    print("[重试] 416 Range 越界，已清除本地残留改为全量下载", flush=True)
                except OSError:
                    pass
            last = e
            print(f"[重试] {attempt}/{retries} 失败: {e}", flush=True)
    raise last


def _ensure_7z(dest_path):
    """确保 7-Zip 命令行工具就位。

    hashcat 的发行包用 BCJ2 过滤器压缩，py7zr 明确不支持
    （报 UnsupportedCompressionMethodError）。Linux 侧通常已随仓库带
    .buildtools/7zz；Windows 侧首次使用时自动拉取独立的 7zr.exe。
    下载失败则返回 False，调用方回退 py7zr（hashcat 会安装失败，但不影响其他工具）。
    """
    if os.path.exists(dest_path):
        return True
    if os.name != "nt":
        return False        # Linux/macOS 走 .buildtools/7zz
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        print("[提示] 需要 7-Zip 命令行工具，正在拉取 7zr.exe")
        _download("https://www.7-zip.org/a/7zr.exe", dest_path)
        if os.path.exists(dest_path):
            print("[完成] 7zr.exe 就位")
            return True
    except Exception as e:
        print(f"[提示] 7zr.exe 获取失败（{e}），将回退 py7zr")
    return False


def _detect_extract(path, declared):
    """按文件魔数推断真正的打包格式，优先于 spec 里声明的 extract。

    同一仓库在不同平台的资产格式常常不同，而 spec 的 extract 只写了一个值：
      chisel     Linux .gz 单文件   / Windows .zip
      ffuf、frp、gobuster、dalfox、urlfinder  Linux .tar.gz / Windows .zip
      sqlcmd     Linux .tar.bz2     / Windows .zip
    照搬声明会在 Windows 端解压失败（例如拿 gzip 去解 ZIP 报 "Not a gzipped file (b'PK')"）。
    这里以魔数为准；gz 与 tar.gz 魔数相同，用 declared/文件名区分。
    """
    try:
        with open(path, "rb") as f:
            magic = f.read(8)
    except OSError:
        return declared
    if magic[:2] == b"PK":
        return "zip"
    if magic[:3] == b"BZh":
        return "tarbz2"
    if magic[:6] == b"7z\xbc\xaf\x27\x1c":
        return "7z"
    if magic[:2] == b"\x1f\x8b":
        if declared == "targz" or path.lower().endswith(".tar.gz"):
            return "targz"
        return "gz"
    return declared or "raw"


def _extract(archive, dest_dir, extract):
    os.makedirs(dest_dir, exist_ok=True)
    if extract == "zip":
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest_dir)
    elif extract == "targz":
        subprocess.check_call(["tar", "xzf", archive, "-C", dest_dir])
    elif extract == "tarbz2":
        subprocess.check_call(["tar", "xjf", archive, "-C", dest_dir])
    elif extract == "7z":
        # 7z 解压：优先用 7-Zip 二进制（支持 BCJ2），否则回退 py7zr。
        # hashcat 的包用了 BCJ2 过滤器，而 py7zr 明确不支持，Windows 端必须靠 7zr.exe。
        seven_zip = os.path.join(BASE_DIR, ".buildtools",
                                 "7zz" if os.name != "nt" else "7zr.exe")
        if not os.path.exists(seven_zip):
            _ensure_7z(seven_zip)
        if os.path.exists(seven_zip):
            subprocess.check_call([seven_zip, "x", archive, f"-o{dest_dir}", "-y"])
            return
        venv_py = os.path.join(TOOLS_DIR, "_venv",
                               "Scripts" if os.name == "nt" else "bin",
                               "python" + (".exe" if os.name == "nt" else ""))
        code = (f"import py7zr; py7zr.SevenZipFile({archive!r}, 'r').extractall({dest_dir!r})")
        if os.path.exists(venv_py):
            subprocess.check_call([venv_py, "-c", code])
        else:
            import py7zr
            py7zr.SevenZipFile(archive, "r").extractall(dest_dir)
    if extract == "gz":
        out = os.path.join(dest_dir, os.path.basename(archive)[:-3])
        with open(archive, "rb") as fi, open(out, "wb") as fo:
            import gzip
            fo.write(gzip.decompress(fi.read()))
        return out
    elif extract == "raw":
        shutil.copy(archive, dest_dir)
        return os.path.join(dest_dir, os.path.basename(archive))


def _find_binary(dest_dir, binary):
    for root, _, files in os.walk(dest_dir):
        for fn in files:
            base, ext = os.path.splitext(fn)
            if base == binary or (base + ".exe" == fn and binary + ".exe" == fn):
                return os.path.join(root, fn)
            if binary in ("frps", "frpc") and fn in (binary, binary + ".exe"):
                return os.path.join(root, fn)
    return None


def provision_github(name, spec):
    repo = spec["repo"]
    pattern = spec["win_re"] if PLAT == "windows" else spec["re"]
    assets = _latest_assets(repo)
    asset = next((a for a in assets if re.search(pattern, a)), None)
    if not asset:
        print(f"[跳过] {name}: 平台 {PLAT} 无匹配资产")
        return None
    url = f"https://github.com/{repo}/releases/latest/download/{asset}"
    archive = os.path.join(TOOLS_DIR, f".tmp_{asset}")
    # tmp_out 必须定义在 try 之外：下载失败时 finally 仍会遍历它清理，
    # 若留在 try 内会抛 UnboundLocalError，把真实的下载错误盖掉。
    tmp_out = os.path.join(TOOLS_DIR, f".tmp_out_{spec['subdir']}")
    try:
        print(f"[下载] {name} ← {asset}")
        _download(url, archive)
        subdir = os.path.join(TOOLS_DIR, spec["subdir"])
        shutil.rmtree(tmp_out, ignore_errors=True)
        # 以实际文件魔数为准：同一仓库的 Linux/Windows 资产打包格式可能不同
        # （chisel 是 .gz vs .zip；ffuf/frp/gobuster 等是 .tar.gz vs .zip）
        fmt = _detect_extract(archive, spec["extract"])
        _extract(archive, tmp_out, fmt)

        placed = []
        if spec.get("keep_dir"):
            # 整个框架目录保留（如 hashcat：需 OpenCL/modules/rules 支持文件）
            subdirs = [os.path.join(tmp_out, d) for d in os.listdir(tmp_out)
                       if os.path.isdir(os.path.join(tmp_out, d))]
            if not subdirs:
                print(f"[失败] {name}: keep_dir 模式下未找到子目录")
                return None
            src_dir = subdirs[0]
            target_dir = os.path.join(TOOLS_DIR, spec["subdir"])
            shutil.rmtree(target_dir, ignore_errors=True)
            shutil.copytree(src_dir, target_dir)
            keep_binary = spec["keep_binary"]
            exe_name = "hashcat.exe" if PLAT == "windows" else keep_binary
            bin_path = os.path.join(target_dir, exe_name)
            if not os.path.exists(bin_path):
                print(f"[失败] {name}: 未找到 {exe_name}")
                return None
            os.chmod(bin_path, 0o755)
            placed.append((spec["subdir"], exe_name))
        elif fmt in ("gz", "raw"):
            # 单文件：解压产物即二进制，直接移动到目标名
            files = [os.path.join(tmp_out, f) for f in os.listdir(tmp_out)
                     if os.path.isfile(os.path.join(tmp_out, f))]
            if not files:
                print(f"[失败] {name}: gz 解压无产物")
                return None
            target = os.path.join(TOOLS_DIR, spec["subdir"], spec["binary"] + EXE)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.move(files[0], target)
            if PLAT != "windows":
                os.chmod(target, 0o755)
            placed.append((spec["subdir"], spec["binary"]))
        else:
            binaries = spec["binaries"] if spec.get("binaries") else [spec["binary"]]
            for b in binaries:
                src = _find_binary(tmp_out, b)
                if not src:
                    print(f"[失败] {name}: 未在包内找到 {b}")
                    continue
                target = os.path.join(TOOLS_DIR, spec["subdir"], b + EXE)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.move(src, target)
                if PLAT != "windows":
                    os.chmod(target, 0o755)
                placed.append((spec["subdir"], b))
        return placed
    finally:
        for p in (archive, tmp_out):
            try:
                if os.path.isdir(p):
                    shutil.rmtree(p, ignore_errors=True)
                elif os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass


def provision_sqlmap():
    return _provision_pip("sqlmap", "sqlmap")


# NetExec 依赖中 PyPI 上取得到的那部分。
# 另有 certipy-ad、pynfsclient 两个是 git 依赖，clone 在受限网络下极易失败，
# 这里跳过——它们只影响 AD CS / NFS 相关的子命令，不影响 SMB/WinRM/LDAP 等主协议。
NETEXEC_PYPI_DEPS = [
    "termcolor", "argcomplete", "asyauth", "beautifulsoup4", "bloodhound-ce",
    "certihound", "cryptography", "dploot", "dsinternals", "jwt", "lsassy",
    "masky", "minikerberos", "msldap", "netaddr", "netifaces", "paramiko",
    "pefile", "pycryptodome", "pypykatz", "pypsrp", "pyperclip",
    "python-libnmap", "python-dateutil", "rich", "sqlalchemy", "tabulate",
    "terminaltables3", "unicrypto", "winacl", "xmltodict",
]

# aardwolf（Rust 实现）在 PyPI 只有 sdist，装它需要完整 Rust 工具链；
# 但官方 release 提供各 Python ABI 的预编译 wheel，用它可完全免掉编译器。
AARDWOLF_TAG = "0.2.12"


def _aardwolf_wheel_url():
    """返回当前平台/Python 对应的 aardwolf 预编译 wheel 地址，无则 None。"""
    abi = f"cp{sys.version_info.major}{sys.version_info.minor}"
    base = f"https://github.com/skelsec/aardwolf/releases/download/{AARDWOLF_TAG}"
    if PLAT == "windows":
        return f"{base}/aardwolf-{AARDWOLF_TAG}-{abi}-{abi}-win_amd64.whl"
    if PLAT == "linux":
        many = "manylinux_2_17_x86_64.manylinux2014_x86_64"
        return f"{base}/aardwolf-{AARDWOLF_TAG}-{abi}-{abi}-{many}.whl"
    return None


def provision_netexec():
    """安装 NetExec。

    这条路有三个坑，缺一个都装不上：

    1. PyPI 上没有它的发行包（netexec / nxc / netexec-py 全 404），只能从源码装；
    2. 它用 poetry-dynamic-versioning 从 git 元数据推导版本号，而源码 zip 没有
       .git，pip 在生成元数据阶段就会失败——必须设
       POETRY_DYNAMIC_VERSIONING_BYPASS 绕过；
    3. 它依赖 aardwolf（Rust 实现）。PyPI 只有 sdist、编译要 Rust 工具链 + C 编译器，
       但官方 release 有各 ABI 的预编译 wheel，优先用它；
       其余 git 依赖易失败，故先用 --no-deps 装主体，再补 PyPI 上取得到的依赖。
    """
    venv = os.path.join(TOOLS_DIR, "_venv")
    bindir = os.path.join(venv, "Scripts" if PLAT == "windows" else "bin")
    py = os.path.join(bindir, "python" + EXE)
    pip = os.path.join(bindir, "pip" + EXE)
    if not os.path.exists(py):
        subprocess.check_call([sys.executable, "-m", "venv", venv])

    # 1) aardwolf：优先预编译 wheel，避免要求 Rust 工具链
    try:
        if subprocess.run([py, "-c", "import aardwolf"],
                          capture_output=True).returncode != 0:
            url = _aardwolf_wheel_url()
            if url:
                print(f"[下载] aardwolf ← {AARDWOLF_TAG} 预编译 wheel（免编译）")
                subprocess.check_call([pip, "install", "-q", "--no-deps", url])
            else:
                print("[提示] 当前平台无 aardwolf 预编译 wheel，将回退源码编译（需 Rust）")
    except Exception as e:
        print(f"[提示] aardwolf 预编译包安装失败（{e}），将回退源码编译")

    # 2) NetExec 主体 + 3) 补齐依赖
    archive = os.path.join(TOOLS_DIR, ".tmp_netexec.zip")
    env = os.environ.copy()
    env["POETRY_DYNAMIC_VERSIONING_BYPASS"] = "0.0.0"
    try:
        print("[下载] NetExec ← 源码 zip")
        _download("https://codeload.github.com/Pennyw0rth/NetExec/zip/refs/heads/main",
                  archive)
        subprocess.check_call([pip, "install", "-q", "--no-deps", archive], env=env)
        print("[下载] NetExec 依赖（PyPI 部分）")
        subprocess.check_call([pip, "install", "-q", *NETEXEC_PYPI_DEPS])
    except Exception as e:
        print(f"[失败] netexec: {e}")
        return None
    finally:
        _drop(archive)

    exe = os.path.join(bindir, "nxc" + EXE)
    if not os.path.exists(exe):
        print("[失败] netexec: 安装后未找到 nxc 入口")
        return None
    return [("_venv", os.path.relpath(exe, TOOLS_DIR))]


def _liberica_url(ver):
    """查 BellSoft API 取含 JavaFX 的 full 版 JDK 下载地址；失败返回 None。"""
    osname = LIBERICA_OS.get(PLAT, "linux")
    api = (f"https://api.bell-sw.com/v1/liberica/releases?version-feature={ver}"
           f"&os={osname}&arch=x86&bundle-type=jdk-full&output=json")
    req = urllib.request.Request(api, headers={"User-Agent": "provision_tools"})
    with urllib.request.urlopen(req, timeout=60) as r:
        releases = json.load(r)
    if not releases:
        return None
    v = releases[0]["version"]
    ext = "zip" if PLAT == "windows" else "tar.gz"
    return f"https://download.bell-sw.com/java/{v}/bellsoft-jdk{v}-{osname}-amd64-full.{ext}"


def provision_jdk(versions=("8", "11"), force=False):
    """下载 Temurin（Adoptium）JDK 到 Java_path/，目录名沿用 env_manager 内置约定。

    env_manager.get_java_home 会读 config/settings.json 的 java8_path/java11_path，
    其默认值已指向 Java_path/Java_{8,11}_win/bin，故此处无需改配置。
    """
    placed = []
    for ver in versions:
        dest_dir = os.path.join(JAVA_PATH_DIR, JDK_TARGETS[ver])
        if not force and os.path.exists(os.path.join(dest_dir, "bin", "java" + EXE)):
            print(f"[已有] JDK {ver} 已安装，跳过（--force 重新下载）")
            placed.append(ver)
            continue
        archive = os.path.join(TOOLS_DIR, f".tmp_jdk{ver}.tar.gz")
        tmp_out = os.path.join(TOOLS_DIR, f".tmp_jdk{ver}")
        try:
            url = _liberica_url(ver)
            if not url:
                print(f"[失败] JDK {ver}: 未取到下载地址")
                continue
            print(f"[下载] JDK {ver} ← Liberica full {os.path.basename(url)}")
            _download(url, archive)
            shutil.rmtree(tmp_out, ignore_errors=True)
            os.makedirs(tmp_out, exist_ok=True)
            subprocess.check_call(["tar", "xzf", archive, "-C", tmp_out])
            entries = [os.path.join(tmp_out, d) for d in os.listdir(tmp_out)
                       if os.path.isdir(os.path.join(tmp_out, d))]
            if not entries:
                print(f"[失败] JDK {ver}: 解压后无顶层目录")
                continue
            os.makedirs(JAVA_PATH_DIR, exist_ok=True)
            shutil.rmtree(dest_dir, ignore_errors=True)
            shutil.move(entries[0], dest_dir)
            java_bin = os.path.join(dest_dir, "bin", "java" + EXE)
            if not os.path.exists(java_bin):
                print(f"[失败] JDK {ver}: 未找到 {java_bin}")
                continue
            if PLAT != "windows":
                os.chmod(java_bin, 0o755)
            print(f"[完成] JDK {ver} → {os.path.relpath(dest_dir, BASE_DIR)}")
            placed.append(ver)
        except Exception as e:
            print(f"[失败] JDK {ver}: {e}")
        finally:
            for p in (archive, tmp_out):
                try:
                    if os.path.isdir(p):
                        shutil.rmtree(p, ignore_errors=True)
                    elif os.path.exists(p):
                        os.remove(p)
                except OSError:
                    pass
    return placed


def provision_mongosh(force=False):
    """下载 mongosh（MongoDB Shell）到 tools/mongodb/mongosh。"""
    target_dir = os.path.join(TOOLS_DIR, "mongodb")
    target = os.path.join(target_dir, "mongosh" + EXE)
    if not force and os.path.exists(target):
        print("[已有] mongodb 已打包，跳过（--force 重新下载）")
        return [("mongodb", "mongosh")]
    # MongoDB 的命名规则与其他工具都不同：Windows 是 win32-x64.zip
    # （不是 windows，也不是 .tgz），Linux/macOS 是 <plat>-x64.tgz
    if PLAT == "windows":
        asset = f"mongosh-{MONGOSH_VERSION}-win32-x64.zip"
    else:
        asset = f"mongosh-{MONGOSH_VERSION}-{PLAT}-x64.tgz"
    archive = os.path.join(TOOLS_DIR, f".tmp_{asset}")
    tmp_out = os.path.join(TOOLS_DIR, ".tmp_out_mongosh")
    try:
        print(f"[下载] mongodb ← {asset}")
        _download(f"https://downloads.mongodb.com/compass/{asset}", archive)
        shutil.rmtree(tmp_out, ignore_errors=True)
        os.makedirs(tmp_out, exist_ok=True)
        _extract(archive, tmp_out, _detect_extract(archive, "targz"))
        src = None
        for root, _, files in os.walk(tmp_out):
            if os.path.basename(root) == "bin" and "mongosh" + EXE in files:
                src = os.path.join(root, "mongosh" + EXE)
                break
        if not src:
            print("[失败] mongodb: 包内未找到 bin/mongosh")
            return None
        os.makedirs(target_dir, exist_ok=True)
        shutil.move(src, target)
        if PLAT != "windows":
            os.chmod(target, 0o755)
        return [("mongodb", "mongosh")]
    except Exception as e:
        print(f"[失败] mongodb: {e}")
        return None
    finally:
        for p in (archive, tmp_out):
            try:
                if os.path.isdir(p):
                    shutil.rmtree(p, ignore_errors=True)
                elif os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass


def _provision_pip(package, entry):
    venv = os.path.join(TOOLS_DIR, "_venv")
    bindir = os.path.join(venv, "Scripts" if PLAT == "windows" else "bin")
    if not os.path.isdir(bindir):
        print(f"[下载] {package} → pip 安装到 tools/_venv")
        subprocess.check_call([sys.executable, "-m", "venv", venv])
    pip = os.path.join(bindir, "pip" + EXE)
    try:
        subprocess.check_call([pip, "install", "-q", "--upgrade", package])
    except subprocess.CalledProcessError:
        print(f"[失败] {package}: pip 安装失败（包名可能不同）")
        return None
    exe = os.path.join(bindir, entry + EXE)
    if not os.path.exists(exe):
        print(f"[失败] {package}: pip 安装后未找到入口 {entry}")
        return None
    rel = os.path.relpath(exe, TOOLS_DIR)
    return [("_venv", rel)]


def _gh_latest_asset(repo, pattern):
    """返回 GitHub 最新 release 中匹配 pattern 的资产名，无则 None。"""
    d = _gh_api(f"https://api.github.com/repos/{repo}/releases/latest")
    for a in d.get("assets", []):
        if re.search(pattern, a["name"]):
            return a["name"]
    return None


def _drop(*paths):
    """静默清理临时文件/目录（忽略 None）。"""
    for p in paths:
        if not p:
            continue
        try:
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.exists(p):
                os.remove(p)
        except OSError:
            pass


def provision_usql(force=False):
    """下载 usql（通用 SQL 客户端）到 tools/usql/usql。

    替代 mysql / oracle 客户端：单个二进制即可连 MySQL/MariaDB/PostgreSQL/Oracle/MSSQL。
    """
    target = os.path.join(TOOLS_DIR, "usql", "usql" + EXE)
    if not force and os.path.exists(target):
        print("[已有] usql 已打包，跳过（--force 重新下载）")
        return [("usql", "usql")]
    # 两平台资产格式不同：Windows 是 .zip（内含 usql.exe），Linux/macOS 是 .tar.bz2 单文件
    if PLAT == "windows":
        asset = f"usql-{USQL_VERSION}-windows-amd64.zip"
    else:
        asset = f"usql-{USQL_VERSION}-{PLAT}-amd64.tar.bz2"
    url = f"https://github.com/xo/usql/releases/download/v{USQL_VERSION}/{asset}"
    archive = os.path.join(TOOLS_DIR, f".tmp_{asset}")
    tmp_out = os.path.join(TOOLS_DIR, ".tmp_out_usql")
    try:
        print(f"[下载] usql ← {asset}")
        _download(url, archive)
        shutil.rmtree(tmp_out, ignore_errors=True)
        os.makedirs(tmp_out, exist_ok=True)
        _extract(archive, tmp_out, _detect_extract(archive, "tarbz2"))
        src = os.path.join(tmp_out, "usql" + EXE)
        if not os.path.exists(src):
            print("[失败] usql: 包内未找到 usql 可执行文件")
            return None
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.move(src, target)
        if PLAT != "windows":
            os.chmod(target, 0o755)
        return [("usql", "usql")]
    except Exception as e:
        print(f"[失败] usql: {e}")
        return None
    finally:
        _drop(archive, tmp_out)


def provision_jndi(force=False):
    """下载 JNDI-Injection-Exploit 到 tools/jndi/。

    通用 JNDI 注入利用服务，一并覆盖 fastjson 反序列化与 log4j2 (CVE-2021-44228) 的利用。
    """
    jar_name = f"JNDI-Injection-Exploit-{JNDI_VERSION}-SNAPSHOT-all.jar"
    target_dir = os.path.join(TOOLS_DIR, "jndi")
    target = os.path.join(target_dir, jar_name)
    if not force and os.path.exists(target):
        print("[已有] jndi 已打包，跳过（--force 重新下载）")
        return [("jndi", jar_name)]
    url = (f"https://github.com/welk1n/JNDI-Injection-Exploit/releases/download/"
           f"v{JNDI_VERSION}/{jar_name}")
    try:
        print(f"[下载] jndi ← {jar_name}")
        os.makedirs(target_dir, exist_ok=True)
        _download(url, target)
        return [("jndi", jar_name)]
    except Exception as e:
        print(f"[失败] jndi: {e}")
        _drop(target)
        return None


ORACLE_IC_BASE = "https://download.oracle.com/otn_software/linux/instantclient"

# chaitin/xray 的 releases/latest 已被 xpoc 顶替，官方下载站 download.xray.cool 已 404，
# 但按固定版本号仍能取到旧资产。首次运行会自动生成 module/plugin/xray.yaml。
XRAY_VERSION = "1.9.11"


def provision_xray(force=False):
    """下载 xray 到 tools/xray/（替代 config/tools.json 里标为"需自备"的 xray）。"""
    target_dir = os.path.join(TOOLS_DIR, "xray")
    target = os.path.join(target_dir, "xray" + EXE)
    if not force and os.path.exists(target):
        print("[已有] xray 已打包，跳过（--force 重新下载）")
        return [("xray", "xray")]
    asset = "xray_windows_amd64.exe.zip" if PLAT == "windows" else "xray_linux_amd64.zip"
    url = (f"https://github.com/chaitin/xray/releases/download/"
           f"{XRAY_VERSION}/{asset}")
    archive = os.path.join(TOOLS_DIR, f".tmp_{asset}")
    try:
        print(f"[下载] xray ← {asset}")
        _download(url, archive)
        tmp_out = os.path.join(TOOLS_DIR, ".tmp_out_xray")
        shutil.rmtree(tmp_out, ignore_errors=True)
        os.makedirs(tmp_out, exist_ok=True)
        _extract(archive, tmp_out, "zip")
        src = None
        for root, _, files in os.walk(tmp_out):
            for fn in files:
                if fn.startswith("xray_") or fn == "xray" + EXE:
                    src = os.path.join(root, fn)
                    break
            if src:
                break
        if not src:
            print("[失败] xray: 包内未找到 xray 可执行文件")
            return None
        os.makedirs(target_dir, exist_ok=True)
        shutil.move(src, target)
        if PLAT != "windows":
            os.chmod(target, 0o755)
        _drop(tmp_out)
        return [("xray", "xray")]
    except Exception as e:
        print(f"[失败] xray: {e}")
        return None
    finally:
        _drop(archive)

# sqlplus 需从同目录的 Instant Client 加载共享库（LD_LIBRARY_PATH），
# 另外系统需有 libaio.so.1（Ubuntu 24.04 的 libaio1t64 只提供 libaio.so.1t64，要手动链接）。
ORACLE_WRAPPER = '''#!/usr/bin/env bash
# zeroxf 包装脚本：sqlplus 需要 Instant Client 的共享库路径
_here="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
_ic="$( ls -d "${_here}"/instantclient_* 2>/dev/null | head -1 )"
if [ -n "${_ic}" ]; then
  export LD_LIBRARY_PATH="${_ic}:${LD_LIBRARY_PATH}"
  exec "${_ic}/sqlplus" "$@"
fi
echo "未找到 Instant Client 目录" >&2
exit 1
'''


ORACLE_WRAPPER_BAT = '''@echo off
rem zeroxf 包装脚本：sqlplus.exe 需要 Instant Client 目录下的 DLL 才能启动
setlocal
set "_HERE=%~dp0"
set "_IC="
for /d %%D in ("%_HERE%instantclient_*") do set "_IC=%%D"
if not defined _IC (
    echo 未找到 Instant Client 目录 1>&2
    exit /b 1
)
set "PATH=%_IC%;%PATH%"
"%_IC%\\sqlplus.exe" %*
'''


ORACLE_IC_WIN_HINT = """[跳过] oracle：Oracle 不为 Windows 版 Instant Client 提供免登录直链。

  Linux 版可以自动下载，但 Windows 版必须从官网手动获取（需 Oracle 账号）：
    https://www.oracle.com/database/technologies/instant-client/winx64-64-downloads.html

  下载这两个包并解压到本目录（tools/oracle/）即可自动生效：
    instantclient-basiclite-windows.x64-*.zip
    instantclient-sqlplus-windows.x64-*.zip
  本脚本会检测到 instantclient_* 目录并生成 sqlplus.bat 包装。"""


def provision_oracle(force=False):
    """下载 Oracle Instant Client + SQL*Plus 到 tools/oracle/。

    Linux 版的下载地址是公开的，不需要 Oracle 账号——原 tools.json 把它标成
    "需自备"是过虑了。Windows 版则相反：Oracle 只给登录用户，因此单独提示。
    sqlplus 依赖同目录的 IC 共享库；Linux 还需系统 libaio.so.1。
    """
    target_dir = os.path.join(TOOLS_DIR, "oracle")
    entry_name = "sqlplus.bat" if PLAT == "windows" else "sqlplus.sh"
    if not force and os.path.exists(os.path.join(target_dir, entry_name)):
        print("[已有] oracle 已打包，跳过（--force 重新下载）")
        return [("oracle", entry_name)]
    if PLAT == "windows":
        # Windows 版 Instant Client 拿不到免登录直链（见 ORACLE_IC_WIN_HINT）。
        # 若用户已手动解压进来，只补一个包装脚本即可；否则明确说明而不是
        # 误下载 Linux 版（那会导致 sqlplus.bat 调用一个 ELF 文件）。
        have_ic = os.path.isdir(target_dir) and any(
            d.startswith("instantclient_") for d in os.listdir(target_dir))
        if have_ic:
            wrapper = os.path.join(target_dir, "sqlplus.bat")
            with open(wrapper, "w", encoding="gbk", newline="\r\n") as f:
                f.write(ORACLE_WRAPPER_BAT)
            print("[完成] oracle：检测到手动放入的 Instant Client，已生成 sqlplus.bat")
            return [("oracle", "sqlplus.bat")]
        print(ORACLE_IC_WIN_HINT)
        return None
    try:
        os.makedirs(target_dir, exist_ok=True)
        for name in ("instantclient-basiclite-linuxx64.zip",
                     "instantclient-sqlplus-linuxx64.zip"):
            archive = os.path.join(TOOLS_DIR, f".tmp_{name}")
            print(f"[下载] oracle ← {name}")
            _download(f"{ORACLE_IC_BASE}/{name}", archive)
            _extract(archive, target_dir, "zip")
            _drop(archive)
        ic_dir = next((os.path.join(target_dir, d) for d in os.listdir(target_dir)
                       if d.startswith("instantclient_")), None)
        if not ic_dir:
            print("[失败] oracle: 解压后未找到 instantclient_* 目录")
            return None
        # 清掉 zip 顶层散落的 LICENSE/README，只留 IC 目录与包装脚本
        for f in os.listdir(target_dir):
            p = os.path.join(target_dir, f)
            if os.path.isfile(p):
                os.remove(p)
        entry = os.path.join(ic_dir, "sqlplus")
        if os.path.exists(entry):
            os.chmod(entry, 0o755)
        # Windows 无法执行 .sh，且 sqlplus.exe 需要 Instant Client 的 DLL 在 PATH 里，
        # 所以两端各生成对应形式的包装脚本（内容等价，形式按平台）
        if PLAT == "windows":
            wrapper = os.path.join(target_dir, "sqlplus.bat")
            with open(wrapper, "w", encoding="gbk", newline="\r\n") as f:
                f.write(ORACLE_WRAPPER_BAT)
        else:
            wrapper = os.path.join(target_dir, "sqlplus.sh")
            with open(wrapper, "w", encoding="utf-8") as f:
                f.write(ORACLE_WRAPPER)
            os.chmod(wrapper, 0o755)
        return [("oracle", entry_name)]
    except Exception as e:
        print(f"[失败] oracle: {e}")
        return None


def _write_zap_wrapper(target_dir):
    """生成 ZAP 包装脚本（注入内置 JDK 17）。

    返回的入口名两端统一为 zap-tianhu.sh，以保证 config/tools.json 保持
    单一数据源；Windows 上实际落盘的是 zap-tianhu.bat，由 cli_runner 的
    _win_exec_argv 自动把 .sh 换成 .bat。
    """
    if PLAT == "windows":
        wrapper = os.path.join(target_dir, "zap-tianhu.bat")
        with open(wrapper, "w", encoding="gbk", newline="\r\n") as f:
            f.write(ZAP_WRAPPER_BAT)
        return "zap-tianhu.sh"      # 逻辑名，两端一致
    wrapper = os.path.join(target_dir, "zap-tianhu.sh")
    with open(wrapper, "w", encoding="utf-8") as f:
        f.write(ZAP_WRAPPER)
    os.chmod(wrapper, 0o755)
    return "zap-tianhu.sh"


def provision_zap(force=False):
    """下载 OWASP ZAP 到 tools/zap/（替代已停止公开分发的 xray）。

    ZAP 是 Java 应用，运行时需 JDK（本项目已装机便携 JDK）。
    """
    target_dir = os.path.join(TOOLS_DIR, "zap")
    if not force and os.path.exists(os.path.join(target_dir, "zap.sh")):
        print("[已有] zap 已打包，跳过（--force 重新下载）")
        return [("zap", _write_zap_wrapper(target_dir))]
    archive = None
    tmp_out = os.path.join(TOOLS_DIR, ".tmp_out_zap")
    try:
        # 注意 ZAP 的资产命名两平台不一致：Linux 是 ZAP_2.17.0_Linux.tar.gz（点号），
        # Windows 是 ZAP_2_17_0_windows.exe（下划线），所以正则要放宽。
        # 另外 Windows 那个 .exe 其实是**安装程序**而非压缩包，无法直接解压，
        # 因此 Windows 端改用同样可用的 ZAP_*_Crossplatform.zip（标准 zip）。
        if PLAT == "windows":
            pattern = r"ZAP_[0-9._]*Crossplatform\.zip$"
            fallback = f"ZAP_{ZAP_VERSION}_Crossplatform.zip"
        else:
            pattern = r"ZAP_[0-9._]*Linux\.tar\.gz$"
            fallback = f"ZAP_{ZAP_VERSION}_Linux.tar.gz"
        try:
            asset = _gh_latest_asset("zaproxy/zaproxy", pattern)
        except Exception as e:
            # GitHub API 会匿名限流（403），此时退回已知版本号
            print(f"[提示] 查询最新版失败（{e}），改用兜底版本 {ZAP_VERSION}")
            asset = None
        if not asset:
            asset = fallback
        # 取版本号：兼容 2.17.0 与 2_17_0 两种写法
        ver = re.search(r"ZAP_([\d._]+?)_(?:Linux|Crossplatform)", asset).group(1).replace("_", ".")
        url = f"https://github.com/zaproxy/zaproxy/releases/download/v{ver}/{asset}"
        archive = os.path.join(TOOLS_DIR, f".tmp_{asset}")
        print(f"[下载] zap ← {asset}")
        _download(url, archive)
        shutil.rmtree(tmp_out, ignore_errors=True)
        os.makedirs(tmp_out, exist_ok=True)
        _extract(archive, tmp_out, _detect_extract(archive, "targz"))
        tops = [os.path.join(tmp_out, d) for d in os.listdir(tmp_out)
                if os.path.isdir(os.path.join(tmp_out, d))]
        if not tops:
            print("[失败] zap: 解压后无顶层目录")
            return None
        shutil.rmtree(target_dir, ignore_errors=True)
        shutil.move(tops[0], target_dir)
        entry = os.path.join(target_dir, "zap.sh")
        if os.path.exists(entry) and PLAT != "windows":
            os.chmod(entry, 0o755)
        return [("zap", _write_zap_wrapper(target_dir))]
    except Exception as e:
        print(f"[失败] zap: {e}")
        return None
    finally:
        _drop(archive, tmp_out)


# Windows 端需要系统级安装的工具：(命令名, winget 包 ID)
# winget 随 Windows 10 1809+ 自带，无需额外装包管理器。
WINGET_PACKAGES = [
    ("nmap", "Insecure.Nmap"),
    ("mysql", "Oracle.MySQL"),
]
# Metasploit 官方 MSI（Rapid7），支持 /qn 静默安装；winget 源里没有它
METASPLOIT_MSI = "https://windows.metasploit.com/metasploitframework-latest.msi"


def provision_win_deps(force=False):
    """Windows 端补装系统级命令行工具（nmap / MySQL 客户端 / Metasploit）。

    这些不是「解压即用」的单文件，必须走系统安装：

    - nmap、MySQL 客户端 → winget（Windows 10 1809+ 自带）
    - Metasploit          → Rapid7 官方 MSI，用 msiexec /qn 静默安装

    hydra 无法安装：它的原版只支持类 Unix，winget 源里同名的是游戏启动器，
    第三方编译版来源不可靠。爆破需求可由 nmap 的 NSE brute 脚本覆盖
    （装好 nmap 后即可用）：
        nmap -p22 --script ssh-brute --script-args userdb=u.txt,passdb=p.txt TARGET
    """
    if PLAT != "windows":
        print("[跳过] 系统依赖安装仅适用于 Windows")
        return False
    ok = True

    # 1) winget 包
    if shutil.which("winget"):
        for cmd, pkg in WINGET_PACKAGES:
            if shutil.which(cmd) and not force:
                print(f"[已有] {cmd} 已在 PATH，跳过")
                continue
            print(f"[安装] {pkg}（winget，可能需要几分钟）")
            try:
                subprocess.check_call([
                    "winget", "install", "--id", pkg, "-e",
                    "--accept-package-agreements", "--accept-source-agreements",
                    "--disable-interactivity",
                ])
            except Exception as e:
                print(f"[失败] {pkg}: {e}")
                ok = False
    else:
        print("[失败] 未找到 winget（需要 Windows 10 1809 及以上）")
        ok = False

    # 2) Metasploit（官方 MSI 静默安装，约 700 MB）
    if shutil.which("msfconsole") and not force:
        print("[已有] metasploit 已安装，跳过")
    else:
        print("[下载] Metasploit 官方 MSI（约 380MB，静默安装）")
        msi = os.path.join(TOOLS_DIR, ".tmp_msf.msi")
        try:
            _download(METASPLOIT_MSI, msi)
            # 必须从原始文件安装，且安装期间不能删除它——否则 MSI 会因
            # 找不到安装源而报 1603（SOURCEMGMT: Failed to resolve source）。
            subprocess.check_call(["msiexec", "/i", msi, "/qn", "/norestart"])
            if not shutil.which("msfconsole"):
                # 实测部分环境下 msiexec 返回 0 但文件并未落地（MSI 日志里
                # 是 1603 + Failed to resolve source），因此这里以结果为准判断
                print("[提示] msiexec 已执行，但未检测到 msfconsole——")
                print("       该 MSI 的静默安装在此环境不生效，请手动双击安装：")
                print(f"       {METASPLOIT_MSI}")
                ok = False
        except Exception as e:
            print(f"[失败] metasploit: {e}")
            ok = False
        finally:
            _drop(msi)

    print("[说明] hydra 无 Windows 官方版本，未安装；"
          "爆破需求可用 nmap 的 NSE brute 脚本覆盖")
    return ok


def provision_gui(force=False):
    """安装 GUI 依赖（PyQt6）到 tools/_venv。

    main.py / launcher.py / loader.py 是 PyQt6 应用，但 PyQt6 只提供库、
    没有命令行入口，走不了 _provision_pip（那个函数要校验入口脚本存在），
    因此单独处理。
    """
    venv = os.path.join(TOOLS_DIR, "_venv")
    bindir = os.path.join(venv, "Scripts" if PLAT == "windows" else "bin")
    py = os.path.join(bindir, "python" + EXE)
    if not os.path.exists(py):
        print("[提示] 未找到 tools/_venv，正在创建")
        subprocess.check_call([sys.executable, "-m", "venv", venv])
    if not force:
        r = subprocess.run([py, "-c", "import PyQt6.QtWidgets"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            print("[已有] PyQt6 已安装，跳过（--force 重装）")
            return True
    # PyQt6 会连带拉 Qt6 运行时（约 90MB），是这里最大的单个依赖
    print("[下载] PyQt6 → GUI 运行时依赖（约 90MB）")
    try:
        subprocess.check_call([os.path.join(bindir, "pip" + EXE),
                               "install", "--upgrade", "PyQt6"])
        return True
    except subprocess.CalledProcessError as e:
        print(f"[失败] PyQt6: {e}")
        return False


def provision_impacket():
    # impacket 是一组协议攻击脚本，NetExec 本身即基于它；入口取常用的 secretsdump
    return _provision_pip("impacket", "impacket-secretsdump")


def provision_oracledb(force=False):
    """安装 python-oracledb 到 tools/_venv。

    Oracle 官方不提供 Windows 版 Instant Client 的免登录下载，但
    python-oracledb 的 **thin 模式是纯 Python 实现**，不需要任何 Oracle
    客户端库就能连库——因此 Windows 端也能用上 Oracle 客户端能力。

    这里只负责装库；CLI 包装是仓库自带的 tools/oracle-py/oracle_cli.py，
    无需额外下载。
    """
    venv = os.path.join(TOOLS_DIR, "_venv")
    bindir = os.path.join(venv, "Scripts" if PLAT == "windows" else "bin")
    py = os.path.join(bindir, "python" + EXE)
    if not os.path.exists(py):
        subprocess.check_call([sys.executable, "-m", "venv", venv])
    if not force:
        r = subprocess.run([py, "-c", "import oracledb"], capture_output=True)
        if r.returncode == 0:
            print("[已有] python-oracledb 已安装，跳过（--force 重装）")
            return True
    print("[下载] python-oracledb → tools/_venv（Oracle thin 模式，免客户端）")
    try:
        subprocess.check_call([os.path.join(bindir, "pip" + EXE),
                               "install", "-q", "--upgrade", "oracledb"])
        return True
    except subprocess.CalledProcessError as e:
        print(f"[失败] oracledb: {e}")
        return False


def provision_patator():
    # 多协议在线爆破，替代 hydra（免编译、免系统依赖）
    return _provision_pip("patator", "patator")


def provision_searchsploit(force=False):
    """下载 searchsploit 脚本 + ExploitDB 索引到 tools/exploitdb/。

    替代 metasploit 的漏洞库检索部分。脚本在自身所在目录查找 files_*.csv
    （见 searchsploit 第 806 行），因此数据必须与脚本同目录存放。
    """
    target_dir = os.path.join(TOOLS_DIR, "exploitdb")
    script = os.path.join(target_dir, "searchsploit")
    if not force and os.path.exists(script) and os.path.exists(
            os.path.join(target_dir, "files_exploits.csv")):
        print("[已有] exploitdb 已打包，跳过（--force 重新下载）")
        return [("exploitdb", "searchsploit")]
    try:
        os.makedirs(target_dir, exist_ok=True)
        print("[下载] exploitdb ← searchsploit 脚本")
        _download(f"{EXPLOITDB_RAW}/searchsploit", script)
        for name in ("files_exploits.csv", "files_shellcodes.csv"):
            print(f"[下载] exploitdb ← {name}")
            _download(f"{EXPLOITDB_RAW}/{name}", os.path.join(target_dir, name))
        if PLAT != "windows":
            os.chmod(script, 0o755)
        rc = os.path.join(target_dir, ".searchsploit_rc")
        with open(rc, "w", encoding="utf-8") as f:
            f.write(SEARCHSPLOIT_RC)
        return [("exploitdb", "searchsploit")]
    except Exception as e:
        print(f"[失败] exploitdb: {e}")
        return None


# jar 类工具：14 个 Java 利用/管理工具的 jar，全部来自天狐工具箱 V4.0 原始发行包。
# 它们是第三方作者的作品，没有任何公开下载源，provision 无法逐个拉取；
# 合计 632 MB，其中 weblogic(130MB) / iwannagetall(180MB) / behinder(126MB)
# 单个就超过 GitHub 单文件 100 MB 的硬限制，因此不能入 git ——
# 统一打包成 Release 资产分发，由本函数下载还原。
JAR_BUNDLE_TAG = "jar-tools-v1"
JAR_BUNDLE_FILE = "zeroxf-jar-tools-v1.tar.gz"
JAR_BUNDLE_URL = ("https://github.com/qwq-nm/zeroxf_tools/releases/download/"
                  f"{JAR_BUNDLE_TAG}/{JAR_BUNDLE_FILE}")

JAR_TOOLS = {
    "shiro":        "shiro/shiro_attack.jar",
    "struts2":      "struts2/struts2_exp.jar",
    "weblogic":     "weblogic/WeblogicTool.jar",
    "thinkphp":     "thinkphp/ThinkphpGUI.jar",
    "nacos":        "nacos/nacos-exploit.jar",
    "jenkins":      "jenkins/JenkinsExploit.jar",
    "xxl-job":      "xxljob/xxl-job-attack.jar",
    "jeecg":        "jeecg/jeecgExploitss.jar",
    "dbcombo":      "dbcombo/DBUtil.jar",
    "iwannagetall": "iwannagetall/IWannaGetAll.jar",
    "hyacinth":     "hyacinth/hyacinth.jar",
    "godzilla":     "godzilla/godzilla.jar",
    "behinder":     "behinder/Behinder.jar",
    "heapdump":     "heapdump/JDumpSpider.jar",
}


def provision_jars(force=False):
    """下载并还原 14 个 jar 类工具。

    返回已就位的工具名列表。整体是一个 584 MB 的 tar.gz，下载走 _download
    （支持断点续传），解包用 tarfile 而非系统 tar —— Windows 上不必依赖
    tar.exe 是否存在，也方便逐条做路径校验。
    """
    def dest_of(rel):
        return os.path.join(TOOLS_DIR, rel.replace("/", os.sep))

    missing = [n for n, rel in JAR_TOOLS.items()
               if force or not os.path.exists(dest_of(rel))]
    if not missing:
        print(f"[已有] jar 类工具 {len(JAR_TOOLS)} 个已就位，跳过"
              f"（--force 重新下载解包）")
        return sorted(JAR_TOOLS)

    print(f"[提示] 需补齐 {len(missing)}/{len(JAR_TOOLS)} 个 jar 类工具: "
          f"{'、'.join(missing)}")

    cache = os.path.join(BASE_DIR, ".buildtools", JAR_BUNDLE_FILE)
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    if not os.path.exists(cache):
        print(f"[下载] {JAR_BUNDLE_FILE}（约 584 MB，大文件，支持断点续传）")
        _download(JAR_BUNDLE_URL, cache)
    else:
        print(f"[缓存] 复用 {cache}")

    print(f"[解压] → {TOOLS_DIR}")
    root = os.path.realpath(BASE_DIR)
    done, n = [], 0
    with tarfile.open(cache, "r:gz") as tf:
        for m in tf.getmembers():
            if not m.isfile():
                continue
            rel = m.name.lstrip("./")
            if not rel.startswith("tools/"):
                continue
            target = os.path.realpath(os.path.join(BASE_DIR, rel))
            # 防目录穿越：包内路径必须落在仓库目录内
            if not target.startswith(root + os.sep):
                print(f"[警告] 跳过可疑路径: {m.name}")
                continue
            if os.path.exists(target) and not force:
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            src = tf.extractfile(m)
            if src is None:
                continue
            with src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            n += 1

    done = [nm for nm, rel in JAR_TOOLS.items() if os.path.exists(dest_of(rel))]
    print(f"[完成] jar 类工具就位 {len(done)}/{len(JAR_TOOLS)}（本次写入 {n} 个文件）")
    still = [nm for nm in JAR_TOOLS if nm not in done]
    if still:
        print(f"[警告] 仍缺失: {'、'.join(still)}")
    return sorted(done)


def update_tools_json(placed_map):
    if not placed_map:
        return
    with open(TOOLS_FILE, "r", encoding="utf-8") as f:
        tools = json.load(f)
    for t in tools:
        name = str(t.get("name", ""))
        if name in placed_map:
            subdir, binary = placed_map[name]
            t["path"] = f"/tools/{subdir}/{binary}" if not binary.startswith("_venv") \
                else f"/tools/{binary}"
            print(f"[更新] {name} → path={t['path']}")
    with open(TOOLS_FILE, "w", encoding="utf-8") as f:
        json.dump(tools, f, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser(description="打包开源工具进 tools/")
    ap.add_argument("--tools", nargs="*", help="只打包指定工具，如 --tools nuclei httpx")
    ap.add_argument("--jdk", action="store_true",
                    help="安装便携 JDK 8/11/17 到 Java_path/")
    ap.add_argument("--gui", action="store_true",
                    help="安装 GUI 依赖 PyQt6 到 tools/_venv（main.py/launcher.py 需要）")
    ap.add_argument("--win-deps", action="store_true",
                    help="Windows 端补装系统级工具：nmap / MySQL 客户端 / Metasploit")
    ap.add_argument("--oracledb", action="store_true",
                    help="装 python-oracledb 到 tools/_venv（Oracle thin 模式，免客户端）")
    ap.add_argument("--jars", action="store_true",
                    help="还原 14 个 jar 类工具（632 MB，从本仓库 Release 下载）")
    ap.add_argument("--force", action="store_true", help="已存在也重新下载")
    args = ap.parse_args()

    os.makedirs(TOOLS_DIR, exist_ok=True)
    if args.jdk:
        provision_jdk(force=args.force)
    if args.gui:
        provision_gui(force=args.force)
    if args.win_deps:
        provision_win_deps(force=args.force)
    if args.oracledb:
        provision_oracledb(force=args.force)
    if args.jars:
        provision_jars(force=args.force)
    # 只开 --jdk/--gui 等开关时不顺带重跑整个 SOURCES 表（否则会重下几十个工具）
    only_flags = (args.jdk or args.gui or args.win_deps or args.oracledb or args.jars)
    names = args.tools
    if names is None and not only_flags:
        names = list(SOURCES.keys())
    names = names or []
    placed_map = {}

    # 非 GitHub-release 模式的工具（pip 安装 / 直链下载 / 多文件组装）
    special = {
        "sqlmap": provision_sqlmap,
        "netexec": provision_netexec,
        "impacket": provision_impacket,
        "patator": provision_patator,
        "mongodb": lambda: provision_mongosh(force=args.force),
        "usql": lambda: provision_usql(force=args.force),
        "jndi": lambda: provision_jndi(force=args.force),
        "zap": lambda: provision_zap(force=args.force),
        "exploitdb": lambda: provision_searchsploit(force=args.force),
        "oracle": lambda: provision_oracle(force=args.force),
        "xray": lambda: provision_xray(force=args.force),
    }
    for name in names:
        if name in special:
            try:
                r = special[name]()
            except Exception as e:
                print(f"[失败] {name}: {type(e).__name__}: {e}")
                continue
            if r:
                placed_map[name] = r[0]
            continue
        if name not in SOURCES:
            print(f"[跳过] 未知工具: {name}")
            continue
        spec = SOURCES[name]
        if not args.force and _already_present(spec, name):
            print(f"[已有] {name} 已打包，跳过（--force 重新下载）")
            continue
        try:
            r = provision_github(name, spec)
        except Exception as e:
            # 单个工具失败不应中断整批安装：网络中断、解压格式不支持
            # （如 hashcat 的 7z 用了 py7zr 不认的 BCJ2 过滤器）都可能发生
            print(f"[失败] {name}: {type(e).__name__}: {e}")
            continue
        if not r:
            continue
        if spec.get("binaries"):
            for sub, b in r:
                placed_map[b] = (sub, b)   # frps → frp/frps, frpc → frp/frpc
        else:
            placed_map[name] = r[0] if isinstance(r, list) else (spec["subdir"], name)

    update_tools_json(placed_map)

    # 全量安装（无参数直接跑）时一并还原 jar 包；用 --tools/--jars 挑了具体目标
    # 就不顺带拉这 584 MB，避免「只想装个 nuclei」却等半小时。
    if not only_flags and args.tools is None:
        try:
            provision_jars(force=args.force)
        except Exception as e:
            print(f"[失败] jars: {type(e).__name__}: {e}")
            print("        jar 类工具可从 Release 手动下载后解包覆盖到仓库根目录")

    print(f"[完成] 打包完成，当前平台: {PLAT}")


def _already_present(spec, name):
    if spec.get("binaries"):
        return all(os.path.exists(os.path.join(TOOLS_DIR, spec["subdir"], b + EXE))
                   for b in spec["binaries"])
    # keep_dir 模式（如 hashcat）落盘的是 keep_binary（hashcat.bin），不是 binary，
    # 否则每次都会被判定为"不存在"而重下 100MB+ 的包
    b = spec.get("keep_binary", spec["binary"]) + EXE
    return os.path.exists(os.path.join(TOOLS_DIR, spec["subdir"], b))


if __name__ == "__main__":
    main()
