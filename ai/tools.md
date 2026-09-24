# zeroxf 工具箱 AI 参考手册（geshell）

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
| ssti | ssti | Python | exploit | SSTI 统一入口：Fenjing + SSTImap（WAF 绕过） |
| spring | spring | Python | exploit | Spring 统一入口：SpringScan + SpringBoot-Scan + CloudSe |
| tomcat | tomcat | Python | brute | Tomcat 扫描（弱口令/上传漏洞） |
| dedecmscan | dedecmscan | Python | exploit | DedeCMS 漏洞扫描器 |
| redis | redis | Python | exploit | Redis 统一入口：爆破/RCE/写Shell/SSH/Cron |
| heapdump | heapdump | JAVA11 | passive | Heap Dump 敏感信息提取 v1.1 |
| ruoyi | ruoyi | Python | exploit | 若依统一入口：扫描器 + 综合利用 |
| fscan | fscan | 命令行 | active | 内网综合扫描（端口/服务/漏洞/MS17010） |
| yasso | yasso | 命令行 | active | 内网扫描 + 密码爆破 |
| hydra | hydra | Python | bruteforce | 密码爆破（ssh/ftp/rdp/smb/mssql/ldap/winrm 等 15 种协议）：有  |
| hashcat | hashcat | 命令行 | brute | GPU 离线密码哈希爆破 |
| frps | frps | 命令行 | tunnel | frp 服务端（VPS 接收内网连接） |
| frpc | frpc | 命令行 | tunnel | frp 客户端（内网机器映射服务） |
| chisel | chisel | 命令行 | tunnel | HTTP 隧道 / SOCKS5 代理 |
| metasploit | metasploit | 命令行 | post-exploit | Metasploit 渗透测试框架（CLI） |
| avoidkilling | avoidkilling | Python | post-exploit | PHP 免杀 Webshell 生成 |
| docem | docem | Python | exploit | Office 文档 XXE / XSS Payload 注入 |
| subfinder | subfinder | 命令行 | passive | 子域名被动收集 |
| naabu | naabu | 命令行 | passive | 端口扫描器（ProjectDiscovery） |
| katana | katana | 命令行 | passive | 下一代爬虫（JS 渲染） |
| dnsx | dnsx | 命令行 | passive | DNS 查询与验证 |
| uncover | uncover | 命令行 | passive | Shodan/Censys 测绘聚合 |
| gobuster | gobuster | 命令行 | passive | 目录/虚拟主机爆破 |
| shiro | shiro | JAVA8 | exploit | Shiro 反序列化利用 v5.1.1 |
| struts2 | struts2 | JAVA11 | exploit | Struts2 漏洞利用 v19.73 |
| weblogic | weblogic | JAVA8 | exploit | WebLogic 漏洞利用 v1.3 |
| thinkphp | thinkphp | JAVA8 | exploit | ThinkPHP 漏洞利用 GUI |
| nacos | nacos | JAVA11 | exploit | Nacos 漏洞利用 v3.0.5 |
| jenkins | jenkins | JAVA8 | exploit | Jenkins 漏洞利用 GUI |
| xxljob | xxl-job | JAVA8 | exploit | XXL-JOB 漏洞利用 |
| dbx | dbx | Python | active | 数据库工作台 DBX：支持 70+ 种库（MySQL/PG/SQLite/Oracle/SQL Se |
| netexec | netexec | 命令行 | active | 内网认证/枚举（原 crackmapexec） |
| sliver | sliver | 命令行 | post-exploit | Sliver 开源 C2 |
| dirsearch | dirsearch | Python | passive | Web 目录扫描（枷锁版） |
| revshell | revshell | Python | post-exploit | 反弹 Shell 命令生成（11 种语言/环境，含监听命令） |
| jeecg | jeecg | JAVA8 | exploit | Jeecg-Boot 漏洞利用 |
| iwannagetall | iwannagetall | JAVA8 | exploit | OA 综合利用 |
| hyacinth | hyacinth | JAVA8 | exploit | Java 综合利用 v2.0.2 |
| webshell | webshell | Python | post-exploit | WebShell 管理 CLI：直连蚁剑/冰蝎/哥斯拉三种协议的 PHP 马，可执行命令、探服务器信 |
| jndi | jndi | JAVA8 | exploit | JNDI 注入利用服务端（JNDI-Injection-Exploit）：起 LDAP/RMI 服务 |
| zap | zap | 命令行 | passive | OWASP ZAP 被动代理/自动化扫描（替代已停止公开分发的 xray） |
| impacket | impacket | 命令行 | active | impacket 协议攻击脚本集：secretsdump/psexec/smbclient/GetN |
| exploitdb | exploitdb | 命令行 | passive | ExploitDB 本地漏洞库检索（searchsploit；配合 sliver/nuclei/im |

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
- 别名：ffuf-fuzz
- 示例：`geshell ffuf -u https://target.com/FUZZ -w /opt/wordlists/dir-common.txt`

### arl（arl）

- 说明：ARL 灯塔资产管理平台 Web 控制台入口（指向本机 localhost:5003，需另行部署）
- 风险：passive
- 参数模式：passthrough

