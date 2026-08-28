#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并用户自带的原版天狐 tools.json 到当前工具清单。

规则：
- 按 name+category 去重
- 现有条目（含扩展字段 risk/ai_callable/aliases）优先保留
- --drop 名单里的工具直接剔除（踢掉不好用的）
- 可覆盖同名条目的字段：--override 时用导入条目覆盖现有

用法：
  python3 scripts/merge_tools.py --import <原版tools.json> [--drop 名称1 名称2 ...] [--override]
"""
import argparse
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_FILE = os.path.join(BASE_DIR, "config", "tools.json")

EXTRA_FIELDS = ("risk", "ai_callable", "aliases", "example", "dependencies", "args_mode")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        for key in ("tools", "data", "items"):
            if isinstance(raw.get(key), list):
                return raw[key]
    return raw


def main():
    ap = argparse.ArgumentParser(description="合并原版天狐 tools.json")
    ap.add_argument("--import", dest="import_file", required=True, help="原版 tools.json 路径")
    ap.add_argument("--drop", nargs="*", default=[], help="要剔除的工具名")
    ap.add_argument("--override", action="store_true", help="同名工具用导入条目覆盖")
    ap.add_argument("--tools-file", default=TOOLS_FILE, help="当前工具清单路径")
    args = ap.parse_args()

    incoming = load_json(args.import_file)
    drop_set = set(args.drop)

    with open(args.tools_file, "r", encoding="utf-8") as f:
        current = json.load(f)

    key = lambda t: (str(t.get("name", "")).strip(), str(t.get("category", "")).strip())
    cur_map = {key(t): t for t in current if key(t)[0]}

    added, updated, dropped = 0, 0, 0
    for t in incoming:
        if not isinstance(t, dict) or not t.get("name"):
            continue
        if str(t.get("name", "")).strip() in drop_set:
            dropped += 1
            continue
        k = key(t)
        if k in cur_map:
            if args.override:
                merged = {**t}
                for fld in EXTRA_FIELDS:
                    if fld not in merged and fld in cur_map[k]:
                        merged[fld] = cur_map[k][fld]
                cur_map[k] = merged
                updated += 1
        else:
            cur_map[k] = t
            added += 1

    merged = list(cur_map.values())
    with open(args.tools_file, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"[完成] 新增 {added}，覆盖 {updated}，剔除 {dropped}，当前共 {len(merged)} 个工具")


if __name__ == "__main__":
    main()
