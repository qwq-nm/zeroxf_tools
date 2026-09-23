import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import subprocess
import threading

import customtkinter as ctk

from revshell_templates import LISTENER_TYPES
from revshell_theme import BG_CARD, BG_HOVER, BG_INPUT, GREEN, MONO_S, R, R_CARD, RED, TEXT, TEXT_SEC, TEXT_TER
from revshell_utils import normalize_port, terminate_process


class ListenerPanel:
    def build_listener(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        ctrl = ctk.CTkFrame(parent, corner_radius=R_CARD, fg_color=BG_CARD, border_width=0)
        ctrl.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ctrl.grid_columnconfigure(4, weight=1)

        lis_names = [t[0] for t in LISTENER_TYPES]
        ctk.CTkLabel(ctrl, text="类型", font=("pingfang sc", 10), text_color=TEXT_SEC).grid(row=0, column=0, padx=(16, 4), pady=10)
        self._lis_type_var = ctk.StringVar(value=lis_names[0])
        ctk.CTkOptionMenu(
            ctrl, values=lis_names, variable=self._lis_type_var, width=120, height=30,
            font=("pingfang sc", 12), corner_radius=8, fg_color=BG_INPUT, button_color=TEXT_TER,
            button_hover_color=TEXT_SEC, text_color=TEXT, dropdown_fg_color=BG_CARD,
            dropdown_text_color=TEXT,
        ).grid(row=0, column=1, padx=(0, 20), pady=10)

        ctk.CTkLabel(ctrl, text="端口", font=("pingfang sc", 10), text_color=TEXT_SEC).grid(row=0, column=2, padx=(0, 4), pady=10)
        self._lis_port_var = ctk.StringVar(value="4444")
        ctk.CTkEntry(
            ctrl, textvariable=self._lis_port_var, width=80, height=30, font=MONO_S,
            corner_radius=8, fg_color=BG_INPUT, border_width=0, text_color=TEXT,
        ).grid(row=0, column=3, padx=(0, 20), pady=10)

        self._lis_start_btn = ctk.CTkButton(
            ctrl, text="▶ 启动监听", width=110, height=30, font=("pingfang sc", 12, "bold"),
            corner_radius=R, fg_color=GREEN, hover_color="#2db84d", text_color="#ffffff",
            command=self._start_listener,
        )
        self._lis_start_btn.grid(row=0, column=4, sticky="e", padx=(0, 6), pady=10)

        self._lis_stop_btn = ctk.CTkButton(
            ctrl, text="■ 停止", width=70, height=30, font=("pingfang sc", 10),
            corner_radius=R, fg_color=BG_INPUT, hover_color=BG_HOVER, text_color=TEXT_SEC,
            state="disabled", command=self._stop_listener,
        )
        self._lis_stop_btn.grid(row=0, column=5, padx=(0, 16), pady=10)

        self._lis_cmd_label = ctk.CTkLabel(parent, text="", font=MONO_S, text_color=TEXT_SEC, anchor="w")
        self._lis_cmd_label.grid(row=1, column=0, sticky="w", pady=(0, 6))
        self._update_lis_cmd()
        self._lis_type_var.trace_add("write", lambda *_: self._update_lis_cmd())
        self._lis_port_var.trace_add("write", lambda *_: self._update_lis_cmd())

        log_card = ctk.CTkFrame(parent, corner_radius=R_CARD, fg_color=BG_CARD, border_width=0)
        log_card.grid(row=2, column=0, sticky="nsew")
        log_card.grid_rowconfigure(1, weight=1)
        log_card.grid_columnconfigure(0, weight=1)

        log_hdr = ctk.CTkFrame(log_card, fg_color="transparent", height=36)
        log_hdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 0))
        ctk.CTkLabel(log_hdr, text="● 日志输出", font=("pingfang sc", 11, "bold"), text_color=GREEN).pack(side="left")

        self._lis_log = ctk.CTkTextbox(
            log_card, font=MONO_S, fg_color=BG_INPUT, corner_radius=8,
            text_color=TEXT, wrap="word", state="disabled", border_width=0,
        )
        self._lis_log.grid(row=1, column=0, sticky="nsew", padx=14, pady=(6, 14))

    def _update_lis_cmd(self):
        port = normalize_port(self._lis_port_var.get(), "4444")
        if not port:
            self._lis_cmd_label.configure(text="端口无效：请输入 1-65535")
            return
        name = self._lis_type_var.get()
        for n, tmpl in LISTENER_TYPES:
            if n == name:
                self._lis_cmd_label.configure(text=f"$ {tmpl.format(port=port)}")
                break

    def _start_listener(self):
        if self._listener_proc and self._listener_proc.poll() is None:
            return
        port = normalize_port(self._lis_port_var.get(), "4444")
        if not port:
            self._log("[!] 端口无效，请输入 1-65535\n")
            return
        name = self._lis_type_var.get()
        cmd_str = None
        for n, tmpl in LISTENER_TYPES:
            if n == name:
                cmd_str = tmpl.format(port=port)
                break
        if not cmd_str:
            return

        self._log(f"[*] 启动: {cmd_str}\n")
        self._lis_start_btn.configure(state="disabled")
        self._lis_stop_btn.configure(state="normal", fg_color=RED)

        def _run():
            try:
                self._listener_proc = subprocess.Popen(
                    cmd_str, shell=True, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, bufsize=1,
                    start_new_session=True,
                )
                for line in self._listener_proc.stdout:
                    self.root.after(0, self._log, line)
                self._listener_proc.wait()
            except Exception as e:
                self.root.after(0, self._log, f"[!] 错误: {e}\n")
            finally:
                self.root.after(0, self._on_listener_done)

        self._listener_thread = threading.Thread(target=_run, daemon=True)
        self._listener_thread.start()

    def _stop_listener(self):
        if self._listener_proc and self._listener_proc.poll() is None:
            terminate_process(self._listener_proc)
            self._log("[*] 已停止监听\n")

    def _on_listener_done(self):
        self._lis_start_btn.configure(state="normal")
        self._lis_stop_btn.configure(state="disabled", fg_color=BG_INPUT)
        self._listener_proc = None

    def _log(self, text):
        self._lis_log.configure(state="normal")
        self._lis_log.insert("end", text)
        self._lis_log.see("end")
        self._lis_log.configure(state="disabled")
