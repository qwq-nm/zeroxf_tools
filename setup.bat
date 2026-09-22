@echo off
rem ============================================================
rem  zeroxf 工具箱 AI 版 · Windows 环境检查与依赖安装清单
rem  用法: setup.bat [--install]
rem    （不带参数：只检查；带 --install：执行下方 winget 安装）
rem ============================================================
setlocal EnableDelayedExpansion

echo.
echo == zeroxf 工具箱 AI 版 · Windows 环境检查 ==
echo.

rem ---- Python ----
python --version >nul 2>&1
if %errorlevel%==0 (
    echo [ok]   Python: %errorlevel% & python --version
) else (
    echo [缺少] Python 3.8+，请安装: https://www.python.org/downloads/
    echo        或 winget install Python.Python.3.12
)

rem ---- 本机 venv ----
if exist "%~dp0venv\Scripts\python.exe" (
    echo [ok]   项目 venv 存在
) else (
    echo [提示] 未找到 venv，可选: python -m venv venv ^&^& venv\Scripts\pip install PyQt6
)

rem ---- Java ----
where java >nul 2>&1
if %errorlevel%==0 (
    echo [ok]   Java: & java -version 2^>^&1 | findstr /i "version"
) else (
    echo [缺少] Java 8/11（JAVA8/JAVA11 类工具需要），
    echo        安装: winget install EclipseAdoptium.Temurin.11.JDK
)

rem ---- 常用系统命令 ----
for %%t in (nmap sqlmap nuclei ffuf httpx hydra fscan frps frpc chisel) do (
    where %%t >nul 2>&1
    if !errorlevel!==0 (
        echo [ok]   %%t
    ) else (
        echo [缺少] %%t
    )
)

echo.
if "%~1"=="--install" (
    echo == 开始安装缺失系统依赖（winget）==
    winget install --id Insecure.Nmap -e
    winget install --id ProjectDiscovery.Nuclei -e
    winget install --id ProjectDiscovery.Httpx -e
    winget install --id ffuf.ffuf -e
    pip install sqlmap
    echo [提示] hydra/fscan/frp/chisel 请从官方 release 下载二进制放入 tools\ 或 PATH
) else (
    echo [提示] 加 --install 参数自动安装常见依赖（winget/pip）
)
endlocal
