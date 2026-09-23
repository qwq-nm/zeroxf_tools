#!/usr/bin/env python3
"""反弹 Shell 命令生成器 & 监听器 — Apple HIG 风格"""

import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import customtkinter as ctk

from revshell_generator import GeneratorPanel
from revshell_listener import ListenerPanel
from revshell_theme import ACCENT, BG, BG_CARD, DIVIDER, FONT_B, FONT_S, FONT_T, GREEN, R, TEXT
from revshell_utils import detect_ip
from revshell_vps import VpsPanel


class RevShellGUI(GeneratorPanel, ListenerPanel, VpsPanel):
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("反弹 Shell")
        self.root.geometry("820x680")
        self.root.minsize(660, 500)
        self.root.configure(fg_color=BG)
        ctk.set_appearance_mode("light")

        self._listener_proc = None
        self._listener_thread = None
        self._last_lang = None
        self._auto_ip = detect_ip()
        self._variant_keys = []
        self._trace_bound = False
        self._current_langs = []

        self._build_topbar()
        self._build_body()
        self._build_bottombar()
        self._refresh_lang_menu(trigger_generate=False)
        self._generate()

    def _build_topbar(self):
        bar = ctk.CTkFrame(self.root, height=56, corner_radius=0, fg_color=BG_CARD, border_width=0)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(2, weight=1)

        ctk.CTkFrame(bar, height=1, fg_color=DIVIDER).grid(row=1, column=0, columnspan=6, sticky="ew")
        ctk.CTkLabel(bar, text="反弹 Shell", font=FONT_T, text_color=TEXT).grid(row=0, column=0, padx=(20, 24), pady=10)

        conn = ctk.CTkFrame(bar, fg_color="#f5f5f7", corner_radius=R)
        conn.grid(row=0, column=1, padx=4, pady=10)

        ctk.CTkLabel(conn, text="LHOST", font=("sf mono", 10, "bold"), text_color=ACCENT, width=46).pack(side="left", padx=(10, 2), pady=6)
        self._ip_var = ctk.StringVar(value=self._auto_ip or "10.0.0.1")
        ctk.CTkEntry(conn, textvariable=self._ip_var, width=150, height=28, font=("sf mono", 11),
                     corner_radius=6, fg_color=BG_CARD, border_width=0, text_color="#1d1d1f", placeholder_text="IP"
                     ).pack(side="left", padx=(0, 12), pady=6)

        ctk.CTkLabel(conn, text="LPORT", font=("sf mono", 10, "bold"), text_color=ACCENT, width=48).pack(side="left", padx=(0, 2))
        self._port_var = ctk.StringVar(value="4444")
        ctk.CTkEntry(conn, textvariable=self._port_var, width=80, height=28, font=("sf mono", 11),
                     corner_radius=6, fg_color=BG_CARD, border_width=0, text_color="#1d1d1f", placeholder_text="Port"
                     ).pack(side="left", padx=(0, 10), pady=6)

    def _build_body(self):
        body = ctk.CTkFrame(self.root, fg_color=BG)
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=(12, 6))
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        tab_bar = ctk.CTkFrame(body, fg_color="transparent")
        tab_bar.grid(row=0, column=0, sticky="w", pady=(0, 12))

        self._tab_gen_btn = ctk.CTkButton(
            tab_bar, text="生成器", width=80, height=32, font=FONT_B, corner_radius=R,
            fg_color=ACCENT, hover_color=ACCENT, text_color="#ffffff",
            command=lambda: self._on_tab("generator"),
        )
        self._tab_gen_btn.pack(side="left", padx=(0, 6))
        self._tab_lis_btn = ctk.CTkButton(
            tab_bar, text="监听器", width=80, height=32, font=FONT_B, corner_radius=R,
            fg_color="#e8e8ed", hover_color="#ededf0", text_color="#86868b",
            command=lambda: self._on_tab("listener"),
        )
        self._tab_lis_btn.pack(side="left", padx=(0, 6))
        self._tab_vps_btn = ctk.CTkButton(
            tab_bar, text="VPS转发", width=80, height=32, font=FONT_B, corner_radius=R,
            fg_color="#e8e8ed", hover_color="#ededf0", text_color="#86868b",
            command=lambda: self._on_tab("vps"),
        )
        self._tab_vps_btn.pack(side="left")

        self._gen_frame = ctk.CTkFrame(body, fg_color=BG)
        self._lis_frame = ctk.CTkFrame(body, fg_color=BG)
        self._vps_frame = ctk.CTkFrame(body, fg_color=BG)
        self.build_generator(self._gen_frame)
        self.build_listener(self._lis_frame)
        self.build_vps(self._vps_frame)
        self._gen_frame.grid(row=1, column=0, sticky="nsew")

    def _build_bottombar(self):
        bar = ctk.CTkFrame(self.root, height=32, corner_radius=0, fg_color=BG_CARD, border_width=0)
        bar.grid(row=2, column=0, sticky="ew")
        ctk.CTkFrame(bar, height=1, fg_color=DIVIDER).grid(row=0, column=0, columnspan=2, sticky="ew")
        self._status = ctk.CTkLabel(bar, text="就绪", font=FONT_S, text_color=GREEN, anchor="w")
        self._status.grid(row=1, column=0, padx=20, pady=4, sticky="w")

    def _on_tab(self, tab):
        self._gen_frame.grid_forget()
        self._lis_frame.grid_forget()
        self._vps_frame.grid_forget()
        self._tab_gen_btn.configure(fg_color="#e8e8ed", text_color="#86868b")
        self._tab_lis_btn.configure(fg_color="#e8e8ed", text_color="#86868b")
        self._tab_vps_btn.configure(fg_color="#e8e8ed", text_color="#86868b")
        if tab == "generator":
            self._gen_frame.grid(row=1, column=0, sticky="nsew")
            self._tab_gen_btn.configure(fg_color=ACCENT, text_color="#ffffff")
        elif tab == "listener":
            self._lis_frame.grid(row=1, column=0, sticky="nsew")
            self._tab_lis_btn.configure(fg_color=ACCENT, text_color="#ffffff")
        else:
            self._vps_frame.grid(row=1, column=0, sticky="nsew")
            self._tab_vps_btn.configure(fg_color=ACCENT, text_color="#ffffff")

    def _copy(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._status.configure(text="已复制到剪贴板")
        self.root.after(2000, lambda: self._status.configure(text="就绪"))

    def _render_message(self, parent, text, color="#aeaeb2"):
        ctk.CTkLabel(parent, text=text, font=FONT_S, text_color=color).pack(pady=30)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = RevShellGUI()
    app.run()
