#!/usr/bin/env python3
"""docem 交互式引导启动器"""

import subprocess
import sys
import os
import glob

DIR = os.path.dirname(os.path.abspath(__file__))
# 二开：改用项目共享 venv 的解释器（tools/_venv/bin/python）
_SHARED = os.path.join(os.path.dirname(DIR), "_venv", "bin", "python")
PYTHON = _SHARED if os.path.exists(_SHARED) else os.path.join(DIR, "venv/bin/python")
DOCEM = os.path.join(DIR, "docem.py")

def pick(prompt, options, allow_custom=False):
    print(f"\n  {prompt}")
    for i, opt in enumerate(options, 1):
        print(f"    {i}) {opt}")
    if allow_custom:
        print(f"    0) 自定义输入")
    while True:
        choice = input("  >> ").strip()
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(options):
                return options[idx - 1]
            if idx == 0 and allow_custom:
                return input("  输入值: ").strip()
        print("  无效选择，请重试")

def main():
    if len(sys.argv) > 1:
        return subprocess.run([PYTHON, DOCEM] + sys.argv[1:], cwd=DIR).returncode

    print("\n  ╔══════════════════════════════════════╗")
    print("  ║   docem - XXE/XSS Payload 注入工具   ║")
    print("  ╚══════════════════════════════════════╝")

    # 选择 payload 类型
    pt = pick("选择 Payload 类型:", ["xxe - XXE注入", "xss - XSS注入"])
    pt = pt.split(" ")[0]

    # 选择注入模式
    pm = pick("选择注入模式:", [
        "per_place - 每个注入点一个文件",
        "per_file - 每个文件一个payload",
        "per_document - 每个文档一个payload",
    ])
    pm = pm.split(" ")[0]

    # 选择样本
    samples_dir = os.path.join(DIR, "samples", "marked")
    samples = []
    if os.path.isdir(samples_dir):
        for ext in ("*.docx", "*.xlsx", "*.pptx", "*.odt", "*"):
            for f in sorted(glob.glob(os.path.join(samples_dir, ext))):
                if os.path.isfile(f):
                    samples.append(f)
            if samples:
                break

    if samples:
        sample_names = [os.path.relpath(s, DIR) for s in samples]
        sample = pick("选择样本文件:", sample_names, allow_custom=True)
    else:
        print("\n  未找到内置样本，请输入样本路径:")
        sample = input("  >> ").strip()

    sample_path = sample if os.path.isabs(sample) else os.path.join(DIR, sample)
    if not os.path.exists(sample_path):
        print(f"\n  错误: 文件不存在 {sample_path}")
        input("  按回车退出...")
        return

    # 选择 payload 文件
    payloads_dir = os.path.join(DIR, "payloads")
    payloads = sorted(glob.glob(os.path.join(payloads_dir, f"*{pt}*")))
    if not payloads:
        payloads = sorted(glob.glob(os.path.join(payloads_dir, "*")))

    if payloads:
        payload_names = [os.path.relpath(p, DIR) for p in payloads]
        pf = pick("选择 Payload 文件:", payload_names, allow_custom=True)
    else:
        print("\n  请输入 payload 文件路径:")
        pf = input("  >> ").strip()

    # 选择输出扩展名
    ext_map = {".docx": "docx", ".xlsx": "xlsx", ".pptx": "pptx", ".odt": "odt"}
    _, s_ext = os.path.splitext(sample_path)
    default_ext = ext_map.get(s_ext.lower(), "docx")
    sx = pick(f"输出格式 (默认: {default_ext}):", [
        "docx", "xlsx", "pptx", "odt",
    ], allow_custom=True)
    if not sx:
        sx = default_ext

    # 构造命令
    cmd = [PYTHON, DOCEM,
           "-s", sample_path,
           "-pt", pt,
           "-pf", pf if os.path.isabs(pf) else os.path.join(DIR, pf),
           "-pm", pm,
           "-sx", sx]

    print(f"\n  执行命令:")
    print(f"  {' '.join(cmd)}\n")
    print("  " + "─" * 44)

    subprocess.run(cmd, cwd=DIR)

    print("\n  " + "─" * 44)
    input("  按回车退出...")

if __name__ == "__main__":
    sys.exit(main() or 0)
