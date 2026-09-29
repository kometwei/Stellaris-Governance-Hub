@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PYTHON_CMD="
where py >nul 2>nul && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD where python >nul 2>nul && set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
    echo [错误] 未找到 Python 3。请先安装 Python 3.10 或更高版本。
    echo 下载地址: https://www.python.org/downloads/windows/
    pause
    exit /b 1
)

echo 正在读取当前 Stellaris 播放集并生成本地定制版……
%PYTHON_CMD% tools\build_release_profiles.py local --install
if errorlevel 1 (
    echo.
    echo [失败] 生成器没有完成，请保留上方错误信息并前往仓库反馈。
    pause
    exit /b 1
)

echo.
echo [完成] 请打开 Paradox Launcher，启用：
echo [本地生成] 星政中枢
echo 请不要同时启用创意工坊核心版。
pause
