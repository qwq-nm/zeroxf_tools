import base64
import os
import signal
import socket
import subprocess


def is_valid_port(value):
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError):
        return False
    return 1 <= port <= 65535


def normalize_port(value, default):
    value = str(value).strip()
    if not value:
        return default
    return value if is_valid_port(value) else None


def encode_command(raw, encode):
    if encode == "Base64":
        encoded = base64.b64encode(raw.encode()).decode()
        return f"echo {encoded} | base64 -d | sh"
    return raw


def terminate_process(proc):
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass


def detect_ip():
    import re

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            candidate = s.getsockname()[0]
        if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", candidate) and candidate != "127.0.0.1":
            return candidate
    except Exception:
        pass

    for iface in ("en0", "en1", "bridge100"):
        try:
            r = subprocess.run(["ipconfig", "getifaddr", iface],
                               capture_output=True, text=True, timeout=1)
            candidate = r.stdout.strip()
            if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", candidate):
                return candidate
        except Exception:
            pass
    return None
