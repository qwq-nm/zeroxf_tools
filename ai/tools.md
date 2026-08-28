# 天狐工具箱 AI 参考手册（geshell）

> 由 `geshell gendocs` 自动生成。工具名匹配忽略大小写、空格、横线、下划线，支持拼音。

## 调用方式
```bash
geshell <工具名> [参数...]
```

## 工具总览（AI 可调用）

| 调用名 | 工具 | 类型 | 风险 | 用途 |
| --- | --- | --- | --- | --- |
| nmap | nmap | 命令行 | passive | 网络发现与端口/服务版本扫描 |
| httpx | httpx | 命令行 | passive | HTTP 探活与 Web 指纹识别 |
| urlfinder | urlfinder | 命令行 | passive | 从 JS/HTML 提取隐藏 URL 与敏感接口 |
| ffuf | ffuf | 命令行 | passive | 目录/文件/参数 Fuzz |
| nuclei | nuclei | 命令行 | passive | 基于 YAML 模板的自动化漏洞扫描 |
| sqlmap | sqlmap | 命令行 | active | SQL 注入自动化检测与利用 |
| xray | xray | 命令行 | passive | 被动代理漏洞扫描器 |
| dalfox | dalfox | 命令行 | active | XSS 专用扫描器 |
| ssti | ssti | 命令行 | exploit | 模板注入(SSTI)检测与利用 |
| spring | spring | 命令行 | exploit | Spring Boot 信息泄漏 + RCE |
| tomcat | tomcat | 命令行 | exploit | Tomcat 弱口令 + 上传漏洞 |
| dedecmscan | dedecmscan | 命令行 | exploit | DedeCMS 漏洞扫描 |
| redis | redis | 命令行 | exploit | Redis 未授权访问 + RCE + 写 Shell |
| heapdump | heapdump | 命令行 | exploit | 从 HeapDump 提取敏感信息 |
| ruoyi | ruoyi | 命令行 | exploit | 若依框架漏洞扫描与利用 |
| fscan | fscan | 命令行 | active | 内网综合扫描（端口/服务/漏洞/MS17010） |
| yasso | yasso | 命令行 | active | 内网扫描 + 密码爆破 |
| hydra | hydra | 命令行 | brute | 多协议在线密码爆破 |
| hashcat | hashcat | 命令行 | brute | GPU 离线密码哈希爆破 |
| frps | frps | 命令行 | tunnel | frp 服务端（VPS 接收内网连接） |
| frpc | frpc | 命令行 | tunnel | frp 客户端（内网机器映射服务） |
| chisel | chisel | 命令行 | tunnel | HTTP 隧道 / SOCKS5 代理 |
| metasploit | metasploit | 命令行 | post-exploit | Metasploit 渗透测试框架（CLI） |
| avoidkilling | avoidkilling | 命令行 | post-exploit | PHP 免杀 Webshell 生成（XOR/Base64/混淆） |
| docem | docem | 命令行 | post-exploit | Office 文档 XXE / XSS Payload 注入 |

## 信息收集工具

### nmap（nmap）

- 说明：网络发现与端口/服务版本扫描
- 风险：passive
- 参数模式：passthrough
- 别名：nmap-rs
- 示例：`geshell nmap -sV -sC -p- --min-rate=1000 target.com`

### httpx（httpx）

- 说明：HTTP 探活与 Web 指纹识别
- 风险：passive
- 参数模式：passthrough
- 别名：httpx-probe
- 示例：`geshell cat urls.txt | httpx -sc -title -tech-detect`

### urlfinder（urlfinder）

- 说明：从 JS/HTML 提取隐藏 URL 与敏感接口
- 风险：passive
- 参数模式：passthrough
- 别名：url-finder
- 示例：`geshell urlfinder -u https://target.com -s 2`

### ffuf（ffuf）

- 说明：目录/文件/参数 Fuzz
- 风险：passive
- 参数模式：passthrough
- 别名：ffuf-fuzz, dirsearch
- 示例：`geshell ffuf -u https://target.com/FUZZ -w /opt/wordlists/dir-common.txt`

### arl（arl）

- 说明：ARL 灯塔资产管理平台 Web 控制台
- 风险：passive
- 参数模式：passthrough

## 漏洞扫描与利用工具

### nuclei（nuclei）

- 说明：基于 YAML 模板的自动化漏洞扫描
- 风险：passive
- 参数模式：passthrough
- 别名：nuclei-scan
- 示例：`geshell nuclei -u https://target.com -severity critical,high`

### sqlmap（sqlmap）

- 说明：SQL 注入自动化检测与利用
- 风险：active
- 参数模式：passthrough
- 别名：sqli, sql注入
- 示例：`geshell sqlmap -u 'https://target.com/?id=1' --batch --level=3`

### xray（xray）

- 说明：被动代理漏洞扫描器
- 风险：passive
- 参数模式：passthrough
- 别名：xray-proxy
- 示例：`geshell xray webscan --listen 127.0.0.1:7777`

### dalfox（dalfox）

