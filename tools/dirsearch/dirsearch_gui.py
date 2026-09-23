#!/usr/bin/env python3
"""Dirsearch GUI - 枷锁工具箱"""

from __future__ import annotations

import csv
import json
import os
import queue
import signal
import sys
import threading
from dataclasses import asdict, dataclass
from tkinter import filedialog
from tkinter import ttk

import customtkinter as ctk

DIRSEARCH_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_WORDLIST = os.path.join(DIRSEARCH_DIR, "db", "dicc.txt")

if DIRSEARCH_DIR not in sys.path:
    sys.path.insert(0, DIRSEARCH_DIR)

BG = "#0b0d10"
PANEL = "#11151a"
CARD = "#151a20"
INPUT = "#0f1318"
BORDER = "#27313b"
RED = "#e63946"
RED_DARK = "#5c1820"
GREEN = "#22c55e"
YELLOW = "#f59e0b"
CYAN = "#38bdf8"
TEXT = "#d7dee8"
TEXT_MUTED = "#8b98a8"
TEXT_DIM = "#596473"


def _font(size: int, bold: bool = False):
    return ("PingFang SC", size, "bold" if bold else "normal")


FONT_TITLE = _font(18, True)
FONT_HEAD = _font(13, True)
FONT_BODY = _font(12)
FONT_SMALL = _font(11)
FONT_MONO = ("Menlo", 11)
FONT_MONO_HEAD = ("Menlo", 11, "bold")


@dataclass
class ScanResult:
    path: str
    status: int
    size: str
    content_type: str
    redirect: str
    url: str
    elapsed: float


class GUIInterface:
    """Small adapter used by dirsearch internals instead of terminal output."""

    def __init__(self, result_q: queue.Queue):
        self._q = result_q
        self.last_in_line = False
        self.buffer = ""

    def status_report(self, response, full_url):
        path = response.full_path if hasattr(response, "full_path") else response.path
        self._q.put({
            "type": "result",
            "data": ScanResult(
                path=path,
                status=response.status,
                size=str(response.length or 0),
                content_type=response.type or "",
                redirect=response.redirect or "",
                url=response.url or full_url or "",
                elapsed=response.elapsed,
            ),
        })

    def last_path(self, index, length, *args, **kwargs):
        self._q.put({"type": "progress", "data": {"index": index, "length": length}})

    def error(self, reason):
        self._q.put({"type": "status", "data": {"message": str(reason), "level": "error"}})

    def warning(self, message, do_save=True):
        self._q.put({"type": "status", "data": {"message": str(message), "level": "warning"}})

    def new_directories(self, directories): pass
    def header(self, message): pass
    def config(self, wordlist_size): pass
    def target(self, target): pass
    def log_file(self, file): pass
    def print_header(self, headers): pass
    def in_line(self, string): pass
    def new_line(self, string="", do_save=True): pass

    @staticmethod
    def erase(): pass


