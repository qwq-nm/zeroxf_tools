import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import customtkinter as ctk

from revshell_templates import ALL_LANG_LIST, COMMON_LANG_LIST, ENCODE_LIST, PAYLOADS, PRESET_LIST, PRESET_VALUES, variant_label
from revshell_theme import ACCENT, ACCENT_LIGHT, BG_CARD, BG_HOVER, BG_INPUT, FONT, FONT_S, FONT_SEC, MONO, MONO_S, R, R_CARD, RED, TEXT, TEXT_SEC, TEXT_TER
from revshell_utils import encode_command, normalize_port


class GeneratorPanel:
    def build_generator(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        opts = ctk.CTkFrame(parent, corner_radius=R_CARD, fg_color=BG_CARD, border_width=0)
        opts.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        opts.grid_columnconfigure(4, weight=1)

        ctk.CTkLabel(opts, text="预设", font=FONT_S, text_color=TEXT_SEC).grid(row=0, column=0, padx=(16, 4), pady=10)
        self._preset_var = ctk.StringVar(value="自定义")
        self._preset_menu = ctk.CTkOptionMenu(
            opts, values=PRESET_LIST, variable=self._preset_var, command=self._apply_preset,
            width=120, height=30, font=FONT, corner_radius=8, fg_color=BG_INPUT,
            button_color=TEXT_TER, button_hover_color=TEXT_SEC, text_color=TEXT,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT,
        )
        self._preset_menu.grid(row=0, column=1, padx=(0, 20), pady=10)

        ctk.CTkLabel(opts, text="模板", font=FONT_S, text_color=TEXT_SEC).grid(row=0, column=2, padx=(0, 4), pady=10)
        self._lang_mode_var = ctk.StringVar(value="常用")
        ctk.CTkSegmentedButton(
            opts, values=["常用", "全部"], variable=self._lang_mode_var,
            command=lambda _: self._refresh_lang_menu(), font=FONT_S, corner_radius=8,
            selected_color=ACCENT, selected_hover_color=ACCENT,
            unselected_color=BG_INPUT, unselected_hover_color=BG_HOVER, text_color=TEXT,
            width=132,
        ).grid(row=0, column=3, padx=(0, 16), pady=10)

        ctk.CTkLabel(opts, text="语言", font=FONT_S, text_color=TEXT_SEC).grid(row=0, column=4, padx=(0, 4), pady=10)
        self._lang_var = ctk.StringVar(value=COMMON_LANG_LIST[0])
        self._lang_menu = ctk.CTkOptionMenu(
            opts, values=COMMON_LANG_LIST, variable=self._lang_var, command=lambda _: self._generate(),
            width=120, height=30, font=FONT, corner_radius=8, fg_color=BG_INPUT,
            button_color=TEXT_TER, button_hover_color=TEXT_SEC, text_color=TEXT,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT,
        )
        self._lang_menu.grid(row=0, column=5, padx=(0, 20), pady=10)

        ctk.CTkLabel(opts, text="变体", font=FONT_S, text_color=TEXT_SEC).grid(row=0, column=6, padx=(0, 4), pady=10)
        self._variant_var = ctk.StringVar()
        self._variant_menu = ctk.CTkOptionMenu(
            opts, values=["默认"], variable=self._variant_var, command=lambda _: self._generate(),
            width=180, height=30, font=FONT_S, corner_radius=8, fg_color=BG_INPUT,
            button_color=TEXT_TER, button_hover_color=TEXT_SEC, text_color=TEXT,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT,
        )
        self._variant_menu.grid(row=0, column=7, sticky="w", padx=(0, 20), pady=10)

        ctk.CTkLabel(opts, text="编码", font=FONT_S, text_color=TEXT_SEC).grid(row=0, column=8, padx=(0, 4), pady=10)
        self._encode_var = ctk.StringVar(value=ENCODE_LIST[0])
        ctk.CTkOptionMenu(
            opts, values=ENCODE_LIST, variable=self._encode_var, command=lambda _: self._generate(),
            width=100, height=30, font=FONT_S, corner_radius=8, fg_color=BG_INPUT,
            button_color=TEXT_TER, button_hover_color=TEXT_SEC, text_color=TEXT,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT,
        ).grid(row=0, column=9, padx=(0, 16), pady=10)

        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.grid(row=1, column=0, sticky="w", pady=(0, 6))
        ctk.CTkLabel(hdr, text="生成的命令", font=FONT_SEC, text_color=TEXT).pack(side="left", padx=4)
        ctk.CTkLabel(hdr, text="（点击复制）", font=FONT_S, text_color=TEXT_TER).pack(side="left", padx=(4, 0))

        self._output_box = ctk.CTkScrollableFrame(
            parent, fg_color=BG_CARD, corner_radius=R_CARD,
            scrollbar_button_color=BG_INPUT, scrollbar_button_hover_color=TEXT_TER,
        )
        self._output_box.grid(row=2, column=0, sticky="nsew")
        self._output_box.grid_columnconfigure(0, weight=1)

        foot = ctk.CTkFrame(parent, fg_color="transparent")
        foot.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        foot.grid_columnconfigure(0, weight=1)

        self._cmd_count_lbl = ctk.CTkLabel(foot, text="", font=FONT_S, text_color=TEXT_TER, anchor="w")
        self._cmd_count_lbl.pack(side="left")

        ctk.CTkButton(
            foot, text="复制全部", width=100, height=30, font=FONT, corner_radius=R,
            fg_color=ACCENT, hover_color="#0066d6", text_color="#ffffff", command=self._copy_all,
        ).pack(side="right")

        self._update_variants()

    def _update_variants(self):
        lang = self._lang_var.get()
        variants = list(PAYLOADS.get(lang, {}).keys())
        if not variants:
            self._variant_menu.configure(values=["默认"])
            self._variant_var.set("默认")
            self._variant_keys = []
            return

        labels = [variant_label(v) for v in variants]
        self._variant_menu.configure(values=labels)
        self._variant_var.set(labels[0])
        self._variant_keys = variants

    def _available_langs(self):
        return COMMON_LANG_LIST if self._lang_mode_var.get() == "常用" else ALL_LANG_LIST

    def _refresh_lang_menu(self, trigger_generate=True):
        langs = self._available_langs()
        current = self._lang_var.get()
        self._lang_menu.configure(values=langs)
        if current not in langs:
            current = langs[0]
            self._lang_var.set(current)
        self._current_langs = langs
        self._update_variants()
        if trigger_generate:
            self._generate()

    def _apply_preset(self, preset_name):
        if preset_name == "自定义":
            self._generate()
            return

        values = PRESET_VALUES.get(preset_name, {})
        if "ip" in values:
            if values["ip"] == "AUTO":
                self._ip_var.set(self._auto_ip or "10.0.0.1")
            else:
                self._ip_var.set(values["ip"])
        if "port" in values:
            self._port_var.set(values["port"])
        if "lang" in values:
            self._lang_mode_var.set("常用" if values["lang"] in COMMON_LANG_LIST else "全部")
            self._refresh_lang_menu(trigger_generate=False)
            self._lang_var.set(values["lang"])
        if "variant" in values:
            self._variant_var.set(values["variant"])
        if "encode" in values:
            self._encode_var.set(values["encode"])
        if "listener_type" in values:
            self._lis_type_var.set(values["listener_type"])
        if "listener_port" in values:
            self._lis_port_var.set(values["listener_port"])
        if "vps_method" in values:
            self._vps_method_var.set(values["vps_method"])
        if "vps_port" in values:
            self._vps_port_var.set(values["vps_port"])
        if "local_port" in values:
            self._local_port_var.set(values["local_port"])
        self._generate()

    def _generate(self):
        ip = self._ip_var.get().strip() or "10.0.0.1"
        port = normalize_port(self._port_var.get(), "4444")
        lang = self._lang_var.get()
        encode = self._encode_var.get()

        if lang != self._last_lang:
            self._last_lang = lang
            self._update_variants()

        for w in self._output_box.winfo_children():
            w.destroy()

        if not port:
            self._render_message(self._output_box, "LPORT 必须是 1-65535 的数字端口", RED)
            self._cmd_count_lbl.configure(text="端口无效")
            return

        payloads = PAYLOADS.get(lang, {})
        if self._variant_keys:
            labels = [variant_label(v) for v in self._variant_keys]
            cur = self._variant_var.get()
            idx = labels.index(cur) if cur in labels else 0
            key = self._variant_keys[idx]
        elif payloads:
            key = list(payloads.keys())[0]
        else:
            return

        raw = payloads[key].format(ip=ip, port=port)
        result = encode_command(raw, encode)

        card = ctk.CTkFrame(self._output_box, corner_radius=10, fg_color=ACCENT_LIGHT, border_width=0)
        card.pack(fill="x", pady=4, padx=4)
        card.grid_columnconfigure(0, weight=1)

        tag = ctk.CTkFrame(card, fg_color="transparent")
        tag.grid(row=0, column=0, sticky="w", padx=14, pady=(10, 0))
        ctk.CTkLabel(tag, text=lang, font=("pingfang sc", 11, "bold"), text_color=ACCENT).pack(side="left")
        if encode != "无编码":
            ctk.CTkLabel(tag, text=f"  ·  {encode}", font=FONT_S, text_color=TEXT_SEC).pack(side="left")

        cmd_lbl = ctk.CTkLabel(
            card, text=result, font=MONO, text_color=TEXT, wraplength=700,
            justify="left", anchor="w", cursor="hand2",
        )
        cmd_lbl.grid(row=1, column=0, sticky="ew", padx=14, pady=(6, 4))

        bot = ctk.CTkFrame(card, fg_color="transparent")
        bot.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 10))
        ctk.CTkLabel(bot, text=f"{len(result)} chars", font=FONT_S, text_color=TEXT_TER).pack(side="left")
        ctk.CTkButton(
            bot, text="复制", width=56, height=24, font=FONT_S, corner_radius=6,
            fg_color=ACCENT, hover_color="#0066d6", text_color="#ffffff",
            command=lambda t=result: self._copy(t),
        ).pack(side="right")

        cmd_lbl.bind("<ButtonPress-1>", lambda e, t=result: self._copy(t))

        if not self._trace_bound:
            self._ip_var.trace_add("write", lambda *_: self._generate())
            self._port_var.trace_add("write", lambda *_: self._generate())
            self._trace_bound = True
        self._cmd_count_lbl.configure(text=f"{lang} / {self._variant_var.get()} / {len(result)} chars")

    def _copy_all(self):
        lang = self._lang_var.get()
        ip = self._ip_var.get().strip() or "10.0.0.1"
        port = normalize_port(self._port_var.get(), "4444")
        if not port:
            self._status.configure(text="端口无效")
            self.root.after(2000, lambda: self._status.configure(text="就绪"))
            return
        encode = self._encode_var.get()
        payloads = PAYLOADS.get(lang, {})
        lines = [encode_command(tmpl.format(ip=ip, port=port), encode) for key, tmpl in payloads.items()]
        text = "\n\n".join(lines)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._status.configure(text=f"已复制 {lang} 全部 {len(payloads)} 个 payload")
        self.root.after(2000, lambda: self._status.configure(text="就绪"))