### subfinder（subfinder）

- 说明：子域名被动收集
- 风险：passive
- 参数模式：passthrough
- 别名：sub, 子域名
- 示例：`geshell subfinder -d target.com -all`

### naabu（naabu）

- 说明：端口扫描器（ProjectDiscovery）
- 风险：passive
- 参数模式：passthrough
- 别名：naabu端口
- 示例：`geshell naabu -host target.com -p -`

### katana（katana）

- 说明：下一代爬虫（JS 渲染）
- 风险：passive
- 参数模式：passthrough
- 别名：katana爬虫
- 示例：`geshell katana -u https://target.com -jc`

### dnsx（dnsx）

- 说明：DNS 查询与验证
- 风险：passive
- 参数模式：passthrough
- 别名：dnsx查询
- 示例：`geshell dnsx -l domains.txt -a -resp`

### uncover（uncover）

- 说明：Shodan/Censys 测绘聚合
- 风险：passive
- 参数模式：passthrough
- 别名：uncover测绘
- 示例：`geshell uncover -q 'app:shiro'`

### gobuster（gobuster）

- 说明：目录/虚拟主机爆破
- 风险：passive
- 参数模式：passthrough
- 别名：gobuster目录
- 示例：`geshell gobuster dir -u https://target.com -w dict.txt`

### dirsearch（dirsearch）

- 说明：Web 目录扫描（枷锁版）
- 风险：passive
- 参数模式：passthrough
- 别名：dirsearch扫描
- 示例：`geshell dirsearch -u http://target:8888 -e php,html,js -t 25`

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

- 说明：SSTI 统一入口：Fenjing + SSTImap（WAF 绕过）
- 风险：exploit
- 参数模式：passthrough
- 别名：ssti检测, sstikit
- 示例：`geshell ssti auto -u http://target/?name=test`

### docem（docem）

- 说明：Office 文档 XXE / XSS Payload 注入
- 风险：exploit
- 参数模式：passthrough
- 别名：docx
- 示例：`geshell docem`

### zap（zap）

- 说明：OWASP ZAP 被动代理/自动化扫描（替代已停止公开分发的 xray）
- 风险：passive
- 参数模式：passthrough
- 别名：zap, owaspzap
- 示例：`geshell zap.sh -cmd -quickurl http://target.com -quickout /tmp/zap.html`

### exploitdb（exploitdb）

- 说明：ExploitDB 本地漏洞库检索（searchsploit；配合 sliver/nuclei/impacket 覆盖 msf 用途）
- 风险：passive
- 参数模式：passthrough
- 别名：exploitdb, searchsploit
- 示例：`geshell searchsploit apache 2.4`

## 框架漏洞利用工具

### spring（spring）

- 说明：Spring 统一入口：SpringScan + SpringBoot-Scan + CloudSec
- 风险：exploit
- 参数模式：passthrough
- 别名：springboot, actuator
- 示例：`geshell spring boot -u http://target:8080`

### tomcat（tomcat）

- 说明：Tomcat 扫描（弱口令/上传漏洞）
- 风险：brute
- 参数模式：passthrough
- 别名：tomcatscanpro
- 示例：`geshell tomcat`

### dedecmscan（dedecmscan）

- 说明：DedeCMS 漏洞扫描器
- 风险：exploit
- 参数模式：passthrough
- 别名：dedecms
- 示例：`geshell dedecmscan -u https://target.com`

### redis（redis）

- 说明：Redis 统一入口：爆破/RCE/写Shell/SSH/Cron
- 风险：exploit
- 参数模式：passthrough
- 别名：redis未授权, redisexp
- 示例：`geshell redis exp -h`

### shiro（shiro）

- 说明：Shiro 反序列化利用 v5.1.1
- 风险：exploit
- 参数模式：passthrough
- 别名：shiro反序列化

### struts2（struts2）

- 说明：Struts2 漏洞利用 v19.73
- 风险：exploit
- 参数模式：passthrough
- 别名：s2

### weblogic（weblogic）

- 说明：WebLogic 漏洞利用 v1.3
- 风险：exploit
- 参数模式：passthrough
- 别名：weblogic漏洞

### thinkphp（thinkphp）

- 说明：ThinkPHP 漏洞利用 GUI
- 风险：exploit
- 参数模式：passthrough
- 别名：thinkphp漏洞

### jndi（jndi）

- 说明：JNDI 注入利用服务端（JNDI-Injection-Exploit）：起 LDAP/RMI 服务并投递 payload
- 风险：exploit
- 参数模式：passthrough
- 别名：jndi, jndi-injection
- 示例：`geshell jndi -C 'touch /tmp/pwn' -A 10.0.0.5`

## 重点系统漏洞工具

### heapdump（heapdump）

- 说明：Heap Dump 敏感信息提取 v1.1
- 风险：passive
- 参数模式：passthrough
- 别名：jdumpspider
- 示例：`geshell heapdump -f heapdump文件路径`

### ruoyi（ruoyi）

