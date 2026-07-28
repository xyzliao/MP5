@echo off
REM ============================================================
REM MP5录播器 Windows版 — 构建脚本
REM 将 Python 脚本打包为 Windows 可执行文件 (.exe)
REM ============================================================

echo ========================================
echo   MP5录播器 Windows版 构建脚本
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] 检查依赖...
pip install pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [警告] 安装 PyInstaller 失败，尝试继续...
)

echo [2/4] 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist MP5Player.spec del MP5Player.spec

echo [3/4] 打包中...
pyinstaller --onefile --windowed --name MP5Player ^
    --add-data "mp5_box.py;." ^
    --add-data "mp5_parser.py;." ^
    --add-data "sync_engine.py;." ^
    --add-data "exporters.py;." ^
    --add-data "__init__.py;." ^
    mp5_player.py

if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

echo [4/4] 构建完成!
echo.
echo 可执行文件位于: dist\MP5Player.exe
echo.
pause