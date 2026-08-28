#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工具打包脚本：把开源工具二进制下载进 tools/，让 geshell 开箱即用。

按当前平台（Linux/Windows/macOS）从官方 GitHub release 拉取二进制，
解压到 tools/<子目录>/<可执行文件>，并自动更新 config/tools.json 的 path。

用法：
  python3 scripts/provision_tools.py [--tools 名称1 名称2 ...] [--force]

说明：
- 只打包本表内能免费拉取的开源工具；xray（需授权）、CobaltStrike/Burp（商业）、
  枷锁专属脚本（spring/tomcat/redis/heapdump 等）不在表内，保持原样，doctor 会提示。
- 同一脚本在 Windows 上重跑一次即可拉取 .exe 版本。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
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


def _gh_api(url):
    req = urllib.request.Request(url, headers={"User-Agent": "provision_tools"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _latest_assets(repo):
    d = _gh_api(f"https://api.github.com/repos/{repo}/releases/latest")
    return [a["name"] for a in d.get("assets", [])]


def _download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "provision_tools"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


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
        # 7z 解压：优先用自带 7-Zip 二进制（支持 BCJ2），否则 py7zr
        seven_zip = os.path.join(BASE_DIR, ".buildtools",
                                 "7zz" if os.name != "nt" else "7z.exe")
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
    try:
        print(f"[下载] {name} ← {asset}")
        _download(url, archive)
        subdir = os.path.join(TOOLS_DIR, spec["subdir"])
        tmp_out = os.path.join(TOOLS_DIR, f".tmp_out_{spec['subdir']}")
        shutil.rmtree(tmp_out, ignore_errors=True)
        _extract(archive, tmp_out, spec["extract"])

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
        elif spec["extract"] in ("gz", "raw"):
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


def provision_netexec():
    return _provision_pip("nxc", "nxc")


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
    ap.add_argument("--force", action="store_true", help="已存在也重新下载")
    args = ap.parse_args()

    os.makedirs(TOOLS_DIR, exist_ok=True)
    names = args.tools or list(SOURCES.keys())
    placed_map = {}

    for name in names:
        if name in ("sqlmap", "netexec"):
            r = provision_sqlmap() if name == "sqlmap" else provision_netexec()
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
        r = provision_github(name, spec)
        if not r:
            continue
        if spec.get("binaries"):
            for sub, b in r:
                placed_map[b] = (sub, b)   # frps → frp/frps, frpc → frp/frpc
        else:
            placed_map[name] = r[0] if isinstance(r, list) else (spec["subdir"], name)

    update_tools_json(placed_map)
    print(f"[完成] 打包完成，当前平台: {PLAT}")


def _already_present(spec, name):
    if spec.get("binaries"):
        return all(os.path.exists(os.path.join(TOOLS_DIR, spec["subdir"], b + EXE))
                   for b in spec["binaries"])
    b = spec["binary"] + EXE
    return os.path.exists(os.path.join(TOOLS_DIR, spec["subdir"], b))


if __name__ == "__main__":
    main()
