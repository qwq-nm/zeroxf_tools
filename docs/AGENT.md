# 给 AI Agent 的安装与验证指南

> **这份文档是写给 AI 编码助手的。** 用户把本文件（或它的链接
> `https://raw.githubusercontent.com/qwq-nm/zeroxf_tools/main/docs/AGENT.md`）
> 交给你时，意味着他希望你（而不是他）来完成 zeroxf 工具箱的环境搭建与验证。
>
> 请按顺序执行，每步都对照「成功判据」。遇到失败先查「失败处置」表，不要跳过。

---

## 0. 先探测环境（不要跳过）

```bash
# 平台与 Python
python3 -V || python -V
uname -a 2>/dev/null || ver        # Windows 用 ver

# 是否已 clone
ls config/tools.json 2>/dev/null && echo "代码就位" || echo "需要 clone"

# 已有的依赖情况
ls Java_path/ 2>/dev/null
ls tools/_venv/ 2>/dev/null
```

**关键判断**：
- Python ≥ 3.8？否则先装
- 是否在 WSL 里？（`uname -r` 含 `microsoft`）——影响后续 GUI 与路径处理
- 磁盘剩余 ≥ 5 GB？`df -h .`

---

## 1. 获取代码（若尚未 clone）

```bash
git clone https://github.com/qwq-nm/zeroxf_tools.git
cd zeroxf_tools
```

**成功判据**：`config/tools.json` 存在，且 `python3 -c "import json;print(len(json.load(open('config/tools.json'))))"` 输出 **57**。

> ⚠️ 若 `tools.json` 不存在或数量不对，说明 clone 到的是旧版本，执行 `git pull`。

---

## 2. 安装

依次执行（**每步都可能耗时数分钟**，属正常）：

```bash
python3 scripts/provision_tools.py --all      # 一条命令装完，约 4.9 G
```

`--all` = 便携 JDK + 全部工具（28 个二进制 + 13 个 jar）+ 运行时依赖 + GUI 运行时，
Windows 上另含系统级工具（nmap / MySQL / Metasploit）。
需要分开装时用 `--jdk` / `--gui` / `--jars` / `--webshell-deps` 单个开关。

> `--all` 里含从本仓库 **Release 资产**（tag `jar-tools-v1`）下载 584 MB 的
> `zeroxf-jar-tools-v1.tar.gz` 以还原 13 个 jar 类工具。这些 jar 是第三方作品、
> 无公开下载源，其中 3 个单个超 GitHub 100 MB 限制，所以只能走 Release。
> 想跳过就改用 `--tools <名称>` 逐个装，或事后单独跑 `--jars`。
> 下载失败不影响其余工具——脚本会报 `[失败] jars:` 后继续。

Windows 下将 `python3` 替换为 `python`。

**执行时的注意事项**：
1. **不要在执行期间频繁访问目标目录**（`ls`/`du`/`tail` 循环监控）。Windows 与 WSL 跨文件系统访问会对正在搬移的文件加锁，可能触发 `PermissionError: [WinError 5]`。让它跑完再看。
2. 脚本**对单个工具失败做了隔离**——某个工具失败不会中断整批。全部结束后再统一处理失败项。
3. 输出里的 `[重试]` 是断点续传的正常行为，不必惊慌。

**成功判据**：结尾出现 `[完成] 打包完成，当前平台: <平台>`。

---

## 3. 验证（逐项核对）

### 3.0 全量验证（推荐先跑这个）

```bash
python3 scripts/verify_all.py
```

一条命令跑完六组检查并给出汇总。**建议先跑它**——哪一项不对会直接指出来，
比逐条手工核对快得多，也不用担心漏项。

它会自己区分「预期内缺失」（授权/平台限制，记警告并说明原因）与「真异常」
（记失败）。`--quick` 跳过耗时项，`--offline` 不联网。

若本机没有 php，webshell 三协议回归会记为「跳过」——这是环境差异，不是异常。

### 3.1 环境自检

```bash
./geshell doctor
```

**期望**：
- `[ok] JDK 8:` 与 `[ok] JDK 11:` 各一行，且路径存在
- 剩余警告**仅限**这 3 个（属预期，不要试图修复）：
  `cobaltstrike4.9`、`BurpSuite`、`蚁剑` —— 都是商业软件或需自备
- **其他任何警告都算异常**，按「失败处置」处理

### 3.2 回归测试

```bash
./geshell selftest
```

**期望**：`Ran 11 tests ... OK`

### 3.3 工具清单

```bash
./geshell list
```

**期望**：列出 57 个工具，表尾汇总为 `✓ 就绪 51   ⚠ 已注册但文件缺失 0   ✗ 未注册 6`。

> 状态列是三态：`✓` 就绪可直接调用 / `⚠` 已注册但文件没装（要跑 provision）/
> `✗` 未注册为 AI 可调用。**只要 `⚠` 不是 0，就说明安装没跑完。**

### 3.4 抽样实调

```bash
./geshell nuclei -version        # 应输出版本号
./geshell httpx -version
./geshell nmap --version
./geshell dbx --list           # 应输出已配置的连接（或 "No connections configured"）
./geshell impacket --help
```

