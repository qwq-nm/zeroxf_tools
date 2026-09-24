---
name: zeroxf-toolbox
description: >-
  zeroxf 工具箱（63 个渗透工具的命令行/MCP 集合）。当手头出现**具体的安全测试目标**时使用——
  域名、IP、URL、CTF 题目附件、nc 地址、需要扫描/爆破/漏洞利用/拿 shell/内网横向/后渗透的场景。
  典型触发：「扫一下这个站」「这有个 IP 帮我看看」「CTF 这道题」「爆破一下」「有没有 shiro/weblogic 利用工具」
  「换个工具试试」「本地有没有现成的 XX 工具」。先 `geshell list` 看工具箱里有什么再动手，
  比自己现拼命令快且全。**注意：先跑 `geshell doctor` 确认真实就绪度——`list` 标 ✓ 只代表注册过，
  不代表文件已安装（新 clone 只有十几个可用）。**
---

# zeroxf 工具箱 — 用法

**先定位工具箱**（路径因人而异，下面这套能自己找到）：

```bash
# 常见位置，或按 geshell + config/tools.json 这两个标志物搜
TB=~/zeroxf_tools
[ -x "$TB/geshell" ] || TB=$(find ~ -maxdepth 3 -name geshell -type f -perm -u+x 2>/dev/null | head -1 | xargs -r dirname)
echo "工具箱: $TB"
```

## 第一步永远是这两个

```bash
cd "$TB"
./geshell doctor          # 真实就绪度：哪些工具的文件真的在
./geshell list            # 63 个工具按分类列出
```

`list` 的状态列是三态，含义不同：

| 符号 | 含义 |
| --- | --- |
| `✓` | 就绪，可直接调用 |
| `⚠` | 已注册为 AI 可调用，但**入口文件不存在**（没装），调用会报路径不存在 |
| `✗` | 未注册为 AI 可调用（通常是 GUI 或商业软件） |

**全新 clone 只有十几个是 ✓**，其余要跑 provision 才到位。不先看这个就调用，
会得到一堆「路径不存在」。

## 找工具 → 看用法 → 调用

```bash
./geshell info nmap           # 单个工具的详情、入口路径、示例
./geshell nmap -sV -p- TARGET # 直接调用，参数原样透传
```

命令名**忽略大小写、空格、横线和下划线**，支持中文别名：

```bash
./geshell 若依        # = ./geshell ruoyi
./geshell 反弹shell   # = ./geshell revshell
```

## 几个值得记住的工具

| 场景 | 工具 |
| --- | --- |
| 端口/服务 | `nmap` `fscan` `naabu` |
| Web 探测 | `httpx` `nuclei` `ffuf` `dirsearch` `katana` |
| 框架漏洞 | `shiro` `struts2` `weblogic` `thinkphp` `spring` `tomcat` `nacos` `jenkins` |
| JNDI 注入 | `jndi`（起 LDAP/RMI 服务端） |
| 数据库 | `sqlmap` `oracle-py` `usql` `redis` `mongodb` |
| WebShell | `webshell`（蚁剑/冰蝎/哥斯拉三种协议 + 自动识别） |
| 爆破 | `hydra`（Windows 上自动落到 netexec） |
| 内网 | `fscan` `yasso` `netexec` `impacket` |
| 后渗透 | `metasploit` `sliver` `revshell` `avoidkilling` |

## 工具缺失时

```bash
python3 scripts/provision_tools.py                       # 全量（约 4.9 G）
python3 scripts/provision_tools.py --tools nuclei ffuf   # 只装指定的
python3 scripts/provision_tools.py --jars                # 只补 14 个 jar 类工具
python3 scripts/provision_tools.py --jdk                 # 便携 JDK
python3 scripts/provision_tools.py --webshell-deps       # webshell 依赖
python3 scripts/verify_all.py                            # 一站式自检
```

## 通过 MCP 调用（可选）

`ai/mcp_server.py` 是 stdio JSON-RPC server，把 57 个工具暴露为 `tool_<名称>`。
注册方法与 `~/.claude.json` 配置见工具箱 README 的「MCP（AI 调用）」一节。

## 边界

- **只在有明确授权的目标上使用**。未授权扫描/爆破/利用违法。
- 高风险工具（爆破、漏洞利用）先跟用户确认目标在授权范围内。
- 运行日志在 `output/runs/<时间戳>_<工具名>/`，排查失败时看那里。
