@echo off
setlocal enabledelayedexpansion
mode con cols=94 lines=30&color 0a&title 创建zeroxf工具箱-社区版V4.0一键启动脚本快捷方式
echo.
echo One-Fox安全团队
echo  官网：https://www.one-fox.cn/  
echo  微信公众号：狐狸说安全
echo  By.狐狸
echo  GitHub官方地址：https://github.com/One-Fox-Security-Team/One-Fox-T00ls
echo.
echo [+] 获得当前路径:%~dp0
echo.

:: 设置vbs文件和快捷方式名称
set "path=%~dp0zeroxf工具箱-社区版V4.0.vbs"
set "LinkName=zeroxf工具箱-社区版V4.0"

:: 检查选择的vbs文件是否存在
if exist "!path!" (
    echo [+] 发现zeroxf工具箱-社区版V4.0一键启动脚本!
    echo.
    echo [+] 启动脚本路径：
    echo [+] !path!
    echo.
    goto :creat
) else (
    echo [-] 注意,未发现启动脚本zeroxf工具箱-社区版V4.0.vbs，请注意是否改名,程序退出... 
    echo.
    pause
    exit /b
)

:creat
echo [+] 开始创建快捷方式...
echo.
rem 设置程序的完整路径(必要)
set Program=!path!
rem 程序工作路径
set WorkDir=%~dp0
rem 设置快捷方式说明
set Desc=zeroxf工具箱-社区版V4.0一键启动_by.狐狸
rem 设置快捷方式图标
set icon=%~dp0config\fox.ico

if not defined WorkDir call:GetWorkDir "%Program%"
(echo Set WshShell=CreateObject("WScript.Shell"^)
echo strDesKtop=WshShell.SpecialFolders("DesKtop"^)
echo Set oShellLink=WshShell.CreateShortcut(strDesKtop^&"\%LinkName%.lnk"^)
echo oShellLink.TargetPath="%Program%"
echo oShellLink.WorkingDirectory="%WorkDir%"
echo oShellLink.WindowStyle=1
echo oShellLink.Description="%Desc%"
echo oShellLink.IconLocation="%icon%"
echo oShellLink.Save)>makelnk.vbs

echo [+] 桌面快捷方式创建成功!!
echo.
start explorer "https://www.one-fox.cn/"
echo.
makelnk.vbs
del /f /q makelnk.vbs
pause
goto :eof

:GetWorkDir
set WorkDir=%~dp1
set WorkDir=%WorkDir:~0,-1%