**期望**：每个都能输出正常内容，而非 `No such file` / `not found`。

### 3.5 MCP 接口（若用户需要 AI 调用）

```bash
printf '%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
 | python3 ai/mcp_server.py
```

**期望**：`initialize` 返回 `serverInfo.name == "tianhu-geshell"`；`tools/list` 返回 **51** 个工具。

### 3.6 Burp Suite MCP（可选，若用户要用 Burp）

Burp 是**商业软件，不在本仓库内**，需要用户自备。当用户提到 Burp、或要「用 Burp 抓包/扫描」时，按本节处理。

**先确认三件事**（缺一不可）：

| 检查 | 怎么查 | 不满足时 |
| --- | --- | --- |
| Burp **Professional** | 窗口标题是否有 `专业版` / `licensed to` | 社区版**不支持** AI 功能，直接告知用户，别浪费时间调配置 |
| MCP 扩展已启用 | Burp → **MCP** 标签 → `Enabled` 开关 | 让用户在 **扩展 → BApp商店** 搜 `MCP Server` 安装 |
| Java **21+** | `java -version` | 见下面「坑 1」 |

**一键配置**：

```bash
python3 scripts/setup_burp.py
```

脚本自动完成：探测 Burp → 定位 proxy jar → 检查 Java → 修正启动脚本 → 写 MCP 配置 → 实连验证。

**若脚本报「未找到 mcp-proxy-all.jar」**：它由 MCP 扩展在首次启动时释放。让用户**先启动一次 Burp**、在 MCP 标签点「解压服务器代理 jar」，再重跑脚本。

**三个坑**（脚本已自动处理，但排查时必须知道）：

1. **JDK 版本** —— 绿色版 Burp 的 `.bat` 调用**裸命令** `javaw.exe`。若系统 PATH 里是 JDK 8（很常见），现象是**双击毫无反应**——不是崩溃，是版本太低。脚本会往脚本头部注入 `JAVA_HOME`/`PATH` 指向 JDK 21。
2. **Host 校验** —— Burp 的 MCP **只接受 `Host: 127.0.0.1:9876`**。从 WSL 直连、或用 `netsh interface portproxy` 转发（Host 会变成网关 IP）**都会被 403 挡掉**。
   **唯一干净解法**：用 **Windows 侧的 `java.exe`** 跑 proxy —— 进程落在 Windows，Host 天然是 `127.0.0.1`，stdio 经 WSL interop 传回。脚本就是这么做的。
3. **社区版限制** —— `Enabled` 开关**能打开**，但右下角**仍显示 `Disabled`**，并弹提示 `AI features are Burp Suite Professional only`。这是授权限制，**不是配置问题，不要反复尝试**。

**验证**：

```bash
python3 scripts/setup_burp.py --verify-only
```

期望输出：`连通成功，Burp 暴露 N 个工具`（Pro 版约 27 个）。

**两个注意事项**：

- MCP 配置是 Claude Code **启动时加载**的，写入后**必须重启**才生效
- 使用期间 **Burp 必须保持运行**（proxy 只是转发，后端是 Burp）

### 3.7 图形界面（若用户需要 GUI）

```bash
# Linux / WSL
tools/_venv/bin/python main.py
# Windows：双击 启动工具箱.bat
```

**期望**：窗口标题为 `zeroxf 工具箱 V4.0`，尺寸约 1400×800，左侧 11 个分类、主区卡片网格。

---

## 4. 失败处置