class DirsearchGUI:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        self.root = ctk.CTk()
        self.root.title("dirsearch - 枷锁工具箱")
        self.root.geometry("1080x680")
        self.root.minsize(920, 560)
        self.root.configure(fg_color=BG)

        self.results: list[ScanResult] = []
        self.result_queue: queue.Queue = queue.Queue()
        self.scan_thread: threading.Thread | None = None
        self.is_scanning = False
        self._controller = None

        self._build_ui()
        self._poll_queue()

    def run(self):
        self.root.mainloop()

    def _build_ui(self):
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self._build_header()
        self._build_main()
        self._build_footer()

    def _build_header(self):
        header = ctk.CTkFrame(self.root, height=56, corner_radius=0, fg_color=PANEL)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=0, padx=18, pady=8, sticky="w")
        ctk.CTkLabel(title_box, text="dirsearch", font=FONT_TITLE, text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(
            title_box,
            text=f"默认字典: {os.path.relpath(DEFAULT_WORDLIST, DIRSEARCH_DIR)}",
            font=FONT_SMALL,
            text_color=TEXT_MUTED,
        ).pack(anchor="w")

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, padx=14, pady=10, sticky="e")
        for text, command in (
            ("TXT", self._export_txt),
            ("CSV", self._export_csv),
            ("JSON", self._export_json),
        ):
            ctk.CTkButton(
                actions,
                text=text,
                width=58,
                height=30,
                font=FONT_SMALL,
                fg_color=CARD,
                hover_color=RED_DARK,
                text_color=TEXT,
                corner_radius=6,
                command=command,
            ).pack(side="right", padx=(6, 0))

    def _build_main(self):
        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=12, pady=10)
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)

        form = ctk.CTkScrollableFrame(main, width=318, fg_color=PANEL, corner_radius=8)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self._build_form(form)

        results = ctk.CTkFrame(main, fg_color=PANEL, corner_radius=8)
        results.grid(row=0, column=1, sticky="nsew")
        results.grid_rowconfigure(1, weight=1)
        results.grid_columnconfigure(0, weight=1)
        self._build_result_panel(results)

    def _label(self, parent, text):
        return ctk.CTkLabel(parent, text=text, anchor="w", font=FONT_SMALL, text_color=TEXT_MUTED)

    def _entry(self, parent, placeholder="", height=32):
        return ctk.CTkEntry(
            parent,
            height=height,
            placeholder_text=placeholder,
            font=FONT_BODY,
            fg_color=INPUT,
            border_color=BORDER,
            border_width=1,
            corner_radius=6,
            text_color=TEXT,
        )

    def _section(self, parent, title):
        ctk.CTkLabel(parent, text=title, anchor="w", font=FONT_HEAD, text_color=TEXT).pack(
            fill="x", pady=(12, 6)
        )

    def _build_form(self, parent):
        self._section(parent, "目标")

        self._label(parent, "URL").pack(fill="x", pady=(0, 3))
        self.url_entry = self._entry(parent, "https://example.com/")
        self.url_entry.pack(fill="x")

        self._label(parent, "扩展名").pack(fill="x", pady=(10, 3))
        self.ext_entry = self._entry(parent, "php,html,js,txt,bak")
        self.ext_entry.insert(0, "php,html,js,txt,bak")
        self.ext_entry.pack(fill="x")

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(10, 0))
        row.grid_columnconfigure((0, 1), weight=1, uniform="opts")

        ctk.CTkLabel(row, text="线程", anchor="w", font=FONT_SMALL, text_color=TEXT_MUTED).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ctk.CTkLabel(row, text="超时", anchor="w", font=FONT_SMALL, text_color=TEXT_MUTED).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )
        self.threads_entry = self._entry(row, "25")
        self.threads_entry.insert(0, "25")
        self.threads_entry.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        self.timeout_entry = self._entry(row, "7.5")
        self.timeout_entry.insert(0, "7.5")
        self.timeout_entry.grid(row=1, column=1, sticky="ew", padx=(6, 0))

        toggles = ctk.CTkFrame(parent, fg_color="transparent")
        toggles.pack(fill="x", pady=(12, 2))
        self.recursive_var = ctk.BooleanVar(value=False)
        self.redirect_var = ctk.BooleanVar(value=False)
        for text, var in (("递归", self.recursive_var), ("跟随跳转", self.redirect_var)):
            ctk.CTkCheckBox(
                toggles,
                text=text,
                variable=var,
                font=FONT_SMALL,
                text_color=TEXT,
                checkbox_width=18,
                checkbox_height=18,
                border_color=BORDER,
                fg_color=RED,
                hover_color=RED_DARK,
                corner_radius=4,
            ).pack(side="left", padx=(0, 18))

        self._section(parent, "过滤")
        self._label(parent, "包含状态码").pack(fill="x", pady=(0, 3))
        self.include_status_entry = self._entry(parent, "200-299,301,302,401,403")
        self.include_status_entry.insert(0, "200-299,301,302,401,403")
        self.include_status_entry.pack(fill="x")

        self._label(parent, "排除状态码").pack(fill="x", pady=(10, 3))
        self.exclude_status_entry = self._entry(parent, "404,429")
        self.exclude_status_entry.pack(fill="x")

        self._label(parent, "排除响应大小").pack(fill="x", pady=(10, 3))
        self.exclude_size_entry = self._entry(parent, "1B,243KB")
        self.exclude_size_entry.pack(fill="x")

        self._section(parent, "请求")
        self._label(parent, "HTTP 方法").pack(fill="x", pady=(0, 3))
        self.method_var = ctk.StringVar(value="GET")
        ctk.CTkSegmentedButton(
            parent,
            values=["GET", "POST", "HEAD"],
            variable=self.method_var,
            height=30,
            font=FONT_SMALL,
            fg_color=INPUT,
            selected_color=RED_DARK,
            selected_hover_color=RED,
            unselected_color=INPUT,
            unselected_hover_color=BORDER,
            corner_radius=6,
        ).pack(fill="x")

        self._label(parent, "Header").pack(fill="x", pady=(10, 3))
        self.headers_box = ctk.CTkTextbox(
            parent,
            height=74,
            font=FONT_MONO,
            fg_color=INPUT,
            border_color=BORDER,
            border_width=1,
            corner_radius=6,
            text_color=TEXT,
        )
        self.headers_box.pack(fill="x")

        self._label(parent, "Cookie").pack(fill="x", pady=(10, 3))
        self.cookie_entry = self._entry(parent, "SESSIONID=...")
        self.cookie_entry.pack(fill="x")

        self._label(parent, "User-Agent").pack(fill="x", pady=(10, 3))
        self.ua_entry = self._entry(parent, "默认")
        self.ua_entry.pack(fill="x")

        self._label(parent, "代理").pack(fill="x", pady=(10, 3))
        self.proxy_entry = self._entry(parent, "http://127.0.0.1:8080")
        self.proxy_entry.pack(fill="x")

        bottom = ctk.CTkFrame(parent, fg_color="transparent")
        bottom.pack(fill="x", pady=(18, 8))
        self.start_btn = ctk.CTkButton(
            bottom,
            text="开始扫描",
            height=38,
            font=FONT_HEAD,
            fg_color=RED,
            hover_color="#ff4d5a",
            text_color="#ffffff",
            corner_radius=6,
            command=self._start_scan,
        )
        self.start_btn.pack(fill="x", pady=(0, 8))
        self.stop_btn = ctk.CTkButton(
            bottom,
            text="停止",
            height=34,
            font=FONT_BODY,
            fg_color=CARD,
            hover_color=RED_DARK,
            text_color=TEXT_DIM,
            corner_radius=6,
            state="disabled",
            command=self._stop_scan,
        )
        self.stop_btn.pack(fill="x")

    def _build_result_panel(self, parent):
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top, text="扫描结果", font=FONT_HEAD, text_color=TEXT).grid(
            row=0, column=0, sticky="w"
        )
        self.summary_label = ctk.CTkLabel(top, text="0 条", font=FONT_SMALL, text_color=TEXT_MUTED)
        self.summary_label.grid(row=0, column=1, sticky="e")

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Dir.Treeview",
            background=CARD,
            foreground=TEXT,
            fieldbackground=CARD,
            borderwidth=0,
            font=FONT_MONO,
            rowheight=27,
        )
        style.configure(
            "Dir.Treeview.Heading",
            background=INPUT,
            foreground=TEXT_MUTED,
            borderwidth=0,
            relief="flat",
            font=FONT_MONO_HEAD,
        )
        style.map("Dir.Treeview", background=[("selected", RED_DARK)], foreground=[("selected", TEXT)])
        style.map("Dir.Treeview.Heading", background=[("active", INPUT)])

        table_frame = ctk.CTkFrame(parent, fg_color="transparent")
        table_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_frame,
            columns=("status", "size", "path", "type", "redirect"),
            show="headings",
            style="Dir.Treeview",
        )
        for col, text, width, anchor in (
            ("status", "状态", 62, "center"),
            ("size", "大小", 78, "e"),
            ("path", "路径", 300, "w"),
            ("type", "类型", 150, "w"),
            ("redirect", "跳转", 250, "w"),
        ):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, minwidth=48, anchor=anchor)

        self.tree.tag_configure("s2xx", foreground=GREEN)
        self.tree.tag_configure("s3xx", foreground=CYAN)
        self.tree.tag_configure("s401", foreground=YELLOW)
        self.tree.tag_configure("s403", foreground="#60a5fa")
        self.tree.tag_configure("s5xx", foreground=RED)
        self.tree.tag_configure("s_other", foreground="#c084fc")

        scroll = ctk.CTkScrollbar(table_frame, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

    def _build_footer(self):
        footer = ctk.CTkFrame(self.root, height=42, corner_radius=0, fg_color=PANEL)
        footer.grid(row=2, column=0, sticky="ew")
        footer.grid_columnconfigure(1, weight=1)

        self.progress = ctk.CTkProgressBar(footer, width=230, height=9, fg_color=INPUT, progress_color=RED)
        self.progress.grid(row=0, column=0, padx=(14, 10), pady=12, sticky="w")
        self.progress.set(0)

        self.status_label = ctk.CTkLabel(footer, text="就绪", font=FONT_SMALL, text_color=GREEN)
        self.status_label.grid(row=0, column=1, padx=4, pady=10, sticky="w")

    def _set_status(self, text: str, color: str = TEXT_MUTED):
        self.status_label.configure(text=text, text_color=color)

    def _parse_status_codes(self, raw: str) -> set[int]:
        codes: set[int] = set()
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                start, end = part.split("-", 1)
                try:
                    codes.update(range(int(start), int(end) + 1))
                except ValueError:
                    continue
            else:
                try:
                    codes.add(int(part))
                except ValueError:
                    continue
        return codes

    def _parse_headers(self, raw: str) -> dict[str, str]:
        headers = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            if key:
                headers[key] = value.strip()
        return headers

    def _build_options(self):
        url = self.url_entry.get().strip()
        if not url:
            raise ValueError("请输入目标 URL")
        if not os.path.isfile(DEFAULT_WORDLIST):
            raise ValueError(f"默认字典不存在: {DEFAULT_WORDLIST}")

        try:
            threads = max(1, int(self.threads_entry.get().strip() or "25"))
        except ValueError as exc:
            raise ValueError("线程数必须是整数") from exc

        try:
            timeout = float(self.timeout_entry.get().strip() or "7.5")
        except ValueError as exc:
            raise ValueError("超时必须是数字") from exc

        extensions = tuple(
            item.strip().lstrip(".")
            for item in self.ext_entry.get().strip().split(",")
            if item.strip()
        )
        proxy = self.proxy_entry.get().strip()
        exclude_sizes = {
            item.strip().upper()
            for item in self.exclude_size_entry.get().strip().split(",")
            if item.strip()
        }

        return {
            "urls": [url],
            "urls_file": None,
            "stdin_urls": None,
            "cidr": None,
            "raw_file": None,
            "session_file": None,
            "session_id": None,
            "list_sessions": False,
            "sessions_dir": None,
            "config": None,
            "wordlists": [DEFAULT_WORDLIST],
            "extensions": extensions,
            "force_extensions": False,
            "overwrite_extensions": False,
            "exclude_extensions": (),
            "prefixes": (),
            "suffixes": (),
            "uppercase": False,
            "lowercase": False,
            "capitalization": False,
            "thread_count": threads,
            "recursive": self.recursive_var.get(),
            "deep_recursive": False,
            "force_recursive": False,
            "recursion_depth": 0,
            "recursion_status_codes": set(),
            "filter_threshold": 0,
            "subdirs": [],
            "exclude_subdirs": [],
            "include_status_codes": self._parse_status_codes(self.include_status_entry.get().strip()),
            "exclude_status_codes": self._parse_status_codes(self.exclude_status_entry.get().strip()),
            "exclude_sizes": exclude_sizes,
            "exclude_texts": None,
            "exclude_regex": None,
            "exclude_redirect": None,
            "exclude_response": None,
            "skip_on_status": set(),
            "minimum_response_size": 0,
            "maximum_response_size": 0,
            "max_time": 0,
            "target_max_time": 0,
            "http_method": self.method_var.get(),
            "data": None,
            "data_file": None,
            "nmap_report": None,
            "headers": self._parse_headers(self.headers_box.get("1.0", "end")),
            "headers_file": None,
            "follow_redirects": self.redirect_var.get(),
            "random_agents": False,
            "auth": None,
            "auth_type": None,
            "cert_file": None,
            "key_file": None,
            "user_agent": self.ua_entry.get().strip() or None,
            "cookie": self.cookie_entry.get().strip() or None,
            "timeout": timeout,
            "delay": 0.0,
            "proxies": [proxy] if proxy else [],
            "proxies_file": None,
            "proxy_auth": None,
            "replay_proxy": None,
            "tor": None,
            "scheme": None,
            "max_rate": 0,
            "max_retries": 1,
            "network_interface": None,
            "ip": None,
            "exit_on_error": False,
            "crawl": False,
            "async_mode": False,
            "full_url": False,
            "redirects_history": False,
            "color": False,
            "quiet": True,
            "disable_cli": True,
            "verbose": False,
            "output_file": None,
            "output_table": None,
            "output_formats": [],
            "mysql_url": None,
            "postgres_url": None,
            "log_file": None,
            "log_file_size": 0,
        }

    def _start_scan(self):
        if self.is_scanning:
            return
        try:
            scan_opts = self._build_options()
        except ValueError as exc:
            self._set_status(str(exc), RED)
            return

        self.results.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.summary_label.configure(text="0 条")
        self.progress.set(0)
        self._set_status("扫描中...", YELLOW)
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal", fg_color=RED, text_color="#ffffff")

        self.is_scanning = True
        self.scan_thread = threading.Thread(target=self._run_scan, args=(scan_opts,), daemon=True)
        self.scan_thread.start()

    def _run_scan(self, scan_opts):
        original_signal = None
        original_handle_pause = None
        try:
            from lib.core.data import options
            options.update(scan_opts)
            options["disable_cli"] = True
            options["quiet"] = True
            options["color"] = False

            import lib.view.terminal as tm
            gui_iface = GUIInterface(self.result_queue)
            tm.interface = gui_iface

            import lib.controller.controller as cm
            cm.interface = gui_iface
            original_handle_pause = cm.Controller.handle_pause

            def _gui_handle_pause(ctrl_self):
                if hasattr(ctrl_self, "fuzzer") and ctrl_self.fuzzer:
                    ctrl_self.fuzzer.quit()
                raise cm.QuitInterrupt

            cm.Controller.handle_pause = _gui_handle_pause

            ctrl = cm.Controller.__new__(cm.Controller)
            ctrl._handling_pause = False
            ctrl._force_quit_handler = cm.StandardForceQuitHandler()
            ctrl.loop = None

            try:
                ctrl.setup()
                ctrl.old_session = False
            except Exception as exc:
                self.result_queue.put({
                    "type": "status",
                    "data": {"message": f"初始化失败: {exc}", "level": "error"},
                })
                return

            self._controller = ctrl
            original_signal = signal.signal
            signal.signal = lambda *args, **kwargs: None

            try:
                ctrl.run()
            except (cm.QuitInterrupt, cm.SkipTargetInterrupt, SystemExit):
                pass
            except Exception as exc:
                self.result_queue.put({
                    "type": "status",
                    "data": {"message": f"扫描错误: {exc}", "level": "error"},
                })
        except Exception as exc:
            self.result_queue.put({
                "type": "status",
                "data": {"message": f"错误: {exc}", "level": "error"},
            })
        finally:
            if original_signal:
                signal.signal = original_signal
            if original_handle_pause:
                try:
                    import lib.controller.controller as cm
                    cm.Controller.handle_pause = original_handle_pause
                except Exception:
                    pass
            self.is_scanning = False
            self.result_queue.put({"type": "complete", "data": {}})

    def _stop_scan(self):
        if self._controller and hasattr(self._controller, "fuzzer") and self._controller.fuzzer:
            self._controller.fuzzer.quit()
        self._set_status("正在停止...", YELLOW)

    def _poll_queue(self):
        try:
            while True:
                msg = self.result_queue.get_nowait()
                msg_type = msg["type"]
                data = msg["data"]
                if msg_type == "result":
                    self._add_result(data)
                elif msg_type == "progress":
                    self._update_progress(data)
                elif msg_type == "status":
                    self._update_status(data)
                elif msg_type == "complete":
                    self._on_complete()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _status_tag(self, code: int) -> str:
        if 200 <= code < 300:
            return "s2xx"
        if 300 <= code < 400:
            return "s3xx"
        if code == 401:
            return "s401"
        if code == 403:
            return "s403"
        if 500 <= code < 600:
            return "s5xx"
        return "s_other"

    def _add_result(self, result: ScanResult):
        self.results.append(result)
        self.tree.insert(
            "",
            "end",
            values=(result.status, result.size, result.path, result.content_type, result.redirect),
            tags=(self._status_tag(result.status),),
        )
        self.summary_label.configure(text=f"{len(self.results)} 条")
        children = self.tree.get_children()
        if children:
            self.tree.see(children[-1])

    def _update_progress(self, data):
        index = data.get("index", 0)
        length = data.get("length", 1)
        if length <= 0:
            return
        value = min(index / length, 1.0)
        self.progress.set(value)
        self._set_status(f"扫描中 {index}/{length} ({value:.0%})", YELLOW)

    def _update_status(self, data):
        level = data.get("level", "info")
        color = RED if level == "error" else YELLOW if level == "warning" else TEXT_MUTED
        self._set_status(data.get("message", ""), color)

    def _on_complete(self):
        self.is_scanning = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled", fg_color=CARD, text_color=TEXT_DIM)
        self.progress.set(1.0 if self.results else 0)
        self._set_status(f"扫描完成，共 {len(self.results)} 条结果", GREEN)

    def _export_path(self, ext: str, label: str):
        if not self.results:
            self._set_status("暂无可导出的结果", YELLOW)
            return None
        return filedialog.asksaveasfilename(defaultextension=ext, filetypes=[(label, f"*{ext}")])

    def _export_txt(self):
        path = self._export_path(".txt", "Text")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as file:
            for result in self.results:
                line = f"{result.status}  {result.size:>8}  {result.path}"
                if result.redirect:
                    line += f"  ->  {result.redirect}"
                file.write(line + "\n")
        self._set_status(f"已导出 TXT: {path}", GREEN)

    def _export_csv(self):
        path = self._export_path(".csv", "CSV")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["status", "size", "path", "content_type", "redirect", "url", "elapsed"])
            for result in self.results:
                writer.writerow([
                    result.status,
                    result.size,
                    result.path,
                    result.content_type,
                    result.redirect,
                    result.url,
                    result.elapsed,
                ])
        self._set_status(f"已导出 CSV: {path}", GREEN)

    def _export_json(self):
        path = self._export_path(".json", "JSON")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as file:
            json.dump([asdict(result) for result in self.results], file, indent=2, ensure_ascii=False)
        self._set_status(f"已导出 JSON: {path}", GREEN)


if __name__ == "__main__":
    app = DirsearchGUI()
    app.run()
