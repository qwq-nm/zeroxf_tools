# -*- coding: utf-8 -*-
"""跨平台命令构建与执行（argv 列表，无 shell，无 cmd /c start）。

从天狐 run_tool 的 Windows GUI 启动器语义改造成：
- argv 列表 + subprocess，可捕获输出（CLI 实时流式、MCP 捕获模式）
- 支持类型：Python / JAVA8 / JAVA11 / Java(<名>) / 命令行 / 批处理 / PowerShell / GUI应用 / 网页
- 环境注入复用天狐 EnvManager（纯 Python，无 PyQt6）
- cwd = 工具所在目录或 working_dir
"""
import os
import shutil
import subprocess
import sys
import webbrowser
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

_env_mgr = None


def _get_env_mgr():
    global _env_mgr
    if _env_mgr is None:
        try:
            from core.env_manager import EnvManager
            _env_mgr = EnvManager()
        except Exception:
            _env_mgr = None
    return _env_mgr


def _split(args_str: str) -> List[str]:
    return [a for a in (args_str or "").split() if a]


def _all_params(tool: Dict[str, Any]) -> List[str]:
    return _split(tool.get("params_pre", "")) + _split(tool.get("params", ""))


def _resolve_path(tool: Dict[str, Any], path: str) -> str:
    """返回绝对路径；若是裸命令名（如 nmap）则原样返回交给 PATH。"""
    if not path:
        return ""
    p = str(path)
    has_sep = ("/" in p) or ("\\" in p)
    is_abs = os.path.isabs(p) or (len(p) > 1 and p[1] == ":")
    if has_sep or is_abs:
        ap = os.path.abspath(p)
        # config/tools.json 是两端共用的一份配置，其中 path 按 Linux 命名书写
        # （如 /tools/yasso/Yasso），而 Windows 上的实际文件带 .exe 后缀。
        # 这里在 Windows 下做一次后缀补全，让同一份配置在两端都能用，
        # 否则 Windows 端会满屏“入口不存在”。
        if os.name == "nt" and not os.path.exists(ap):
            # (a) 工具自身带 .exe 后缀（tools.json 里按 Linux 习惯没写后缀）
            for ext in (".exe", ".bat", ".cmd"):
                if os.path.exists(ap + ext):
                    return ap + ext
            # (b) Python venv 的目录布局两平台不同：Linux 是 bin/，Windows 是 Scripts/
            #     （netexec 的 nxc、impacket 的 secretsdump.py 都属于这种）
            alt = ap.replace("\\bin\\", "\\Scripts\\").replace("/bin/", "/Scripts/")
            if alt != ap:
                if os.path.exists(alt):
                    return alt
                for ext in (".exe", ".py", ".bat", ".cmd"):
                    if os.path.exists(alt + ext):
                        return alt + ext
            # (c) 同一个工具的启动方式两端命名不同：Linux 是 .sh（如 ZAP 的
            #     zap-tianhu.sh），Windows 侧是配套的 .bat/.cmd。
            #     _win_exec_argv 执行时已经会做这个映射，但那条路径不影响
            #     存在性判断——少了这一步，doctor 会把能用的工具报成“路径不存在”。
            if ap.lower().endswith(".sh"):
                base = ap[:-3]
                for cand in (base + ".bat", base + ".cmd", base + ".exe"):
                    if os.path.exists(cand):
                        return cand
        return ap
    return p


def _win_exec_argv(exe: str) -> List[str]:
    """Windows 下把「不能直接执行」的入口包装成可执行的 argv 前缀。

    tools.json 是两端共用的一份配置，里面有两类入口在 Windows 上跑不起来：

    - .sh  —— Windows 无法执行 shell 脚本。oracle 的 sqlplus 就是这种：
             provision 在两端都生成了 sqlplus.sh，但 Windows 上真正能用的是
             随 Instant Client 附带的 sqlplus.exe（需先设好依赖库路径），
             故这里改找同目录的 .bat 包装。
    - .py  —— 类 Unix 靠 shebang 直接执行，Windows 不会，必须显式交给解释器。
             impacket 的 secretsdump.py 属于这类，用工具箱自带的 venv Python 跑。

    非 Windows 或非绝对路径（裸命令）时原样返回。
    """
    if os.name != "nt" or not os.path.isabs(exe):
        return [exe]
    low = exe.lower()
    if low.endswith(".sh"):
        base = exe[:-3]
        for cand in (base + ".bat", base + ".cmd"):
            if os.path.exists(cand):
                return [cand]
        return [exe]
    if low.endswith(".py"):
        return [_resolve_python("Python"), exe]
    return [exe]