- 说明：若依统一入口：扫描器 + 综合利用
- 风险：exploit
- 参数模式：passthrough
- 别名：若依, ruoyi-all
- 示例：`geshell ruoyi scan`

### nacos（nacos）

- 说明：Nacos 漏洞利用 v3.0.5
- 风险：exploit
- 参数模式：passthrough
- 别名：nacos未授权

### jenkins（jenkins）

- 说明：Jenkins 漏洞利用 GUI
- 风险：exploit
- 参数模式：passthrough
- 别名：jenkins漏洞

### xxl-job（xxljob）

- 说明：XXL-JOB 漏洞利用
- 风险：exploit
- 参数模式：passthrough
- 别名：xxljob

### jeecg（jeecg）

- 说明：Jeecg-Boot 漏洞利用
- 风险：exploit
- 参数模式：passthrough
- 别名：jeecg

### iwannagetall（iwannagetall）

- 说明：OA 综合利用
- 风险：exploit
- 参数模式：passthrough
- 别名：oa综合利用

### hyacinth（hyacinth）

- 说明：Java 综合利用 v2.0.2
- 风险：exploit
- 参数模式：passthrough
- 别名：java综合利用

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

### netexec（netexec）

- 说明：内网认证/枚举（原 crackmapexec）
- 风险：active
- 参数模式：passthrough
- 别名：netexec, crackmapexec
- 示例：`geshell nxc smb 10.0.0.0/24`

### impacket（impacket）

- 说明：impacket 协议攻击脚本集：secretsdump/psexec/smbclient/GetNPUsers 等（替代 NetExec）
- 风险：active
- 参数模式：passthrough
- 别名：impacket, secretsdump
- 示例：`geshell secretsdump.py domain/user:pass@10.0.0.5`

## 爆破工具

### hydra（hydra）

- 说明：密码爆破（ssh/ftp/rdp/smb/mssql/ldap/winrm 等 15 种协议）：有 hydra 用 hydra，Windows 无 hydra 时自动落到 netexec(nxc)
- 风险：bruteforce
- 参数模式：passthrough
- 别名：hydra, 爆破, brute
- 示例：`geshell hydra --service ssh --target 10.0.0.5 -u root --passwords pass.txt`

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

- 说明：C2 平台（商业软件，GUI，需自备）。AI 可用的开源 C2 是 sliver
- 风险：post-exploit
- 参数模式：passthrough
- 别名：cs, cobaltstrike

### avoidkilling（avoidkilling）

- 说明：PHP 免杀 Webshell 生成
- 风险：post-exploit
- 参数模式：passthrough
- 别名：免杀
- 示例：`geshell main.py -type default -e xor2 -name shell.php`

### sliver（sliver）

- 说明：Sliver 开源 C2
- 风险：post-exploit
- 参数模式：passthrough
- 别名：sliverc2
- 示例：`geshell sliver`

### revshell（revshell）

- 说明：反弹 Shell 命令生成（11 种语言/环境，含监听命令）
- 风险：post-exploit
- 参数模式：passthrough
- 别名：反弹shell, revshell, 反弹shell生成
- 示例：`geshell revshell 10.0.0.5 -p 4444 -l Netcat -v reverse_e`

## 抓包与代理工具

### BurpSuite（burpsuite）

- 说明：抓包代理（GUI）。AI 接口走 PortSwigger 官方 MCP 扩展而非 CLI（装法见 scripts/setup_burp.py，需 Professional 版）
- 风险：passive
- 参数模式：passthrough
- 别名：burp

## WebShell管理工具

### 蚁剑（antsword）

- 说明：蚁剑 WebShell 管理（GUI）⚠️ 未随工具箱分发（上游只发源码、无二进制），其协议的 AI 调用由 webshell 工具覆盖
- 风险：post-exploit
- 参数模式：passthrough
- 别名：antsword

### godzilla（godzilla）

- 说明：哥斯拉 WebShell 管理（GUI，自身无 CLI 接口）——AI 操作请用 webshell 工具
- 风险：post-exploit
- 参数模式：passthrough
- 别名：哥斯拉

### behinder（behinder）

- 说明：冰蝎 WebShell 管理 v4.1（GUI，自身无 CLI 接口）——AI 操作请用 webshell 工具
- 风险：post-exploit
- 参数模式：passthrough
- 别名：冰蝎

### webshell（webshell）

- 说明：WebShell 管理 CLI：直连蚁剑/冰蝎/哥斯拉三种协议的 PHP 马，可执行命令、探服务器信息、上传下载（--type auto 自动识别协议）
- 风险：post-exploit
- 参数模式：passthrough
- 别名：webshell, webshell管理, 马子管理
- 示例：`geshell webshell -u http://target/shell.php -p pass -t auto -c "id"`

## 数据库利用工具

### dbx（dbx）

- 说明：数据库工作台 DBX：支持 70+ 种库（MySQL/PG/SQLite/Oracle/SQL Server/Redis/MongoDB…），并自带 MCP server（22 个工具，AI 可直接查库）
- 风险：active
- 参数模式：passthrough
- 别名：dbx, 数据库, database
- 示例：`geshell dbx -n prod -c "SELECT * FROM users"`
