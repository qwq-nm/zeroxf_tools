#!/usr/bin/env python3
"""TomcatScanPro GUI v2 — Modern dark-themed interface"""

import os
import re
import sys
import time
import queue
import logging
import threading
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.widgets.scrolled import ScrolledText
from ttkbootstrap.dialogs import Messagebox
import tkinter as tk
from tkinter import ttk, filedialog

import requests
requests.packages.urllib3.disable_warnings()

from TomcatScanPro import (
    adjust_thread_pool_size,
    check_cve_2017_12615_and_cnvd_2020_10487,
    check_weak_password,
)

ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')

# ── Tokyo Night 配色 ──────────────────────────────────────
C = dict(
    bg='#1a1b26',  panel='#24283b',  input='#1f2335',
    fg='#c0caf5',  dim='#565f89',    border='#3b4261',
    red='#f7768e', green='#9ece6a',  yellow='#e0af68',
    blue='#7aa2f7', cyan='#7dcfff',  purple='#bb9af7',
    orange='#ff9e64', teal='#73daca',
)

MONO = 'Menlo' if sys.platform == 'darwin' else 'Consolas'


class GUILogHandler(logging.Handler):
    def __init__(self, q):
        super().__init__()
        self.q = q

    def emit(self, record):
        msg = ANSI_RE.sub('', self.format(record))
        tag = 'info'
        if '[+]' in msg:
            tag = 'success'
        elif '[-]' in msg:
            tag = 'fail'
        elif '[!]' in msg or '[*]' in msg:
            tag = 'warn'
        self.q.put(('log', msg, tag))