- 说明：XSS 专用扫描器
- 风险：active
- 参数模式：passthrough
- 别名：xss, xssscan
- 示例：`geshell dalfox url https://target.com/?search=test`

### ssti（ssti）

- 说明：模板注入(SSTI)检测与利用
- 风险：exploit
- 参数模式：passthrough
- 别名：ssti检测
- 示例：`geshell ssti auto -u 'https://target.com/?name=admin'`

## 框架漏洞利用工具

### spring（spring）

- 说明：Spring Boot 信息泄漏 + RCE
- 风险：exploit
- 参数模式：passthrough
- 别名：springboot, actuator
- 示例：`geshell spring boot -u https://target.com`

### tomcat（tomcat）

- 说明：Tomcat 弱口令 + 上传漏洞
- 风险：exploit
- 参数模式：passthrough
- 别名：tomcat弱口令
- 示例：`geshell tomcat`

### dedecmscan（dedecmscan）

- 说明：DedeCMS 漏洞扫描
- 风险：exploit
- 参数模式：passthrough
- 别名：dedecms
- 示例：`geshell dedecmscan -u https://target.com`

### redis（redis）

- 说明：Redis 未授权访问 + RCE + 写 Shell
- 风险：exploit
- 参数模式：passthrough
- 别名：redis未授权, redis-rce
- 示例：`geshell redis exp -h 10.0.0.5 -p 6379`

### heapdump（heapdump）

- 说明：从 HeapDump 提取敏感信息
- 风险：exploit
- 参数模式：passthrough
- 别名：heap-dump
- 示例：`geshell heapdump -f heapdump文件路径`

### ruoyi（ruoyi）

- 说明：若依框架漏洞扫描与利用
- 风险：exploit
- 参数模式：passthrough
- 别名：若依
- 示例：`geshell ruoyi -u https://target.com`

## 内网渗透工具

### fscan（fscan）

- 说明：内网综合扫描（端口/服务/漏洞/MS17010）
- 风险：active
- 参数模式：passthrough
- 别名：fscan扫描
- 示例：`geshell fscan -h 10.0.0.0/24`

### yasso（yasso）

- 说明：内网扫描 + 密码爆破
- 风险：active
- 参数模式：passthrough
- 别名：yasso内网
- 示例：`geshell yasso`

## 爆破工具

### hydra（hydra）

- 说明：多协议在线密码爆破
- 风险：brute
- 参数模式：passthrough
- 别名：爆破
- 示例：`geshell hydra -l root -P pass.txt ssh://10.0.0.5`

### hashcat（hashcat）

- 说明：GPU 离线密码哈希爆破
- 风险：brute
- 参数模式：passthrough
- 别名：hash爆破
- 示例：`geshell hashcat -m 1000 hashes.txt /opt/wordlists/rockyou.txt`

## 隧道代理工具

### frps（frps）

- 说明：frp 服务端（VPS 接收内网连接）
- 风险：tunnel
- 参数模式：passthrough
- 别名：frp服务端
- 示例：`geshell frps -c frps.toml`

### frpc（frpc）

- 说明：frp 客户端（内网机器映射服务）
- 风险：tunnel
- 参数模式：passthrough
- 别名：frp客户端
- 示例：`geshell frpc -c frpc.toml`

### chisel（chisel）

- 说明：HTTP 隧道 / SOCKS5 代理
- 风险：tunnel
- 参数模式：passthrough
- 别名：chisel隧道
- 示例：`geshell chisel server -p 8080 --reverse`

## 后渗透工具

### metasploit（metasploit）

- 说明：Metasploit 渗透测试框架（CLI）
- 风险：post-exploit
- 参数模式：passthrough
- 别名：msf, metasploit框架
- 示例：`geshell msfconsole -q`

### cobaltstrike4.9（cobaltstrike4.9）

- 说明：CobaltStrike 4.9 红队 C2 平台
- 风险：post-exploit
- 参数模式：passthrough
- 别名：cs, cobaltstrike

### avoidkilling（avoidkilling）

- 说明：PHP 免杀 Webshell 生成（XOR/Base64/混淆）
- 风险：post-exploit
- 参数模式：passthrough
- 别名：免杀
- 示例：`geshell avoidkilling -type default -e xor2 -name config.php`

### docem（docem）

- 说明：Office 文档 XXE / XSS Payload 注入
- 风险：post-exploit
- 参数模式：passthrough
- 别名：docem
- 示例：`geshell docem`

## 抓包与代理工具

### BurpSuite（burpsuite）

- 说明：Burp Suite 抓包代理（GUI）
- 风险：passive
- 参数模式：passthrough
- 别名：burp

## WebShell管理工具

### 蚁剑（antsword）

- 说明：AntSword WebShell 管理（GUI）
- 风险：post-exploit
- 参数模式：passthrough
- 别名：antsword

### 哥斯拉（godzilla）

- 说明：Godzilla WebShell 管理（GUI）
- 风险：post-exploit
- 参数模式：passthrough
- 别名：godzilla

### 冰蝎（behinder）

- 说明：Behinder WebShell 管理（GUI）
- 风险：post-exploit
- 参数模式：passthrough
- 别名：behinder