def _resolve_python(tool_type: str) -> str:
    # 优先项目共享 venv（tools/_venv，已装好工具依赖）
    venv_py = os.path.join(BASE_DIR, "tools", "_venv",
                           "Scripts" if os.name == "nt" else "bin",
                           "python" + (".exe" if os.name == "nt" else ""))
    if os.path.isfile(venv_py):
        return venv_py
    try:
        m = _get_env_mgr()
        if m is not None:
            p = m.get_python_path()
            if p and p != "python":
                return p
    except Exception:
        pass
    return sys.executable


def _resolve_java(tool_type: str, gui: bool) -> str:
    ver = "11" if "11" in tool_type else "8"
    try:
        m = _get_env_mgr()
        if m is not None:
            exe = m.get_java_exe(ver, gui=gui)
            if exe and exe not in ("java", "javaw"):
                return exe
    except Exception:
        pass
    j = shutil.which("javaw" if gui else "java")
    if j:
        return j
    return "javaw" if gui else "java"


def _inject_env(tool_type: str) -> Dict[str, str]:
    try:
        m = _get_env_mgr()
        if m is not None:
            return m.get_injected_env(tool_type)
    except Exception:
        pass
    return os.environ.copy()


def build_command(tool: Dict[str, Any], user_args: List[str]) -> Dict[str, Any]:
    """把工具定义解析成可执行结构。

    返回 dict：{"kind": "cmd"|"gui"|"web", "cmd": [...], "cwd": ..., "env": {...}, "err": 可选}
    """
    t = str(tool.get("type", "") or "").strip()
    path = str(tool.get("path", "") or "").strip()
    url = str(tool.get("url", "") or "").strip()
    pre = _split(tool.get("params_pre", ""))
    post = _split(tool.get("params", ""))
    args = list(user_args)

    cwd = None
    wd = str(tool.get("working_dir", "") or "").strip()
    if wd:
        cwd = os.path.join(BASE_DIR, wd) if not os.path.isabs(wd) else wd

    # 网页工具
    if t in ("网页", "web") or (not t and url):
        return {"kind": "web", "url": url or path}

    # GUI 应用
    if t in ("GUI应用", "GUI", "app"):
        return {"kind": "gui", "target": path}

    # Python 脚本
    if t == "Python" or t.startswith("Python("):
        script = _resolve_path(tool, path)
        if not script or script in ("",):
            return {"kind": "cmd", "cmd": ["true"], "cwd": cwd, "env": os.environ.copy(),
                    "err": f"path 为空（{tool.get('name')} Python 工具缺入口）"}
        if not os.path.isfile(script):
            exe = shutil.which(script)
            if exe:
                script = exe
        # params_pre 放在**脚本之后**，与「命令行」「批处理」两个分支的语义
        # 保持一致：它是这个工具的默认参数。原先放在解释器与脚本之间，于是
        # `python --mode xxx script.py` 把参数喂给了 python 而不是脚本——
        # params_pre 对 Python 类工具等于失效。（Java 分支的 pre 确实是 JVM
        # 参数，那一处语义不同是有意的，不动。）
        cmd = [_resolve_python(t)] + [script] + pre + post + args
        return {"kind": "cmd", "cmd": cmd,
                "cwd": cwd or os.path.dirname(os.path.abspath(script)),
                "env": _inject_env(t)}

    # Java（jar）
    if t.startswith("JAVA") or t.startswith("Java("):
        jar = _resolve_path(tool, path)
        if not jar:
            return {"kind": "cmd", "cmd": ["true"], "cwd": cwd, "env": os.environ.copy(),
                    "err": f"path 为空（{tool.get('name')} Java 工具缺 jar 路径）"}
        gui = "图形化" in t
        cmd = [_resolve_java(t, gui)] + pre + ["-jar", jar] + post + args
        return {"kind": "cmd", "cmd": cmd,
                "cwd": cwd or os.path.dirname(os.path.abspath(jar)),
                "env": _inject_env(t)}

    # 命令行
    if t in ("命令行", "cli"):
        exe = _resolve_path(tool, path) or str(tool.get("name", ""))
        cmd = _win_exec_argv(exe) + pre + post + args
        # 绝对路径的可执行文件以其所在目录为 cwd：有些工具（如 xray）会把配置文件
        # 生成在当前 cwd，沿用调用者目录就会四处污染。裸命令（nmap 等）保持 None。
        return {"kind": "cmd", "cmd": cmd,
                "cwd": cwd or (os.path.dirname(exe) if os.path.isabs(exe) else None),
                "env": _inject_env(t)}

    # 批处理
    if t in ("批处理", "batch"):
        script = _resolve_path(tool, path)
        if os.name == "nt":
            cmd = ["cmd", "/c", script] + pre + post + args
        else:
            cmd = ["bash", script] + pre + post + args
        return {"kind": "cmd", "cmd": cmd,
                "cwd": cwd or (os.path.dirname(os.path.abspath(script)) if script else None),
                "env": _inject_env(t)}

    # PowerShell
    if t in ("PowerShell", "powershell", "ps1"):
        script = _resolve_path(tool, path)
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if not shell:
            return {"kind": "cmd", "cmd": ["true"], "cwd": cwd, "env": os.environ.copy(),
                    "err": "未找到 powershell/pwsh"}
        cmd = [shell, "-NoExit", "-File", script] + pre + post + args
        return {"kind": "cmd", "cmd": cmd,
                "cwd": cwd or (os.path.dirname(os.path.abspath(script)) if script else None),
                "env": _inject_env(t)}

    # 兜底：当作系统命令
    exe = _resolve_path(tool, path) or str(tool.get("name", ""))
    return {"kind": "cmd", "cmd": [exe] + pre + post + args,
            "cwd": cwd or (os.path.dirname(exe) if os.path.isabs(exe) else None),
            "env": _inject_env(t)}