class App:
    OUTPUT_FILE = 'success.txt'

    def __init__(self):
        self.root = tb.Window(title="TomcatScanPro", themename="darkly",
                              size=(1360, 880), minsize=(1080, 720))

        self.scanning = False
        self.stop_event = threading.Event()
        self.q = queue.Queue()
        self.results = []
        self.total = 0
        self.done = 0

        self._init_log()
        self._build_menu()
        self._build_ui()
        self._load_config()
        self._poll()

        self.root.bind('<Control-Return>', lambda e: self._start())
        self.root.bind('<Escape>', lambda e: self._stop() if self.scanning else None)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── logging ────────────────────────────────────────────

    def _init_log(self):
        lg = logging.getLogger()
        lg.setLevel(logging.INFO)
        for h in lg.handlers[:]:
            lg.removeHandler(h)
        h = GUILogHandler(self.q)
        h.setFormatter(logging.Formatter('%(message)s'))
        lg.addHandler(h)
        self.logger = lg

    # ── menu ───────────────────────────────────────────────

    def _build_menu(self):
        mb = tk.Menu(self.root, bg=C['panel'], fg=C['fg'],
                     activebackground=C['blue'], activeforeground='#fff')
        fm = tk.Menu(mb, tearoff=0, bg=C['panel'], fg=C['fg'],
                     activebackground=C['blue'], activeforeground='#fff')
        fm.add_command(label="导入配置 (yaml)", command=self._import_config)
        fm.add_command(label="导出配置", command=self._export_config)
        fm.add_separator()
        fm.add_command(label="退出", command=self._on_close)
        mb.add_cascade(label="文件", menu=fm)

        hm = tk.Menu(mb, tearoff=0, bg=C['panel'], fg=C['fg'],
                     activebackground=C['blue'], activeforeground='#fff')
        hm.add_command(label="关于", command=lambda: tb.Messagebox.show_info(
            "TomcatScanPro GUI v2\n\n"
            "Tomcat 漏洞扫描工具\n\n"
            "功能:\n"
            "  · 弱口令爆破 + 自动部署 Webshell\n"
            "  · CVE-2017-12615 PUT 任意文件上传\n"
            "  · CNVD-2020-10487 AJP 文件包含\n\n"
            "快捷键: Ctrl+Enter 开始 | Esc 停止",
            title="关于 TomcatScanPro", parent=self.root))
        mb.add_cascade(label="帮助", menu=hm)
        self.root.config(menu=mb)

    # ── main layout ────────────────────────────────────────

    def _build_ui(self):
        outer = ttk.Frame(self.root)
        outer.pack(fill=tk.BOTH, expand=True)

        # 左右分割: sidebar | main
        self.hpane = tk.PanedWindow(outer, orient=tk.HORIZONTAL,
                                    bg=C['border'], sashwidth=4,
                                    sashrelief=tk.FLAT, opaqueresize=True)
        self.hpane.pack(fill=tk.BOTH, expand=True)

        # 左侧 sidebar
        self.sidebar = ttk.Frame(self.hpane, width=310)
        self.hpane.add(self.sidebar, minsize=260, width=310)

        # 右侧 main
        self.main_area = ttk.Frame(self.hpane)
        self.hpane.add(self.main_area, minsize=500)

        self._build_sidebar()
        self._build_main_area()

        # 设置初始分隔线位置
        self.root.after(50, lambda: self.hpane.sash_place(0, 310, 0))

    # ── sidebar ────────────────────────────────────────────

    def _build_sidebar(self):
        nb = ttk.Notebook(self.sidebar)
        nb.pack(fill=tk.BOTH, expand=True, padx=(6, 2), pady=6)

        # Tab 1: 目标 URL
        t1 = ttk.Frame(nb)
        nb.add(t1, text='  目标 URL  ')
        self._build_url_tab(t1)

        # Tab 2: 凭据字典
        t2 = ttk.Frame(nb)
        nb.add(t2, text='  凭据字典  ')
        self._build_cred_tab(t2)

        # Tab 3: 扫描设置
        t3 = ttk.Frame(nb)
        nb.add(t3, text='  扫描设置  ')
        self._build_settings_tab(t3)

        self.sidebar_nb = nb

    def _make_text(self, parent, height=12):
        """创建统一风格的文本输入区"""
        txt = tk.Text(parent, wrap=tk.WORD, font=(MONO, 10),
                      bg=C['input'], fg=C['fg'], insertbackground=C['fg'],
                      selectbackground=C['blue'], selectforeground='#fff',
                      relief=tk.FLAT, borderwidth=6, height=height,
                      padx=6, pady=6)
        return txt

    def _build_url_tab(self, parent):
        tip = ttk.Label(parent, text="每行一个 URL，支持 http://host:port 格式",
                        font=('', 8), bootstyle=SECONDARY)
        tip.pack(anchor=tk.W, padx=8, pady=(8, 2))

        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 4))

        self.url_text = self._make_text(frame, height=18)
        sb = ttk.Scrollbar(frame, command=self.url_text.yview)
        self.url_text.configure(yscrollcommand=sb.set)
        self.url_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        bar = ttk.Frame(parent)
        bar.pack(fill=tk.X, padx=6, pady=(0, 8))
        tb.Button(bar, text="导入文件", bootstyle=SECONDARY,
                  command=lambda: self._import('url')).pack(side=tk.LEFT, padx=(0, 6))
        tb.Button(bar, text="清空", bootstyle=SECONDARY,
                  command=lambda: self.url_text.delete('1.0', tk.END)).pack(side=tk.LEFT)
        # 显示行数
        self.url_count = ttk.Label(bar, text="", font=('', 8), bootstyle=SECONDARY)
        self.url_count.pack(side=tk.RIGHT)
        self.url_text.bind('<KeyRelease>', lambda e: self._update_count(self.url_text, self.url_count))

    def _build_cred_tab(self, parent):
        # ── 用户名 ──
        hdr1 = ttk.Frame(parent)
        hdr1.pack(fill=tk.X, padx=8, pady=(8, 2))
        ttk.Label(hdr1, text="用户名列表", font=('', 9, 'bold')).pack(side=tk.LEFT)
        self.user_count = ttk.Label(hdr1, text="", font=('', 8), bootstyle=SECONDARY)
        self.user_count.pack(side=tk.RIGHT)

        uf = ttk.Frame(parent)
        uf.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 4))
        self.user_text = self._make_text(uf, height=6)
        usb = ttk.Scrollbar(uf, command=self.user_text.yview)
        self.user_text.configure(yscrollcommand=usb.set)
        self.user_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        usb.pack(side=tk.RIGHT, fill=tk.Y)
        self.user_text.bind('<KeyRelease>', lambda e: self._update_count(self.user_text, self.user_count))

        ubar = ttk.Frame(parent)
        ubar.pack(fill=tk.X, padx=6)
        tb.Button(ubar, text="导入", bootstyle=SECONDARY,
                  command=lambda: self._import('user')).pack(side=tk.LEFT, padx=(0, 6))
        tb.Button(ubar, text="清空", bootstyle=SECONDARY,
                  command=lambda: self.user_text.delete('1.0', tk.END)).pack(side=tk.LEFT)

        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=8, pady=8)

        # ── 密码 ──
        hdr2 = ttk.Frame(parent)
        hdr2.pack(fill=tk.X, padx=8, pady=(0, 2))
        ttk.Label(hdr2, text="密码列表", font=('', 9, 'bold')).pack(side=tk.LEFT)
        self.pwd_count = ttk.Label(hdr2, text="", font=('', 8), bootstyle=SECONDARY)
        self.pwd_count.pack(side=tk.RIGHT)

        pf = ttk.Frame(parent)
        pf.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 4))
        self.passwd_text = self._make_text(pf, height=6)
        psb = ttk.Scrollbar(pf, command=self.passwd_text.yview)
        self.passwd_text.configure(yscrollcommand=psb.set)
        self.passwd_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        psb.pack(side=tk.RIGHT, fill=tk.Y)
        self.passwd_text.bind('<KeyRelease>', lambda e: self._update_count(self.passwd_text, self.pwd_count))

        pbar = ttk.Frame(parent)
        pbar.pack(fill=tk.X, padx=6, pady=(0, 8))
        tb.Button(pbar, text="导入", bootstyle=SECONDARY,
                  command=lambda: self._import('passwd')).pack(side=tk.LEFT, padx=(0, 6))
        tb.Button(pbar, text="清空", bootstyle=SECONDARY,
                  command=lambda: self.passwd_text.delete('1.0', tk.END)).pack(side=tk.LEFT)

    def _build_settings_tab(self, parent):
        canvas = tk.Canvas(parent, bg=C['bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>",
                          lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 鼠标滚轮
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel, add='+')

        sf = scroll_frame
        # ── 扫描选项 ──
        ttk.Label(sf, text='扫描选项', font=('', 10, 'bold')).pack(
            anchor=tk.W, padx=14, pady=(14, 6))

        self.opt_weak = tk.BooleanVar(value=True)
        self.opt_cve = tk.BooleanVar(value=True)
        self.opt_cnvd = tk.BooleanVar(value=True)

        for text, var, desc in [
            ('弱口令爆破 + Webshell 部署', self.opt_weak, '爆破 Tomcat Manager 并自动上传哥斯拉马'),
            ('CVE-2017-12615 PUT 上传', self.opt_cve, 'Windows + readonly=false 时可 PUT 上传 JSP'),
            ('CNVD-2020-10487 AJP 包含', self.opt_cnvd, 'Ghostcat 幽灵猫 AJP 文件包含/读取'),
        ]:
            f = ttk.Frame(sf)
            f.pack(fill=tk.X, padx=14, pady=2)
            ttk.Checkbutton(f, text=text, variable=var).pack(anchor=tk.W)
            ttk.Label(f, text=desc, font=('', 8), bootstyle=SECONDARY).pack(anchor=tk.W, padx=20)

        ttk.Separator(sf, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=14, pady=12)

        # ── 线程设置 ──
        ttk.Label(sf, text='线程设置', font=('', 10, 'bold')).pack(
            anchor=tk.W, padx=14, pady=(4, 2))

        self.max_threads = self._row(sf, '最大线程数', '500')
        self.min_threads = self._row(sf, '最小线程数', '100')

        ttk.Separator(sf, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=14, pady=12)

        # ── 重试设置 ──
        ttk.Label(sf, text='重试设置', font=('', 10, 'bold')).pack(
            anchor=tk.W, padx=14, pady=(4, 2))

        self.retries = self._row(sf, '最大重试', '3')
        self.retry_delay = self._row(sf, '重试间隔 (秒)', '2')

        ttk.Separator(sf, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=14, pady=12)

        # ── AJP ──
        ttk.Label(sf, text='CNVD-2020-10487 / AJP', font=('', 10, 'bold')).pack(
            anchor=tk.W, padx=14, pady=(4, 2))

        self.ajp_port = self._row(sf, 'AJP 端口', '8009')
        self.ajp_path = self._row(sf, '读取路径', 'WEB-INF/web.xml')
        self.ajp_check = self._row(sf, '匹配关键词', 'Welcome to Tomcat')

        # 底部间距
        ttk.Frame(sf, height=20).pack()

    @staticmethod
    def _row(parent, label, default):
        f = ttk.Frame(parent)
        f.pack(fill=tk.X, padx=14, pady=3)
        ttk.Label(f, text=label, width=16, anchor=tk.W).pack(side=tk.LEFT)
        var = tk.StringVar(value=default)
        ttk.Entry(f, textvariable=var, width=14).pack(side=tk.LEFT, padx=4)
        return var

    # ── main area (right) ─────────────────────────────────

    def _build_main_area(self):
        self._build_toolbar()
        self._build_output()
        self._build_statusbar()

    def _build_toolbar(self):
        bar = ttk.Frame(self.main_area)
        bar.pack(fill=tk.X, padx=6, pady=(6, 2))

        self.start_btn = tb.Button(bar, text="  ▶  开始扫描  ", bootstyle=SUCCESS,
                                   command=self._start)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.stop_btn = tb.Button(bar, text="  ■  停止  ", bootstyle=DANGER,
                                  command=self._stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 6))

        tb.Button(bar, text="导出结果", bootstyle=SECONDARY,
                  command=self._export).pack(side=tk.LEFT, padx=(0, 6))

        tb.Button(bar, text="清空日志", bootstyle=SECONDARY,
                  command=self._clear_log).pack(side=tk.LEFT)

        # 右侧: 进度
        self.pct_label = ttk.Label(bar, text="", width=16, anchor=tk.E,
                                   font=('', 9), bootstyle=SECONDARY)
        self.pct_label.pack(side=tk.RIGHT, padx=4)

        self.progress = ttk.Progressbar(bar, maximum=100, length=220, bootstyle=STRIPED)
        self.progress.pack(side=tk.RIGHT, padx=4)

    def _build_output(self):
        nb = ttk.Notebook(self.main_area)
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=2)

        # ── 日志标签 ──
        log_tab = ttk.Frame(nb)
        nb.add(log_tab, text='  扫描日志  ')

        self.log_text = tk.Text(log_tab, wrap=tk.WORD, state=tk.DISABLED,
                                bg=C['bg'], fg=C['fg'],
                                font=(MONO, 10), insertbackground=C['fg'],
                                selectbackground=C['blue'], selectforeground='#fff',
                                relief=tk.FLAT, borderwidth=8,
                                padx=8, pady=8)
        ls = ttk.Scrollbar(log_tab, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=ls.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ls.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text.tag_configure('success', foreground=C['red'])
        self.log_text.tag_configure('fail', foreground=C['green'])
        self.log_text.tag_configure('warn', foreground=C['yellow'])
        self.log_text.tag_configure('info', foreground=C['blue'])
        self.log_text.tag_configure('error', foreground=C['orange'])
        self.log_text.tag_configure('ts', foreground=C['dim'])

        # ── 结果标签 ──
        res_tab = ttk.Frame(nb)
        nb.add(res_tab, text='  扫描结果  ')

        cols = ('url', 'type', 'detail')
        self.tree = ttk.Treeview(res_tab, columns=cols, show='headings',
                                 selectmode='browse', height=20)
        self.tree.heading('url', text='目标 URL', anchor=tk.W)
        self.tree.heading('type', text='漏洞类型', anchor=tk.W)
        self.tree.heading('detail', text='详细信息', anchor=tk.W)
        self.tree.column('url', width=320, minwidth=180)
        self.tree.column('type', width=180, minwidth=120)
        self.tree.column('detail', width=600, minwidth=200)

        self.tree.tag_configure('weakpwd', foreground=C['red'])
        self.tree.tag_configure('cve', foreground=C['yellow'])
        self.tree.tag_configure('cnvd', foreground=C['cyan'])
        self.tree.tag_configure('webshell', foreground=C['purple'])

        rs = ttk.Scrollbar(res_tab, command=self.tree.yview)
        self.tree.configure(yscrollcommand=rs.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        rs.pack(side=tk.RIGHT, fill=tk.Y)

        # 右键菜单
        self._ctx = tk.Menu(self.tree, tearoff=0, bg=C['panel'], fg=C['fg'],
                            activebackground=C['blue'], activeforeground='#fff')
        self._ctx.add_command(label="复制选中", command=self._copy_result)
        self._ctx.add_command(label="复制全部", command=self._copy_all_results)
        self.tree.bind('<Button-2>', lambda e: self._ctx.post(e.x_root, e.y_root))
        self.tree.bind('<Button-3>', lambda e: self._ctx.post(e.x_root, e.y_root))
        self.tree.bind('<Control-c>', lambda e: self._copy_result())

        self.output_nb = nb

    def _build_statusbar(self):
        bar = tk.Frame(self.main_area, bg=C['panel'], height=28)
        bar.pack(fill=tk.X, padx=6, pady=(2, 6))
        bar.pack_propagate(False)

        self.status_var = tk.StringVar(value="就绪")
        tk.Label(bar, textvariable=self.status_var, bg=C['panel'], fg=C['fg'],
                 font=('', 9)).pack(side=tk.LEFT, padx=10)

        self.stats_var = tk.StringVar(value="")
        tk.Label(bar, textvariable=self.stats_var, bg=C['panel'], fg=C['dim'],
                 font=(MONO, 9)).pack(side=tk.RIGHT, padx=10)

    # ── helpers ────────────────────────────────────────────

    @staticmethod
    def _update_count(widget, label):
        n = len([l for l in widget.get('1.0', tk.END).splitlines() if l.strip()])
        label.configure(text=f"{n} 条" if n else "")

    # ── config / file I/O ──────────────────────────────────

    def _load_config(self):
        try:
            cfg = yaml.safe_load(open('config.yaml', 'r', encoding='utf-8'))
        except Exception:
            return

        files = cfg.get('files', {})
        for key, widget in [('url_file', self.url_text),
                            ('user_file', self.user_text),
                            ('passwd_file', self.passwd_text)]:
            fpath = files.get(key)
            if fpath and os.path.isfile(fpath):
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                if content:
                    widget.insert('1.0', content + '\n')

        tp = cfg.get('thread_pool', {})
        self.max_threads.set(str(tp.get('max_workers_limit', 500)))
        self.min_threads.set(str(tp.get('min_workers', 100)))

        retry = cfg.get('retry', {}).get('check_weak_password', {})
        self.retries.set(str(retry.get('max_retries', 3)))
        self.retry_delay.set(str(retry.get('retry_delay', 2)))

        cnvd = cfg.get('cnvd_2020_10487', {})
        self.ajp_port.set(str(cnvd.get('port', 8009)))
        self.ajp_path.set(str(cnvd.get('file_path', 'WEB-INF/web.xml')))
        self.ajp_check.set(str(cnvd.get('lfi_check', 'Welcome to Tomcat')))

        self._update_count(self.url_text, self.url_count)
        self._update_count(self.user_text, self.user_count)
        self._update_count(self.passwd_text, self.pwd_count)
        self._update_stats()

    def _import(self, name):
        path = filedialog.askopenfilename(
            title="导入文件", filetypes=[("文本", "*.txt"), ("所有", "*.*")])
        if not path:
            return
        widget = {'url': self.url_text, 'user': self.user_text,
                  'passwd': self.passwd_text}[name]
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        current = widget.get('1.0', tk.END).strip()
        widget.delete('1.0', tk.END)
        widget.insert('1.0', (current + '\n' + content).strip() if current else content)
        count_label = {'url': self.url_count, 'user': self.user_count,
                       'passwd': self.pwd_count}[name]
        self._update_count(widget, count_label)

    def _import_config(self):
        path = filedialog.askopenfilename(
            title="导入配置", filetypes=[("YAML", "*.yaml *.yml"), ("所有", "*.*")])
        if not path:
            return
        try:
            cfg = yaml.safe_load(open(path, 'r', encoding='utf-8'))
        except Exception as e:
            tb.Messagebox.show_error(f"配置加载失败: {e}", parent=self.root)
            return
        for key, widget in [('url_file', self.url_text),
                            ('user_file', self.user_text),
                            ('passwd_file', self.passwd_text)]:
            fpath = cfg.get('files', {}).get(key)
            if fpath and os.path.isfile(fpath):
                widget.delete('1.0', tk.END)
                with open(fpath, 'r', encoding='utf-8') as f:
                    widget.insert('1.0', f.read().strip())
        tp = cfg.get('thread_pool', {})
        self.max_threads.set(str(tp.get('max_workers_limit', 500)))
        self.min_threads.set(str(tp.get('min_workers', 100)))
        retry = cfg.get('retry', {}).get('check_weak_password', {})
        self.retries.set(str(retry.get('max_retries', 3)))
        self.retry_delay.set(str(retry.get('retry_delay', 2)))
        cnvd = cfg.get('cnvd_2020_10487', {})
        self.ajp_port.set(str(cnvd.get('port', 8009)))
        self.ajp_path.set(str(cnvd.get('file_path', 'WEB-INF/web.xml')))
        self.ajp_check.set(str(cnvd.get('lfi_check', 'Welcome to Tomcat')))
        self._update_count(self.url_text, self.url_count)
        self._update_count(self.user_text, self.user_count)
        self._update_count(self.passwd_text, self.pwd_count)
        tb.Messagebox.show_info("配置已导入", parent=self.root)

    def _export_config(self):
        path = filedialog.asksaveasfilename(
            title="导出配置", defaultextension=".yaml",
            filetypes=[("YAML", "*.yaml")])
        if not path:
            return
        cfg = {
            'thread_pool': {
                'max_workers_limit': int(self.max_threads.get()),
                'min_workers': int(self.min_threads.get()),
                'combination_per_thread': 40,
            },
            'retry': {
                'check_weak_password': {
                    'max_retries': int(self.retries.get()),
                    'retry_delay': int(self.retry_delay.get()),
                },
                'deploy_godzilla_war': {'max_retries': 3, 'retry_delay': 2},
            },
            'cnvd_2020_10487': {
                'port': int(self.ajp_port.get()),
                'file_path': self.ajp_path.get(),
                'lfi_check': self.ajp_check.get(),
            },
            'files': {
                'url_file': 'data/urls.txt',
                'user_file': 'data/user.txt',
                'passwd_file': 'data/passwd.txt',
                'output_file': self.OUTPUT_FILE,
            },
        }
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        tb.Messagebox.show_info(f"配置已导出到 {path}", parent=self.root)

    # ── scan ───────────────────────────────────────────────

    def _start(self):
        urls = [l.strip() for l in self.url_text.get('1.0', tk.END).splitlines() if l.strip()]
        users = [l.strip() for l in self.user_text.get('1.0', tk.END).splitlines() if l.strip()]
        pwds = [l.strip() for l in self.passwd_text.get('1.0', tk.END).splitlines() if l.strip()]

        if not urls:
            tb.Messagebox.show_warning("请输入目标 URL", parent=self.root)
            return
        if not users or not pwds:
            tb.Messagebox.show_warning("请输入用户名和密码字典", parent=self.root)
            return

        self.scanning = True
        self.stop_event.clear()
        self.done = 0
        self.total = len(urls)
        self.results.clear()
        self.progress['value'] = 0

        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.status_var.set("扫描中...")
        self._update_stats()

        with open(self.OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('')

        threading.Thread(target=self._worker, args=(urls, users, pwds), daemon=True).start()

    def _stop(self):
        self.stop_event.set()
        self.status_var.set("正在停止...")

    def _worker(self, urls, users, passwords):
        max_w = int(self.max_threads.get())
        min_w = int(self.min_threads.get())
        retries = int(self.retries.get())
        delay = int(self.retry_delay.get())
        do_weak = self.opt_weak.get()
        do_cve = self.opt_cve.get()
        do_cnvd = self.opt_cnvd.get()

        shell_content = ''
        try:
            cfg = yaml.safe_load(open('config.yaml', 'r', encoding='utf-8'))
            shell_content = cfg.get('files', {}).get('shell_file_content', '')
        except Exception:
            pass

        config = {
            'files': {'output_file': self.OUTPUT_FILE, 'shell_file_content': shell_content},
            'retry': {
                'check_weak_password': {'max_retries': retries, 'retry_delay': delay},
                'deploy_godzilla_war': {'max_retries': retries, 'retry_delay': delay},
            },
            'cnvd_2020_10487': {
                'port': int(self.ajp_port.get()),
                'file_path': self.ajp_path.get(),
                'lfi_check': self.ajp_check.get(),
            },
            'thread_pool': {
                'max_workers_limit': max_w, 'min_workers': min_w,
                'combination_per_thread': 40,
            },
        }

        count = len(urls) * len(users) * len(passwords)
        workers = adjust_thread_pool_size(count, max_w, min_w, 40)

        self.q.put(('log',
                    f'[*] 启动扫描: {len(urls)} 目标, '
                    f'{len(users)}×{len(passwords)}={count} 组凭据, '
                    f'{workers} 线程', 'info'))

        def scan_one(url):
            if self.stop_event.is_set():
                return
            url = url.strip()
            if not url:
                return

            if do_cve or do_cnvd:
                try:
                    ok, vtype, eurl = check_cve_2017_12615_and_cnvd_2020_10487(url, config)
                    if ok:
                        self.q.put(('result', url, vtype, f'Exploited: {eurl}'))
                        with open(self.OUTPUT_FILE, 'a', encoding='utf-8') as f:
                            f.write(f"{url} - {vtype} Exploited: {eurl}\n")
                except Exception as e:
                    self.q.put(('log', f'[!] 漏洞检测异常 {url}: {e}', 'warn'))

            if do_weak and not self.stop_event.is_set():
                try:
                    check_weak_password(url, users, passwords,
                                        self.OUTPUT_FILE, retries, delay, config)
                except Exception:
                    pass

            self.q.put(('progress',))

        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futs = [pool.submit(scan_one, u) for u in urls]
                for f in as_completed(futs):
                    if self.stop_event.is_set():
                        break
                    try:
                        f.result()
                    except Exception:
                        pass
        except Exception as e:
            self.q.put(('log', f'[-] 扫描异常: {e}', 'error'))

        self.q.put(('done',))

    # ── queue poll ─────────────────────────────────────────

    def _poll(self):
        batch = 0
        while True:
            try:
                item = self.q.get_nowait()
            except queue.Empty:
                break

            kind = item[0]

            if kind == 'log':
                _, msg, tag = item
                self.log_text.configure(state=tk.NORMAL)
                ts = time.strftime('%H:%M:%S')
                self.log_text.insert(tk.END, f'[{ts}] ', 'ts')
                self.log_text.insert(tk.END, msg + '\n', tag)
                self.log_text.configure(state=tk.DISABLED)
                self.log_text.see(tk.END)
                batch += 1

            elif kind == 'result':
                _, url, rtype, detail = item
                tmap = {'弱口令': 'weakpwd', 'CVE-2017-12615': 'cve',
                        'CNVD-2020-10487': 'cnvd', 'Webshell': 'webshell'}
                tag = tmap.get(rtype, '')
                self.tree.insert('', tk.END, values=(url, rtype, detail), tags=(tag,))
                self.results.append((url, rtype, detail))
                self._update_stats()

            elif kind == 'progress':
                self.done += 1
                pct = (self.done / self.total * 100) if self.total else 0
                self.progress['value'] = pct
                self.pct_label.configure(text=f'{self.done} / {self.total}  ({pct:.0f}%)')
                self.status_var.set(f"扫描中")
                self._update_stats()

            elif kind == 'done':
                self.scanning = False
                self.start_btn.configure(state=tk.NORMAL)
                self.stop_btn.configure(state=tk.DISABLED)
                self.progress['value'] = 100
                self.pct_label.configure(text=f'{self.total} / {self.total}  (100%)')
                self.status_var.set("扫描完成")
                self._update_stats()
                self.q.put(('log',
                            f'[*] 扫描结束, 共发现 {len(self.results)} 条结果', 'info'))

        # 限制日志行数防止内存溢出
        if batch > 0:
            line_count = int(self.log_text.index('end-1c').split('.')[0])
            if line_count > 5000:
                self.log_text.configure(state=tk.NORMAL)
                self.log_text.delete('1.0', f'{line_count - 4000}.0')
                self.log_text.configure(state=tk.DISABLED)

        self.root.after(80, self._poll)

    def _update_stats(self):
        self.stats_var.set(
            f"目标 {self.total}  |  已扫 {self.done}  |  发现 {len(self.results)}")

    def _clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete('1.0', tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _export(self):
        if not self.results:
            tb.Messagebox.show_info("暂无结果可导出", parent=self.root)
            return
        path = filedialog.asksaveasfilename(
            title="导出结果", defaultextension=".txt",
            filetypes=[("文本", "*.txt"), ("CSV", "*.csv"), ("所有", "*.*")])
        if not path:
            return
        with open(path, 'w', encoding='utf-8') as f:
            for url, rtype, detail in self.results:
                f.write(f"{url}\t{rtype}\t{detail}\n")
        self.q.put(('log', f'[*] 结果已导出到 {path}', 'info'))

    def _copy_result(self):
        sel = self.tree.selection()
        if sel:
            vals = self.tree.item(sel[0], 'values')
            self.root.clipboard_clear()
            self.root.clipboard_append('\t'.join(vals))

    def _copy_all_results(self):
        self.root.clipboard_clear()
        lines = []
        for item in self.tree.get_children():
            vals = self.tree.item(item, 'values')
            lines.append('\t'.join(vals))
        self.root.clipboard_append('\n'.join(lines))

    def _on_close(self):
        if self.scanning:
            self.stop_event.set()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    App().run()


if __name__ == '__main__':
    main()
