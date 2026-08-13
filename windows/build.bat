@echo off
REM ============================================================
REM MP5录播器 Windows版 — 构建脚本
REM 将 Python 脚本打包为 Windows 可执行文件 (.exe)
REM
REM 修复历史问题:
REM   1. 缺少 gpx_importer.py 和 track_generator.py 模块
REM   2. --add-data 改为 --collect-all（让PyInstaller正确收集所有模块）
REM   3. --hidden-import 确保所有动态导入被发现
REM   4. 先用 --console 测试，确认无错后再 --windowed
REM
REM 作者: 大米斗（Aniseedaliao）
REM 版本: 1.0.10
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

echo [1/5] 检查依赖...
python -m pip install --upgrade pip >nul 2>&1
pip install pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [警告] 安装 PyInstaller 失败，尝试继续...
)

echo [2/5] 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist MP5Player.spec del MP5Player.spec

echo [3/5] 打包中（控制台模式，便于排查错误）...
REM 第一阶段：带控制台打包，确保能看到所有错误
REM 所有 .py 模块都放在同一目录，PyInstaller 会自动通过 import 分析发现它们
REM --hidden-import 作为保险，防止动态导入被遗漏
pyinstaller --onefile --console --name MP5Player ^
    --hidden-import mp5_box ^
    --hidden-import mp5_parser ^
    --hidden-import sync_engine ^
    --hidden-import exporters ^
    --hidden-import gpx_importer ^
    --hidden-import track_generator ^
    mp5_player.py

if errorlevel 1 (
    echo.
    echo [错误] 打包失败！请检查上方错误信息
    pause
    exit /b 1
)

echo [4/5] 重新打包（无控制台窗口模式）...
REM 第二阶段：去掉控制台窗口，生成正式发行版
if exist build rmdir /s /q build
del MP5Player.spec
pyinstaller --onefile --windowed --name MP5Player ^
    --hidden-import mp5_box ^
    --hidden-import mp5_parser ^
    --hidden-import sync_engine ^
    --hidden-import exporters ^
    --hidden-import gpx_importer ^
    --hidden-import track_generator ^
    mp5_player.py

if errorlevel 1 (
    echo [警告] 无窗口模式打包失败，但控制台版可用
    echo 可执行文件位于: dist\MP5Player.exe
    pause
    exit /b 0
)

echo [5/5] 构建完成!
echo.
echo 可执行文件位于: dist\MP5Player.exe
echo.
echo 提示:
echo   - 如果 exe 闪退，请在命令行中运行 dist\MP5Player.exe 查看错误
echo   - 需要安装 VLC 播放器才能内嵌播放视频
echo   - 也可以使用 build.py 进行跨平台构建: python build.py
echo.
pause