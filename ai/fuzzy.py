# -*- coding: utf-8 -*-
"""名称模糊匹配：从天狐 utils.py 抽出的纯函数（无 PyQt6 依赖）。

支持：
- 忽略大小写 / 空格 / 横线 / 下划线（枷锁 geshell 的容错目标）
- 中文全拼 / 首字母匹配（xpinyin），缺失时降级为纯子串匹配
"""
import os
import sys
from functools import lru_cache
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from xpinyin import Pinyin
except Exception:
    Pinyin = None

_PINYIN_ENGINE = None


def _get_pinyin_engine():
    global _PINYIN_ENGINE
    if _PINYIN_ENGINE is not None:
        return _PINYIN_ENGINE
    if Pinyin is None:
        return None
    try:
        _PINYIN_ENGINE = Pinyin()
    except Exception:
        _PINYIN_ENGINE = None
    return _PINYIN_ENGINE


def normalize_name(name) -> str:
    """枷锁风格归一化：小写 + 去掉所有空格/横线/下划线。"""
    try:
        s = str(name).lower().strip()
    except Exception:
        s = ""
    return s.replace(" ", "").replace("-", "").replace("_", "")


def _normalize_search_token(text: str) -> str:
    try:
        s = str(text).casefold().strip()
    except Exception:
        s = ""
    return "".join([ch for ch in s if not ch.isspace() and ch not in "-_/\\."])


@lru_cache(maxsize=4096)
def _build_search_aliases(text: str) -> tuple:
    try:
        raw = str(text or "")
    except Exception:
        raw = ""
    raw_cf = raw.casefold()
    compact = _normalize_search_token(raw)
    aliases = {raw_cf, compact}

    eng = _get_pinyin_engine()
    if eng is not None and any("一" <= ch <= "鿿" for ch in raw):
        try:
            full_py = str(eng.get_pinyin(raw, "")).casefold()
            full_py = _normalize_search_token(full_py)
            if full_py:
                aliases.add(full_py)
        except Exception:
            pass
        try:
            initials = str(eng.get_initials(raw, "")).casefold()
            initials = _normalize_search_token(initials)
            if initials:
                aliases.add(initials)
        except Exception:
            pass

    return tuple(v for v in aliases if v)


@lru_cache(maxsize=4096)
def name_sort_key(text):
    try:
        raw = str(text or "").casefold()
    except Exception:
        raw = ""
    if any("一" <= ch <= "鿿" for ch in raw):
        eng = _get_pinyin_engine()
        if eng is not None:
            try:
                py = str(eng.get_pinyin(raw, "")).casefold()
                if py:
                    return py
            except Exception:
                pass
    return raw


def fuzzy_search(tools: List[Dict[str, Any]], search_text: str) -> List[Dict[str, Any]]:
    """在天狐 utils.fuzzy_search 基础上，去掉 PyQt6 与 tags 依赖。"""
    if not search_text:
        return tools
    try:
        st = str(search_text).casefold()
    except Exception:
        st = ""
    st_compact = _normalize_search_token(st)
    ret = []
    for t in tools:
        try:
            nm = str(t.get("name", "")).casefold()
            desc = str(t.get("description", "")).casefold()
            cat = str(t.get("category", "")).casefold()
            path = str(t.get("path", "")).casefold()
            url = str(t.get("url", "")).casefold()
            params = str(t.get("params", "")).casefold()
        except Exception:
            nm = desc = cat = path = url = params = ""
        if (st in nm) or (st in desc) or (st in cat) or (st in path) or (st in url) or (st in params):
            ret.append(t)
            continue
        if not st_compact:
            continue
        alias_fields = [
            str(t.get("name", "")),
            str(t.get("category", "")),
            str(t.get("description", "")),
            str(t.get("path", "")),
            str(t.get("url", "")),
            str(t.get("params", "")),
        ]
        matched = False
        for field in alias_fields:
            for alias in _build_search_aliases(field):
                if st_compact in alias:
                    matched = True
                    break
            if matched:
                break
        if matched:
            ret.append(t)
    return ret


def find_tool(tools: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    """先按 name+aliases 归一化精确匹配，再退回拼音/子串模糊匹配。"""
    if not name:
        return None
    want = normalize_name(name)
    for t in tools:
        cands = [str(t.get("name", ""))]
        for a in (t.get("aliases") or []):
            cands.append(str(a))
        if any(normalize_name(c) == want for c in cands):
            return t
    hits = fuzzy_search(tools, name)
    if len(hits) == 1:
        return hits[0]
    return None