| 现象 | 原因 | 处置 |
| --- | --- | --- |
| `FileNotFoundError: config/tools.json` | clone 的是不含该文件的旧版本 | `git pull` |
| `PermissionError [WinError 5]` 移动文件时 | 跨文件系统（WSL↔Windows）文件锁冲突 | 停止一切对目标目录的访问，重跑该工具 |
| `gzip.BadGzipFile: Not a gzipped file (b'PK')` | 拿 gzip 解了 ZIP（旧版脚本的格式判断缺陷） | 确认 `_detect_extract` 函数存在；否则 `git pull` |
| `UnsupportedCompressionMethodError: BCJ2` | hashcat 的 7z 用了 py7zr 不支持的过滤器 | 确认 `.buildtools/7zr.exe`(Win) 或 `7zz`(Linux) 存在；否则手动下载 [7zr.exe](https://www.7-zip.org/a/7zr.exe) 放入 |
| `HTTP Error 416` | 断点续传越界 | 脚本会自动清除残留重下，重跑即可 |
| `[失败] jars: HTTP Error 404` | Release 资产 `jar-tools-v1` 不存在（仓库被 fork 后 Release 不跟随，或资产被删） | 从上游 [qwq-nm/zeroxf_tools](https://github.com/qwq-nm/zeroxf_tools/releases) 手动下载 `zeroxf-jar-tools-v1.tar.gz`，解包把 `tools/` 覆盖到仓库根目录 |
| 13 个 jar 工具（shiro/weblogic/哥斯拉…）报路径不存在 | 没跑 `--jars`，或跑了但 Release 拉取失败 | `python3 scripts/provision_tools.py --jars`，见上一行 |
| `NoClassDefFoundError: javafx/...` | JDK 不是 full 版 | `python3 scripts/provision_tools.py --jdk --force` |
| Java 工具段错误 / 闪退（WSL） | WSLg 的 Wayland/XWayland 双栈 | 运行前 `export GDK_BACKEND=x11`（工具箱已自动注入） |
| `netexec` 安装失败 | 其 `aardwolf` 依赖需 Rust 编译，或源码拉取超时 | 装 Rust 后重试，见下方补充说明 |
| `oracle` 报缺 `libaio.so.1` | 系统库缺失 | `apt install libaio1t64` + 建软链 `ln -sf /usr/lib/x86_64-linux-gnu/libaio.so.1t64 /usr/lib/x86_64-linux-gnu/libaio.so.1` |
| 双击 `.bat` 无反应 | 文件被存成 LF 换行或 UTF-8 | 恢复为 CRLF + GBK：`git checkout -- 启动工具箱.bat` |
| Burp 双击**毫无反应**（非崩溃） | PATH 里是旧 JDK（如 8），而 Burp 2026.x 需要 **21+** | `python3 scripts/setup_burp.py`（自动注入正确 JDK）|
| Burp MCP 连接返回 **403** | Host 校验：只接受 `Host: 127.0.0.1:9876` | 用 Windows 侧 java 跑 proxy，见 §3.6 |
| Burp MCP 的 `Enabled` 打开后仍显示 **Disabled** | 社区版不支持 AI 功能（授权限制）| 需 Professional 版，见 §3.6——不要再尝试调配置 |
| `hydra` 字段在 Windows 上显示为 nxc | hydra 本体无 Windows 版，`hydra` 条目指向的 `tools/brute/` 调度器**自动落到 netexec**——这是设计行为，不是故障 | 无需处置。用 `--backend` 可强制指定，`--show` 看实际命令 |
| `tools/webshell/behinder_php.py` **反复消失**，`git status` 显示 `D`；用到冰蝎协议时报 `OSError` / `EBADF` | **杀软按访问扫描把该文件隔离了**（火绒等）。它含冰蝎的 AES 与载荷特征串，易被判为 hacktool。特征是：`git checkout` 恢复后文件在、`stat` 也在，**一旦被 Python 读取就报错，随后文件从磁盘消失** | 提示用户把工具箱目录加进杀软**信任区**，然后 `git checkout -- tools/webshell/behinder_php.py` 恢复。⚠️ **不要试图绕过杀软**（编码混淆、改名、还原隔离区都不行）——那是用户机器上的安全控制，加不加白名单由用户决定。用户不加就如实说明：Windows 端只有哥斯拉、蚁剑两条线，冰蝎用 WSL 侧 |

> `netexec` 的补充：它是 PyPI 上无发行包的包，需从 GitHub 装，且其构建依赖 `poetry-dynamic-versioning` 会读取 git 元数据——用源码 tarball 安装时需绕过：`POETRY_DYNAMIC_VERSIONING_BYPASS=0.0.0 pip install <tarball>`。

---

## 5. 完成后向用户汇报什么

用**结构化**的方式汇报，至少包含：

1. **平台信息** —— 在哪装的（WSL / Windows / 双端）、Python 版本
2. **工具就绪数** —— 两端现在都是 `51/51`。若你的数量更少，逐条看 `doctor` 报的原因，别照抄旧文档里的「预期缺失」
3. **仍缺失的项及原因** —— 明确区分「不可得」（商业软件 / 无公开源）与「安装失败」。
   几个**预期内、不要试图修复**的缺失：
   - `CobaltStrike` / `BurpSuite` / `蚁剑`：商业或需自备（Burp 见 §3.6）

   以下几项**已经不再是缺失项**，别再当预期缺失报给用户：
   - `hydra`（Windows）：该条目指向 `tools/brute/` 调度器，Windows 自动落到 netexec
   - `oracle`（Windows）：Oracle CDN 的版本化直链是公开的，`--tools oracle` 可自动装
4. **验证结果** —— `doctor` / `selftest` / MCP / GUI 各自的结论
5. **使用入口** —— 告诉用户怎么启动（GUI 双击什么、CLI 敲什么、MCP 怎么注册）

**不要**把「预期内的警告」说成失败（见 3.1 的那 5 个）；**也不要**把「安装脚本跳过」说成成功。

---

## 附：关键路径速查

| 用途 | 路径 |
| --- | --- |
| 工具注册表（唯一数据源） | `config/tools.json` |
| 工具二进制 | `tools/<名称>/` |
| 便携 JDK | `Java_path/Java_{8,11,17}_win/` |
| GUI 运行时 venv | `tools/_venv/` |
| CLI 入口 | `./geshell`（Linux）/ `geshell.cmd`（Windows） |
| MCP server | `ai/mcp_server.py` |
| AI 参考手册 | `ai/tools.md`（`geshell gendocs` 重新生成） |
| 运行日志 | `output/runs/<时间戳>_<工具名>/` |
