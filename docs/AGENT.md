# 给 AI Agent 的安装与验证指南

> **这份文档是写给 AI 编码助手的。** 用户把本文件交给你时，意味着他希望你（而不是他）来完成 zeroxf 工具箱的环境搭建与验证。
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

**成功判据**：`config/tools.json` 存在，且 `python3 -c "import json;print(len(json.load(open('config/tools.json'))))"` 输出 **63**。

> ⚠️ 若 `tools.json` 不存在或数量不对，说明 clone 到的是旧版本，执行 `git pull`。

---

## 2. 安装

依次执行（**每步都可能耗时数分钟**，属正常）：

```bash
python3 scripts/provision_tools.py --jdk      # 便携 JDK 8/11/17，约 1.3 G
python3 scripts/provision_tools.py            # 工具二进制，约 3.5 G
python3 scripts/provision_tools.py --gui      # GUI 运行时 PyQt6，约 90 M（仅需 GUI 时）
```

Windows 下将 `python3` 替换为 `python`。

**执行时的注意事项**：
1. **不要在执行期间频繁访问目标目录**（`ls`/`du`/`tail` 循环监控）。Windows 与 WSL 跨文件系统访问会对正在搬移的文件加锁，可能触发 `PermissionError: [WinError 5]`。让它跑完再看。
2. 脚本**对单个工具失败做了隔离**——某个工具失败不会中断整批。全部结束后再统一处理失败项。
3. 输出里的 `[重试]` 是断点续传的正常行为，不必惊慌。

**成功判据**：结尾出现 `[完成] 打包完成，当前平台: <平台>`。

---

## 3. 验证（逐项核对）

### 3.1 环境自检

```bash
./geshell doctor
```

**期望**：
- `[ok] JDK 8:` 与 `[ok] JDK 11:` 各一行，且路径存在
- 剩余警告**仅限**这 5 个（属预期，不要试图修复）：
  `cobaltstrike4.9`、`BurpSuite`、`蚁剑`、`fastjson`、`log4j`
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

**期望**：列出 63 个工具，其中 56 个标 `✓`（AI 可调用）。

### 3.4 抽样实调

```bash
./geshell nuclei -version        # 应输出版本号
./geshell httpx -version
./geshell nmap --version
./geshell usql --version
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

**期望**：`initialize` 返回 `serverInfo.name == "tianhu-geshell"`；`tools/list` 返回 **56** 个工具。

### 3.6 图形界面（若用户需要 GUI）

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
| `NoClassDefFoundError: javafx/...` | JDK 不是 full 版 | `python3 scripts/provision_tools.py --jdk --force` |
| Java 工具段错误 / 闪退（WSL） | WSLg 的 Wayland/XWayland 双栈 | 运行前 `export GDK_BACKEND=x11`（工具箱已自动注入） |
| `netexec` 安装失败 | 其 `aardwolf` 依赖需 Rust 编译，或源码拉取超时 | 装 Rust 后重试，见下方补充说明 |
| `oracle` 报缺 `libaio.so.1` | 系统库缺失 | `apt install libaio1t64` + 建软链 `ln -sf /usr/lib/x86_64-linux-gnu/libaio.so.1t64 /usr/lib/x86_64-linux-gnu/libaio.so.1` |
| 双击 `.bat` 无反应 | 文件被存成 LF 换行或 UTF-8 | 恢复为 CRLF + GBK：`git checkout -- 启动工具箱.bat` |

> `netexec` 的补充：它是 PyPI 上无发行包的包，需从 GitHub 装，且其构建依赖 `poetry-dynamic-versioning` 会读取 git 元数据——用源码 tarball 安装时需绕过：`POETRY_DYNAMIC_VERSIONING_BYPASS=0.0.0 pip install <tarball>`。

---

## 5. 完成后向用户汇报什么

用**结构化**的方式汇报，至少包含：

1. **平台信息** —— 在哪装的（WSL / Windows / 双端）、Python 版本
2. **工具就绪数** —— 例如 `56 个 AI 可调用工具中 54 个依赖就绪`
3. **仍缺失的项及原因** —— 明确区分「不可得」（商业软件/无公开源）与「安装失败」
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
