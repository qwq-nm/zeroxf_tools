@echo off
rem zeroxf 工具箱 · GUI 启动器
rem
rem 用 pushd 而不是 cd /d：cd 不支持 UNC 路径（例如直接从
rem \\wsl.localhost\Ubuntu\... 里双击本脚本），会被 CMD 拒绝并把工作目录
rem 退回 C:\WINDOWS\system32，导致后面的相对路径 python3\pythonw.exe 全部失效。
rem pushd 会把 UNC 临时映射成一个盘符，从而正常进入目录。
pushd "%~dp0"

rem 1) 优先用工具箱自带的便携 Python
if exist "python3\pythonw.exe" (
    start "" "python3\pythonw.exe" launcher.py
    goto :done
)

rem 2) 退回系统里已安装的 Python（pythonw/pyw 不弹控制台窗口）
where pyw     >nul 2>&1 && (start "" pyw     launcher.py & goto :done)
where pythonw >nul 2>&1 && (start "" pythonw launcher.py & goto :done)
where py      >nul 2>&1 && (start "" py      launcher.py & goto :done)
where python  >nul 2>&1 && (start "" python  launcher.py & goto :done)

rem 3) 都没有：说明 GUI 依赖没装齐，给出手动方案
echo.
echo   [!] 没有找到可用的 Python 运行时，GUI 无法启动。
echo.
echo   GUI 需要 Python + PyQt6，两种解决办法：
echo.
echo   A. 直接在本机 WSL 里跑（不用装 Windows 版 Python）：
echo        cd ~/tianhu-tools
echo        tools/_venv/bin/python main.py
echo.
echo   B. 在 Windows 上跑（需先装 Python，再执行）：
echo        pip install PyQt6
echo      然后重新双击本脚本。
echo.
echo   提示：本目录若是通过 \\wsl.localhost\... 打开的，建议改用 WSL 方式(A)。
echo.
pause

:done
popd
