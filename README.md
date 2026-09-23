# zeroxf 工具箱 · AI 版

**一个既给人用、也给 AI 用的渗透测试工具箱**——65 个工具，统一的图形界面、命令行与 MCP 接口，三套入口共用同一份工具注册表。

[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20WSL%2FLinux-blue)](#安装)
[![Tools](https://img.shields.io/badge/tools-65%20(%E5%85%B6%E4%B8%AD59%E4%B8%AAAI%E5%8F%AF%E8%B0%83)-brightgreen)](#集成的工具)
[![License](https://img.shields.io/badge/license-GPL--3.0-orange)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-ready-purple)](#mcp-ai-调用)

![zeroxf 工具箱](docs/poster.png)

### 界面预览

两端界面完全一致（同一份代码 + 同一份工具注册表）：

| WSL / Linux | Windows |
| --- | --- |
| ![WSL 端界面](docs/screenshots/wsl-main.png) | ![Windows 端界面](docs/screenshots/windows-main.png) |

---

## 这是什么

以 **天狐工具箱 V4.0**（[`wr0ld/tianhu-toolbox-v4`](https://github.com/wr0ld/tianhu-toolbox-v4)）为框架底座做的二开，在原版的图形界面之外，补上了 **命令行（geshell）** 与 **MCP** 两套程序化入口，让同一批工具既能人工点击操作，也能被脚本和 AI 直接调用。

架构与接口设计参考了枷锁工具箱（GetShell）的 `ai/launch.py`。

| 入口 | 文件 | 面向 |
| --- | --- | --- |
| 🖥 **图形界面** | `main.py` / `launcher.py` | 人工操作，卡片式工具墙 |
| ⌨️ **命令行** | `geshell` / `geshell.cmd` | 脚本、批处理、终端快手 |
| 🤖 **MCP** | `ai/mcp_server.py` | AI Agent 以工具形式调用 |

**单一数据源**：三者共用 `config/tools.json`。新增一个工具、改一次路径，三个入口同时生效。

---

## 亮点

- **65 个工具开箱可用**，横跨信息收集到后渗透的完整链路；其中 **59 个可被 AI 直接调用**
- **三套入口，一份配置** —— GUI 里能点的，CLI 和 MCP 里都能调，不会出现"界面有、命令行没有"的割裂
- **依赖自动装配** —— `provision_tools.py` 一条命令拉齐全部工具二进制、便携 JDK、GUI 运行时，自动适配 Windows / Linux / macOS
- **零环境依赖的 JDK 方案** —— 内置便携 JDK 8/11/17（8 与 11 为 Liberica full 版，内含 JavaFX），12 个 jar 类工具无需系统装 Java
- **跨平台一致** —— 同一套脚本在 WSL 与 Windows 原生均可用，按平台自动选择资产（`.exe` / ELF）
- **URL 都能救回来** —— 对已停止公开分发的工具（如 xray）也留有可用来源；对无源工具提供功能等价替代
- **容错安装** —— 单个工具失败不会中断整批，最后统一汇报
- **AI 友好** —— 工具元数据带 `risk` / `ai_callable` / `example` 字段，AI 能自行判断哪些该调、怎么调

---

## 集成的工具

**共 65 个**（59 个 AI 可直接调用），按 9 大类组织：

| 分类 | 数量 | 代表工具 |
| --- | ---: | --- |
| 信息收集 | 12 | `nmap` `httpx` `nuclei` `ffuf` `subfinder` `naabu` `katana` `dnsx` `uncover` `gobuster` `urlfinder` `dirsearch` |
| 漏洞扫描与利用 | 8 | `nuclei` `sqlmap` `xray` `dalfox` `zap` `exploitdb` `ssti` `docem` |
| 框架漏洞利用 | 11 | `shiro` `struts2` `weblogic` `fastjson`→`jndi` `log4j`→`jndi` `thinkphp` `spring` `tomcat` `dedecmscan` `redis` `nacos` |
| 重点系统漏洞 | 8 | `heapdump` `ruoyi` `nacos` `jenkins` `xxl-job` `jeecg` `iwannagetall` `hyacinth` |
| 内网渗透 | 4 | `fscan` `yasso` `netexec` `impacket` |
| 爆破 | 2 | `hydra` `hashcat` |
| 隧道代理 | 3 | `frps` `frpc` `chisel` |
| 后渗透 | 5 | `metasploit` `sliver` `cobaltstrike` `avoidkilling` `revshell` |
| 数据库利用 | 6 | `mysql` `mssql` `mongodb` `oracle` `usql` `dbcombo` |
| WebShell 管理 | 4 | **`webshell`**（CLI，AI 可调）`蚁剑` `godzilla` `behinder` |
| 抓包与代理 | 1 | `BurpSuite` |

**能力覆盖**：被动信息收集 → 主动漏洞扫描 → 框架专项利用 → 内网横向 → 权限维持 → 数据提取，一条完整链路。

> 完整清单与调用方式见 [`ai/tools.md`](ai/tools.md)（`geshell gendocs` 自动生成）。

### 关于不可得的工具

以下工具因授权、分发或来源原因无法自动获取，工具箱提供了**功能等价的替代**或说明：

| 工具 | 情况 | 处理 |
| --- | --- | --- |
| `fastjson` `log4j` | 专用利用 jar 无公开源 | 由 **JNDI-Injection-Exploit**（`jndi`）统一覆盖两者场景 |
| `CobaltStrike` `BurpSuite` `蚁剑` | 商业软件 / 需自备 | 保留条目，装入后即可用；`Sliver`（`sliver` 命令）与 `ZAP` 分别是 CS / Burp 的开源等价物 |

`geshell doctor` 会明确列出这些项，不会静默失败。

### WebShell 管理：三种 GUI 工具的协议，收进一个 CLI

蚁剑 / 冰蝎 / 哥斯拉都是图形化程序，AI 驱动不了它们——但这不等于 AI 用不了它们的
能力。「WebShell 管理」的本质就是**按约定协议发 HTTP 请求**，而这三家协议都是公开
可实现的。`webshell` 工具实现的正是协议本身：

```bash
# 自动识别是哪种马（哥斯拉型需要 --key）
geshell webshell -u http://target/shell.php -p pass -t auto -c "id"

geshell webshell -u ... -p pass -t godzilla --key <16字节密钥> --info
geshell webshell -u ... -p pass -t behinder  --upload ./x.php:/var/www/x.php
geshell webshell -u ... -p pass -t antsword --download /etc/passwd:./passwd.txt
```

这与 Burp 走官方 MCP 是同一个思路：**绕开 GUI，直接接协议**。

| 协议 | 命令执行 | 信息探测 | 上传 / 下载 | 备注 |
| --- | :---: | :---: | :---: | --- |
| 哥斯拉 phpXor | ✅ | ✅ | ✅ 原生 | 需要生成 shell 时的 16 字节密钥 |
| 冰蝎 v4 | ✅ | ✅ | ⚠️ 走命令通道 | 见下方 PHP 8 说明 |
| 蚁剑 | ✅ | ✅ | ⚠️ 走命令通道 | 命令通道依赖目标机有 `base64` |

> **冰蝎在 PHP 8 上的坑**：它的载荷外壳写作 `assert|eval(...)`，靠的是 PHP 8 之前
> 「未定义常量当字符串用」的老行为。**PHP 8 起这是致命错误**，症状是响应完全空白、
> 握手静默失败——没有任何报错，最难查的那种。
> 补丁可以打在服务端 shell 里，但真实场景连的是**别人已经上传好的马，改不了目标**。
> `webshell` 因此走客户端降级：标准外壳连不上就换 `define("assert",0);` 前缀重试，
> **目标一个字节都不用动**。

### jar 类工具为什么走 Release 而不是 git

14 个 Java 利用/管理工具（`shiro` `struts2` `weblogic` `thinkphp` `nacos` `jenkins`
`xxl-job` `jeecg` `dbcombo` `iwannagetall` `hyacinth` `godzilla` `behinder` `heapdump`）
的 jar 是第三方作者作品，**没有公开下载源**，脚本无法逐个从上游拉取。

它们合计 **632 MB**，其中 `weblogic`(130 MB)、`iwannagetall`(180 MB)、`behinder`(126 MB)
单个就超过 **GitHub 单文件 100 MB 的硬限制**——直接 `git add` 会被服务器拒收。因此统一
打包成 Release 资产：

```bash
python3 scripts/provision_tools.py --jars     # 下载 584 MB 并还原
```

脚本只解缺失的 jar（已存在的跳过），包内路径做目录穿越校验；下载走断点续传，
缓存留在 `.buildtools/`。手动安装就直接下该 Release 资产、把里面的 `tools/`
覆盖到仓库根目录（`MANIFEST.txt` 列了各 jar 的 sha256）。

### Burp Suite：一键接入 MCP

Burp 是 **PortSwigger 的商业软件**，二进制不适合随仓库分发（体积 + 授权），**需要你自行准备**。工具箱提供 `scripts/setup_burp.py` 自动完成「发现 + 接线」。

**为什么值得单独说**：PortSwigger 官方发布了 **MCP 扩展**（[`PortSwigger/mcp-server`](https://github.com/PortSwigger/mcp-server)），装好后 AI 可以直接发 HTTP 请求、读 proxy history、把请求塞进 Repeater/Intruder、调用 Scanner 与 Collaborator。

**三个前提**：

| # | 前提 | 说明 |
| --- | --- | --- |
| 1 | 自备 Burp | **需要 Professional** —— 社区版会提示 `AI features are Burp Suite Professional only`，MCP 服务无法启用 |
| 2 | 启用 MCP 扩展 | Burp → 扩展 → BApp商店 → 搜 `MCP Server` → 安装 → **MCP 标签打开 Enabled** |
| 3 | Java 21+ | Burp 2026.x 要求。⚠️ 系统里只装了 JDK 8 会导致**双击启动脚本毫无反应** |

**一条命令配置**：

```bash
python3 scripts/setup_burp.py
```

脚本流程：探测 Burp 位置 → 定位 proxy jar → 检查 Java 版本 → 修正绿色版启动脚本 → 写入 `~/.claude.json` 的 MCP 配置 → 实连验证（报告拿到多少工具）。

**两端通用**，脚本自动识别环境：

| 环境 | 做法 |
| --- | --- |
| Windows | 直接连 `127.0.0.1:9876` |
| WSL | 用 **Windows 的 `java.exe`** 跑 proxy（进程落在 Windows 侧），从而绕过 Burp 的 Host 校验 |

**三个已踩过的坑**（脚本已自动处理，手动配置时注意）：

1. **JDK 版本** —— 绿色版的 `.bat` 调用裸命令 `javaw.exe`，若系统 PATH 里是 JDK 8，Burp 起不来或闪退。脚本会注入正确的 `JAVA_HOME`/`PATH`。
2. **Host 校验** —— Burp 的 MCP 只接受 `Host: 127.0.0.1:9876`；从 WSL 直连、或用 `netsh portproxy` 转发（Host 会变成网关 IP）都会被 **403** 挡掉。用 Windows 侧的 java 跑 proxy 是唯一干净解法。
3. **社区版限制** —— 见上表第 1 条。`Enabled` 开关能打开，但服务实际不启动、右下角仍显示 `Disabled`。

**手动配置**（不想用脚本时）：

```json
{
  "mcpServers": {
    "burp": {
      "command": "/mnt/c/Program Files/Java/jdk-21/bin/java.exe",
      "args": ["-jar", "C:\\Users\\<你的用户名>\\AppData\\Roaming\\BurpSuite\\mcp-proxy\\mcp-proxy-all.jar",
               "--sse-url", "http://127.0.0.1:9876"]
    }
  }
}
```

> 配置是**启动时加载**的，改完需重启 Claude Code。使用前记得**先启动 Burp**（proxy 只是转发，后端必须是运行中的 Burp）。

### 两端的能力差异

工具箱**本体**（provision 能自动装的部分）在 WSL 与 Windows 上完全一致——
同一份代码、同一份 `config/tools.json`、同一套工具。差异只来自**系统级软件**
和第三方分发策略：

| 项目 | WSL / Linux | Windows |
| --- | --- | --- |
| 开源工具二进制 | ✅ 自动 | ✅ 自动 |
| 便携 JDK | ✅ 8 / 11 / 17 | ✅ 8 / 11 |
| GUI 运行时（PyQt6） | ✅ 自动 | ✅ 自动 |
| `nmap` `mysql` | `apt install` 即可 | `python scripts/provision_tools.py --win-deps`（winget 自动装）|
| **`hydra`** | ✅ `apt install hydra` | ❌ **装不了 —— Windows 无官方版本** |
| `metasploit` | 官方 installer | ✅ 手动装（官方 MSI 的静默安装实测不生效，见下方说明）|
| `oracle`（sqlplus） | ✅ 自动（Linux 版有免登录直链） | ⚠️ 需 Oracle 账号（官方只对登录用户提供 Windows 包）|
| **`oracle-py`** | ✅ 自动 | ✅ 自动 —— **Windows 端的 Oracle 替代** |

> **`oracle-py`**：Oracle 官方不提供 Windows 版 Instant Client 的免登录下载，但他们的
> Python 驱动 **`python-oracledb` 的 thin 模式是纯 Python 实现**，不需要任何 Oracle
> 客户端库就能连库。因此 Windows 端也有完整的 Oracle 连接能力。
> 装它：`python scripts/provision_tools.py --oracledb`；用法：
> ```bash
> geshell oracle-py scott/tiger@10.0.0.5:1521/orcl -e "select * from users"
> ```

> **`hydra` 的特别说明**：它**只有类 Unix 版本**，官方从未发布 Windows 构建。
> winget 源里搜到的 `HydraLauncher.Hydra` 是**游戏启动器**，与渗透工具无关。
> 因此本工具箱**只在 Linux/WSL 侧配置 hydra**，Windows 端不提供，`doctor` 会如实报缺失。
> Windows 上需要爆破能力时，可用 **nmap 的 NSE brute 脚本**覆盖：
> ```bash
> nmap -p22 --script ssh-brute --script-args userdb=u.txt,passdb=p.txt TARGET
> ```

> **`metasploit` 与 `mysql` 的 Windows 安装**：两者都要**刷新 PATH 才生效**。
> winget 装的 MySQL 不会自己建 shim，Metasploit 的 MSI 静默安装实测多次失败
> （`1603`），手动双击装到 `D:\metasploit-framework` 即可用。
> 装完记得把各自的 `bin` 目录加进 PATH——**已经打开的终端不会自动看到新 PATH**，
> 必须重开一个窗口，否则 `geshell doctor` 仍会报缺失。

实测就绪数（用各自平台真实的 PATH 量，不从 WSL 侧跨环境做数）：

| 平台 | 就绪 | 缺失 |
| --- | --- | --- |
| **WSL / Linux** | **56/58** | `fastjson` `log4j` |
| **Windows** | **54/58** | `fastjson` `log4j` `hydra` `oracle` |

差异只有两条：`hydra`（Windows 无官方版本）、`oracle`（需 Oracle 账号，
Windows 端用 `oracle-py` 替代）。`geshell doctor` 会把缺的逐条列出并说明原因。

> ⚠️ 从 WSL 里调用 Windows 的 python 做检查会得到偏低的数字——那个进程继承的是
> WSL 侧的 PATH 快照，看不到 Windows 后来加的 PATH。要在 Windows 上量，
> 就在 Windows 的终端里跑，或显式用注册表里的 PATH。

---

## 安装

### 先搞清楚：65 个工具分别从哪来

工具箱的获取方式**不是一种而是四种**，因为它们性质不同：

| # | 来源 | 数量 | 装法 |
| --- | ---: | ---: | --- |
| a | **随 git 分发** | 12 | clone 即有，无需操作 |
| b | **provision 自动下载** | 32 | `python3 scripts/provision_tools.py` |
| c | **Release 资产** | 14 | `python3 scripts/provision_tools.py --jars` |
| d | **需自备 / 无公开源** | 7 | 见下方说明，`doctor` 会如实报缺失 |

<details>
<summary>展开看每一类具体是哪些</summary>

- **a. 随 git 分发（11）** —— 天狐原创的 Python 脚本与手写 CLI，没有任何下载源，
  只能入库：`ssti` `spring` `tomcat` `dedecmscan` `redis` `ruoyi` `avoidkilling`
  `docem` `dirsearch` `revshell` `oracle-py`
  > ⚠️ 这几个目录在 `.gitignore` 里是 `tools/*` 的**例外**。改 gitignore 时别把它们
  > 一起挡掉——否则 clone 下来界面有卡片、一点就报路径不存在。
- **b. provision 自动下载（32）** —— 有官方 release 的开源工具（`nuclei` `httpx`
  `ffuf` `fscan` … `zap` `impacket` `sqlmap`）。按平台自动选资产：Windows 拿 `.exe`，
  Linux 拿 ELF。
- **c. Release 资产（14）** —— 第三方 Java 利用/管理工具的 jar，无公开源且体积大
  （3 个超 GitHub 100 MB 限制），打成 `zeroxf-jar-tools-v1.tar.gz` 随 Release 分发。
- **d. 需自备（7）** —— `CobaltStrike` `BurpSuite` `蚁剑`（商业/需自备）、
  `fastjson` `log4j`（专用 jar 无公开源，功能由 `jndi` 覆盖）、`hydra`（仅 Linux）。

</details>

### 方式一：一键初始化（推荐）

clone 之后，仓库里**只有代码**——工具二进制、JDK、GUI 运行时都不入库，需要按需拉取：

```bash
git clone https://github.com/qwq-nm/zeroxf_tools.git
cd zeroxf_tools

python3 scripts/provision_tools.py --jdk    # 便携 JDK 8/11/17（14 个 jar 类工具需要）
python3 scripts/provision_tools.py          # 全部工具二进制 + jar 包
python3 scripts/provision_tools.py --gui    # GUI 运行时 PyQt6（用图形界面才装）
python3 scripts/provision_tools.py --webshell-deps  # webshell 工具依赖（全量安装已含）

# 仅 Windows：补装系统级工具（nmap / MySQL 客户端 / Metasploit）
python scripts/provision_tools.py --win-deps
```

> **jar 包单独装**：不带 `--tools` 的全量安装会顺带还原 14 个 jar 类工具
> （从本仓库 Release 下载 584 MB）。想跳过就用 `--tools` 指定具体工具，
> 或事后单独跑 `python3 scripts/provision_tools.py --jars`。

Windows 下把 `python3` 换成 `python`。脚本会自动识别平台，拉取对应版本（Windows 拿 `.exe`，Linux 拿 ELF）。

`--win-deps` 用 **winget**（Windows 10 1809+ 自带，无需另装包管理器）安装 nmap 与 MySQL 客户端，
并用 Rapid7 官方 MSI 静默安装 Metasploit。

### 方式二：手动安装（逐个控制）

```bash
python3 scripts/provision_tools.py --tools nuclei httpx ffuf     # 只装指定工具
python3 scripts/provision_tools.py --tools zap usql oracle xray  # 专用工具
python3 scripts/provision_tools.py --help                        # 查看全部参数
```

> 详尽的安装说明、系统依赖、故障排查见 **[docs/INSTALL.md](docs/INSTALL.md)**。

### 方式三：交给 AI Agent

如果你在用 Claude Code / 其他 AI 编码助手，把 **[docs/AGENT.md](docs/AGENT.md)** 的内容发给它，它能自行完成环境探测、依赖安装与验证。

---

## 使用

### 图形界面

| 平台 | 启动方式 |
| --- | --- |
| Windows | 双击 `启动工具箱.bat`（或 `启动工具箱-无窗口.vbs` 静默启动） |
| WSL / Linux | `tools/_venv/bin/python main.py` |

界面会按分类展示全部工具卡片，点击即调用，支持搜索、收藏、最近启动。

### 命令行

```bash
./geshell list                        # 按分类列出全部工具
./geshell info nmap                   # 查看单个工具详情与调用方式
./geshell nmap -sV -p- target.com     # 直接调用
./geshell doctor                      # 环境自检
./geshell selftest                    # 回归测试
```

命令名匹配**忽略大小写、空格、横线和下划线**，并支持中文拼音：

```bash
./geshell 若依          # = ./geshell ruoyi
./geshell URL-FINDER    # = ./geshell urlfinder
```

### MCP（AI 调用）

`ai/mcp_server.py` 是一个 stdio JSON-RPC MCP server，把 59 个可调用工具暴露为 `tool_<名称>`：

在 `~/.claude.json` 的 `mcpServers` 段加入：

```json
{
  "mcpServers": {
    "zeroxf-geshell": {
      "command": "python3",
      "args": ["/path/to/zeroxf_tools/ai/mcp_server.py"],
      "description": "zeroxf 工具箱：AI 可调用全部渗透工具"
    }
  }
}
```

之后 AI 就能以 `tool_nmap`、`tool_nuclei`、`tool_sqlmap` 等形式直接调用。

---

## 文档

| 文档 | 内容 |
| --- | --- |
| [docs/INSTALL.md](docs/INSTALL.md) | 完整安装指南：环境要求、分步安装、系统依赖、故障排查 |
| [docs/AGENT.md](docs/AGENT.md) | 给 AI Agent 的安装与验证指令（可直接粘贴给 AI） |
| [ai/tools.md](ai/tools.md) | 全部工具的参数、示例与调用方式（自动生成） |
| `geshell doctor` | 运行时环境自检，定位缺失依赖 |

---

## 常见问题

**Q：双击 `.bat` 没任何反应？**
仓库里的 `.bat` / `.cmd` 已通过 `.gitattributes` 固定为 CRLF 换行 + GBK 编码（Windows 中文环境的原生格式）。如果你手动编辑过这些文件，注意别让编辑器把它存成 LF 或 UTF-8——那会让 CMD 解析错乱、脚本静默不执行。

**Q：从 `\\wsl.localhost\...` 双击启动失败？**
Windows 的 CMD 不支持 UNC 路径作为工作目录。启动脚本已用 `pushd` 规避，但更推荐把工具箱放在 Windows 本地磁盘。

**Q：GUI 里点工具闪一下就没了？**
先跑 `geshell doctor` 看依赖。若在 WSL 下且是 JavaFX 类工具（哥斯拉、冰蝎、shiro 等），工具箱已自动注入 `GDK_BACKEND=x11`——WSLg 同时提供 Wayland 与 XWayland，不强制 X11 会段错误。

**Q：`git clone` 下来界面里一个工具都没有？**
`config/tools.json` 是必须分发的内容（已纳入版本控制）。若缺失，说明用了旧版本，`git pull` 即可。

**Q：某些工具装不上？**
看 `provision_tools.py` 的输出。它对单个工具的失败做了隔离，不会中断整批；失败项会明确打印原因。

---

## 授权与合规

本项目基于 [wr0ld/tianhu-toolbox-v4](https://github.com/wr0ld/tianhu-toolbox-v4)（GPL-3.0）二开，遵循 GPL-3.0 发布，原项目版权归原作者所有。

> ⚠️ **仅限在明确授权的资产和测试范围内使用。** 未授权扫描、爆破、利用或访问他人系统违法。使用者需自行承担合规责任。

CLI 架构参考 [One-JiaSuo/Jiasuo-tools](https://github.com/One-JiaSuo/Jiasuo-tools)。
