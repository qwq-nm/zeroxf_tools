@echo off
rem geshell —— zeroxf 工具箱 AI/CLI 统一入口（Windows）
rem 用法: geshell list / geshell <工具名> [参数...]
python "%~dp0ai\launch.py" %*
