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
        return os.path.abspath(p)
    return p


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
        cmd = [_resolve_python(t)] + pre + [script] + post + args
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
        cmd = [exe] + pre + post + args
        return {"kind": "cmd", "cmd": cmd, "cwd": cwd, "env": _inject_env(t)}

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
    return {"kind": "cmd", "cmd": [exe] + pre + post + args, "cwd": cwd, "env": _inject_env(t)}


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