def launch_gui(tool: Dict[str, Any]) -> int:
    target = str(tool.get("path", "") or "")
    if not target:
        return 1
    if os.name == "nt":
        os.startfile(target)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", target])
    else:
        subprocess.Popen(["xdg-open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


def open_web(url: str) -> int:
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    webbrowser.open(url)
    return 0


def execute(cmd: List[str], cwd: Optional[str], env: Dict[str, str],
            capture: bool = False, timeout: Optional[int] = None
            ) -> Tuple[int, str, str]:
    """执行 argv 命令。

    capture=True（MCP 用）：捕获全部输出返回。
    capture=False（CLI 用）：实时流式转发到终端并落盘（调用方负责写文件）。
    """
    if capture:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr

    p = subprocess.Popen(cmd, cwd=cwd, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    out_chunks: List[str] = []
    err_chunks: List[str] = []

    def _pump(pipe, sink, target, name):
        try:
            for line in iter(pipe.readline, ""):
                sink.append(line)
                target.write(line)
                target.flush()
        except Exception:
            pass
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    import threading
    t1 = threading.Thread(target=_pump, args=(p.stdout, out_chunks, sys.stdout, "out"), daemon=True)
    t2 = threading.Thread(target=_pump, args=(p.stderr, err_chunks, sys.stderr, "err"), daemon=True)
    t1.start()
    t2.start()
    rc = p.wait()
    t1.join(timeout=5)
    t2.join(timeout=5)
    return rc, "".join(out_chunks), "".join(err_chunks)
