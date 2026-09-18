# zeroxf 工具箱 · AI 版

以 **天狐工具箱 V4.0**（`wr0ld/tianhu-toolbox-v4`）为框架底座做的二开：给它加上了 **geshell CLI + MCP 接口**（AI/CLI 统一入口），架构与接口参考枷锁工具箱（GetShell）的 `ai/launch.py` 设计，并做了 **Windows 适配**。

- 工具注册表：`config/tools.json`（扩展 schema，GUI 与 CLI 共用单一数据源）
- GUI（`main.py`/`launcher.py`）：天狐原样保留，供 Windows 人工操作
- CLI（`geshell` / `geshell.cmd`）：AI 可直接调用
- MCP（`ai/mcp_server.py`）：AI 以 MCP 工具形式调用

## 快速开始

```bash
# Linux / macOS
cd ~/tianhu-tools
./geshell list            # 列出所有工具
./geshell info nmap       # 查看工具详情
./geshell nmap -sV -p- target.com   # 直接调用

# Windows
geshell list
```

命令名匹配忽略大小写、空格、横线和下划线，支持中文拼音（如 `geshell ruoyi` / `geshell 若依`）。

## geshell 命令面

| 命令 | 说明 |
| --- | --- |
| `geshell list` | 按分类列出工具，AI 可用打 ✓，GUI/网页打 ✗ |
| `geshell info <工具>` | 工具详情 + 调用方式 |
| `geshell doctor` | 环境自检（JDK / 依赖命令 / 调用名冲突 / 路径） |
| `geshell selftest` | 运行回归测试 |
| `geshell gendocs` | 重新生成 `ai/tools.md`（AI 参考手册） |
| `geshell <工具> [参数...]` | 调用工具，输出实时流式并落盘到 `output/runs/<时间戳>_<名>/` |

## MCP 接口

`ai/mcp_server.py` 是 stdio JSON-RPC MCP server，暴露 `tools/list` 和 `tools/call`，工具名为 `tool_<调用名>`（如 `tool_nmap`、`tool_sqlmap`）。

在 Claude Code 的 `~/.claude.json` 里注册（`mcpServers` 段）：

```json
{
  "mcpServers": {
    "tianhu-geshell": {
      "command": "python3",
      "args": ["/path/to/tianhu-tools/ai/mcp_server.py"],
      "description": "zeroxf 工具箱 geshell：AI 可调用全部渗透工具"
    }
  }
}
```

Windows 端把 `python3` 换成 `python`，路径换成 `C:\...\ai\mcp_server.py`。

## 工具清单

工具清单 = 枷锁好工具 + ProjectDiscovery 全家桶 + **从枷锁 1.2GB 包提取的跨平台工具**（约 58 个），分类：信息收集 / 漏洞扫描 / 框架漏洞利用 / 内网渗透 / 爆破 / 隧道代理 / 后渗透 / WebShell / 抓包代理 / 重点系统漏洞 / 数据库利用。

**工具来源分三层**：
1. **官方二进制**（`provision_tools.py` 自动拉取，20 个）：nuclei/httpx/ffuf/fscan/dalfox/chisel/frps/frpc/sqlmap/subfinder/naabu/katana/dnsx/uncover/sqlcmd/gobuster/urlfinder/yasso/sliver/hashcat
2. **从枷锁提取的跨平台工具**（24 个）：python 工具集（ssti/spring/ruoyi/redis/tomcat/dirsearch/docem/dedecmscan/avoidkilling/revshell）+ jar 利用工具（shiro/struts2/thinkphp/weblogic/jenkins/xxl-job/jeecg/nacos/数据库综合/OA 综合利用/哥斯拉/冰蝎/HeapDump 提取）
3. **需系统安装或自备**（doctor 会提示）：hydra/hashcat/metasploit/nmap、mysql/mongodb/oracle/netexec、xray/CS/Burp 等

`scripts/provision_tools.py` 会自动从官方 GitHub release 拉取可免费分发的二进制；同一脚本在 Windows 重跑一次即拉 .exe 版本。Python 工具共用 `tools/_venv`（已装好依赖）。

每条工具的扩展字段（天狐原生字段之外新增）：

| 字段 | 说明 |
| --- | --- |
| `risk` | 风险等级：`passive / active / exploit / brute / tunnel / post-exploit` |
| `ai_callable` | AI 能否直接调用（GUI 工具设 false） |
| `aliases` | 别名，参与模糊匹配（中文工具名的 aliases[0] 是真实命令） |
| `example` | 示例命令（写入 tools.md 给 AI 参考） |
| `dependencies` | 依赖命令（doctor 用 `shutil.which` 检查） |

### 合并你自带的原版天狐 tools.json（踢掉不好用的）

```bash
python3 scripts/merge_tools.py --import 你的原版tools.json [--drop name1 name2 ...]
```

合并规则：按 name+category 去重，保留现有条目（含扩展字段），`--drop` 列表里的工具直接剔除。

## 环境依赖

- Python 3.8+（GUI 需要 PyQt6，CLI 不需要）
- 系统命令类工具需自行安装（`doctor` 会提示缺失）：nmap / sqlmap / nuclei / ffuf / httpx / hydra / fscan / frp 等
- Java 类工具（JAVA8/JAVA11）：需 JDK，`doctor` 会检测

Windows 可用 `setup.bat` 检查环境并列出 winget 安装命令。

## 二开改了天狐的哪些东西

| 文件 | 改动 |
| --- | --- |
| `config.py` | 路径常量锚定 `BASE_DIR`（不再依赖 cwd）；`save_tools` 保留裸命令名（如 `nmap`）不被绝对化 |
| 新增 `ai/` | `launch.py`（geshell 后端）、`cli_runner.py`（跨平台命令执行）、`fuzzy.py`（从天狐 utils 抽出，无 PyQt6）、`mcp_server.py`、`selftest.py`、`tools.md`（生成） |
| 新增入口 | `geshell`（bash）、`geshell.cmd`（Windows） |
| `config/tools.json` | 种子工具清单（扩展 schema） |

## 授权与合规

仅限在明确授权的资产和测试范围内使用。未授权扫描、爆破、利用或访问他人系统违法。

> 二开说明：本项目基于 [wr0ld/tianhu-toolbox-v4](https://github.com/wr0ld/tianhu-toolbox-v4)（GPL-3.0），CLI 架构参考 [One-JiaSuo/Jiasuo-tools](https://github.com/One-JiaSuo/Jiasuo-tools)。
