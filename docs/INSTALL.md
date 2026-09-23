# 安装指南

完整的环境要求、分步安装与故障排查。只想尽快跑起来的话，看 [README 的「方式一」](../README.md#方式一链初始化推荐)即可。

---

## 环境要求

| 项目 | 要求 |
| --- | --- |
| Python | 3.8+（Windows 建议 3.10+；GUI 需要 PyQt6，其 wheel 覆盖 3.8–3.13） |
| 系统 | Windows 10/11、WSL2、主流 Linux 发行版、macOS |
| 磁盘 | **约 5 GB**（工具二进制 ~3.5 G + 便携 JDK ~1.3 G） |
| 网络 | 能访问 GitHub / GitLab / PyPI（部分资产走 Azure Blob、downloads.mongodb.com） |

> 不必一次装全。只跑 CLI 的话不需要 PyQt6；只做信息收集的话可以不装 JDK（省 1.3 G）。

---

## 快速安装

```bash
git clone https://github.com/qwq-nm/zeroxf_tools.git
cd zeroxf_tools

python3 scripts/provision_tools.py --jdk    # 便携 JDK（14 个 jar 类工具需要）
python3 scripts/provision_tools.py          # 全部工具二进制（含 jar 包，约 4.1 GB）
python3 scripts/provision_tools.py --gui    # GUI 运行时（用界面才需要）
```

> 全量安装（不带 `--tools`）还会顺带装 **webshell 工具的依赖**
> （`requests` / `pycryptodome`）。单独补装：`--webshell-deps`。

> 不想一次拉 632 MB 的 jar 包时，用 `--tools` 挑具体工具即可（不带 `--tools`
> 的全量安装才会顺带还原 jar 包）。

Windows 下把 `python3` 换成 `python`。

---

## 分步详解

### 1. 获取代码

```bash
git clone https://github.com/qwq-nm/zeroxf_tools.git
cd zeroxf_tools
```

仓库里**只有代码和工具注册表**（`config/tools.json`）。工具二进制、JDK、GUI 运行时都不入库——它们体积大、且分平台，由安装脚本按需拉取。

> ⚠️ 注意 `tools/*` 在 `.gitignore` 里是**默认忽略**的，只有几个「仓库自带源码」目录例外
> （`oracle-py` / `revshell` / `sstikit` / `springkit` / `tomcatscanpro` / `dedecmscan` /
> `rediskit` / `ruoyikit` / `avoidkilling` / `docem` / `dirsearch`）。这些是天狐原创脚本，
> 没有任何下载源，**必须靠 git 分发**。若你自定义了 `.gitignore`，别把它们一起挡掉——
> 否则界面里有卡片、一点就报路径不存在。

### 2. 安装工具二进制

```bash
python3 scripts/provision_tools.py                    # 全部
python3 scripts/provision_tools.py --tools nuclei ffuf # 只装指定
python3 scripts/provision_tools.py --force            # 已存在也重新下载
```

脚本会自动识别平台：

| 平台 | 拉取的资产 |
| --- | --- |
| Windows | `*_windows_amd64.zip` / `.exe` |
| Linux / WSL | `*_linux_amd64` (ELF) |
| macOS | `*_darwin_*` |

**解压格式自动识别**：同一工具在不同平台的打包方式可能不同（例如 chisel 在 Linux 是 `.gz` 单文件、Windows 是 `.zip`），脚本按文件魔数判断，不依赖配置声明。

单工具失败**不会中断整批**——脚本会跳过并继续，最后统一汇总，你可以在全部跑完后单独重试失败项：

```bash
python3 scripts/provision_tools.py --tools <失败的工具名>
```

### 3. 安装 jar 类工具

```bash
python3 scripts/provision_tools.py --jars     # 单独安装 / 补齐
python3 scripts/provision_tools.py --jars --force   # 重新下载并覆盖
```

这 14 个工具（`shiro` `struts2` `weblogic` `thinkphp` `nacos` `jenkins` `xxl-job`
`jeecg` `dbcombo` `iwannagetall` `hyacinth` `godzilla` `behinder` `heapdump`）
的 jar 都是**第三方作者作品，没有公开下载源**，provision 没法逐个从上游拉。

它们合计 **632 MB**，其中 `weblogic`(130 MB)、`iwannagetall`(180 MB)、
`behinder`(126 MB) 单个就**超过 GitHub 单文件 100 MB 的硬限制**，因此不能入 git。
工具箱把它们打包成一个 Release 资产分发：

| 项目 | 值 |
| --- | --- |
| 资产 | `zeroxf-jar-tools-v1.tar.gz`（约 584 MB） |
| 位置 | 本仓库 Releases → tag `jar-tools-v1` |
| 缓存 | 下载后留在 `.buildtools/`（已 gitignore），重跑直接复用 |

脚本只解**缺失**的 jar，已存在的不覆盖（除非 `--force`）。包内路径会做目录穿越校验。

**手动安装**（脚本走不通时）：直接下载该资产解包，把 `tools/` 目录覆盖到仓库根目录即可，
结构与仓库一致（`tools/<工具名>/<jar>`）。包内 `MANIFEST.txt` 列了各 jar 的 sha256。

### 4. 安装便携 JDK

```bash
python3 scripts/provision_tools.py --jdk
```

装的是 **BellSoft Liberica** 的 full 版 JDK 8 / 11 / 17 到 `Java_path/`：

| JDK | 用途 | 为什么用 full 版 |
| --- | --- | --- |
| 8 | JavaFX 类工具（shiro、thinkphp、哥斯拉、冰蝎…） | full 版内置 JavaFX，且 JDK 8 的 JavaFX 由扩展类加载器**自动加载**，无需 `--module-path` |
| 11 | 少量 JAVA11 工具 | — |
| 17 | ZAP（要求 Java 17+） | — |

> 普通 JDK（如 Temurin）**不含 JavaFX**，那 7 个 JavaFX 工具会报 `NoClassDefFoundError: javafx/application/Application`。这就是这里特意选 full 版的原因。

装在工具箱内部，**不需要系统装 Java**，也不污染系统 PATH。

### 5. 安装 GUI 运行时

```bash
python3 scripts/provision_tools.py --gui
```

把 PyQt6 装进 `tools/_venv`（约 90 MB）。

---

## 系统依赖

绝大多数工具是静态编译的单文件，开箱即用。少数需要系统库：

| 工具 | 需要 | 安装 |
| --- | --- | --- |
| `oracle`（sqlplus） | `libaio.so.1` | `apt install libaio1t64`，并建立软链：<br>`ln -sf /usr/lib/x86_64-linux-gnu/libaio.so.1t64 /usr/lib/x86_64-linux-gnu/libaio.so.1` |
| `netexec` | Rust 工具链（其 `aardwolf` 依赖需编译） | `curl https://sh.rustup.rs -sSf \| sh -s -- -y --profile minimal` |
| `hydra` / `mysql` / `metasploit` | 系统包 | `apt install hydra default-mysql-client`；metasploit 用官方 installer |

> Ubuntu 24.04 上 `libaio1t64` 提供的文件名是 `libaio.so.1t64`，而 sqlplus 找的是 `libaio.so.1`，所以要建那条软链。

---

## 平台差异

### Windows

- 启动 GUI 双击 `启动工具箱.bat`；不想要黑窗口用 `启动工具箱-无窗口.vbs`
- 这些脚本已通过 `.gitattributes` 固定为 **CRLF + GBK**（Windows 中文 CMD 的原生格式）。**用编辑器改它们时务必保持这个格式**——存成 LF 或 UTF-8 会让 CMD 解析错乱、双击毫无反应
- 若目录是通过 `\\wsl.localhost\...` 访问的，CMD 不支持 UNC 作为工作目录。启动脚本已用 `pushd` 规避，但建议放 Windows 本地磁盘

### WSL / Linux

- GUI 通过 WSLg 直接显示在 Windows 桌面，无需额外 X server
- WSLg 同时提供 Wayland 与 XWayland，工具箱已自动为 Java 类工具注入 `GDK_BACKEND=x11`（否则 JavaFX 会 `GDK_IS_X11_DISPLAY` 断言失败并段错误）

### 双端并存

两端各放一份**独立目录**（如 WSL 的 `~/zeroxf-tools` + Windows 的 `D:\zeroxf-tools`），代码用 git 同步，依赖各自 provision。

> 不要让两端共用同一份目录：`tools/_venv`（Linux 的 `bin/` 与 Windows 的 `Scripts/`）和 `Java_path/` 会冲突。

---

## 故障排查

### 双击 `.bat` 毫无反应

按顺序查：

1. **换行/编码** —— 文件必须是 CRLF + GBK。验证：
   ```bash
   python3 -c "
   raw=open('启动工具箱.bat','rb').read()
   print('CRLF:', raw.count(b'\r\n'), '残留LF:', raw.count(b'\n')-raw.count(b'\r\n'))
   "
   ```
   残留 LF 应为 0。
2. **有没有 Python** —— 启动脚本会依次找 `python3\pythonw.exe`（便携）→ `pyw` → `pythonw` → `py` → `python`。全都没有时会弹提示（不再是静默失败）。
3. **依赖是否齐** —— `python -c "import PyQt6"`。

### `geshell doctor` 报某个工具缺失

`doctor` 会区分三种情况：

- **路径不存在** —— 没装，跑 `provision_tools.py --tools <名字>`
- **命令不在 PATH** —— 需要系统级安装（见上面「系统依赖」）
- **依赖缺失** —— 缺某个被依赖的命令

### 下载中断 / 报 `HTTP 416`

脚本自带**断点续传**（Range 请求）与重试。若出现 416，说明本地残留文件已达或超过远端长度，脚本会自动清除残留并全量重下——重跑一次即可。

### Java 工具报 `NoClassDefFoundError: javafx/...`

JDK 装错了版本。必须是 **Liberica full 版**（内置 JavaFX），Temurin 等常规发行版不含：

```bash
python3 scripts/provision_tools.py --jdk --force
```

### Java 工具窗口闪退 / 段错误（仅 WSL）

WSLg 的 Wayland/XWayland 双栈问题。工具箱已自动注入 `GDK_BACKEND=x11`；若手动运行，自行加上该环境变量。

### `hashcat` 解压失败（`BCJ2 filter is not supported`）

其发行包用了 BCJ2 过滤器，`py7zr` 不支持。Linux 端脚本会用自带的 `.buildtools/7zz`；Windows 端会自动拉取 `7zr.exe`。若自动获取失败（网络原因），手动下载 [7zr.exe](https://www.7-zip.org/a/7zr.exe) 放到 `.buildtools/` 即可。

---

## 验证安装

```bash
./geshell doctor      # 环境自检：JDK / 依赖 / 路径 / 调用名冲突
./geshell selftest    # 回归测试（11 项）
./geshell list        # 列出全部工具与可调用状态
```

`doctor` 报出的 `CobaltStrike` / `BurpSuite` / `蚁剑` / `fastjson` / `log4j` 属**预期**——它们是商业软件或无可公开来源，说明见 [README](../README.md#关于不可得的工具)。

---

## 卸载

工具箱是绿色安装，**不写注册表、不改系统 PATH**（除你自行执行的系统依赖）：

```bash
rm -rf zeroxf_tools              # 删目录即可
rm -rf ~/.cargo ~/.rustup        # 若为 netexec 装过 Rust
```
