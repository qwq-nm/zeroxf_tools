Set ws  = CreateObject("Wscript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)

' zeroxf 工具箱 - GUI 启动器
' 依次尝试：tools/_venv（provision_tools.py --gui 装的 PyQt6）-> 自带便携 Python
' 都找不到时弹窗提示，不再像旧版那样用 vbhide 静默失败
venvPy     = base & "\tools\_venv\Scripts\pythonw.exe"
portablePy = base & "\python3\pythonw.exe"
systemPy   = ""

If fso.FileExists(venvPy) Then
    systemPy = venvPy
ElseIf fso.FileExists(portablePy) Then
    systemPy = portablePy
Else
    ' 退回 PATH 里的 pythonw
    On Error Resume Next
    systemPy = ws.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\pythonw.exe"
    If Not fso.FileExists(systemPy) Then
        systemPy = ""
        MsgBox "[!] 没有找到可用的 Python 运行时，GUI 无法启动。" & vbCrLf & vbCrLf & _
               "本机 Windows 未安装 Python/PyQt6，推荐直接用 WSL 启动（免安装）：" & vbCrLf & vbCrLf & _
               "    wsl.exe -d Ubuntu -- bash -lc ""cd ~/tianhu-tools && tools/_venv/bin/python main.py""" & vbCrLf & vbCrLf & _
               "或双击桌面上的「启动工具箱.bat」（走 WSL 的启动器）。", 48, "zeroxf 工具箱"
        WScript.Quit 1
    End If
End If

ws.CurrentDirectory = base
ws.Run """" & systemPy & """ main.py", 1, False
