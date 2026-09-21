@echo off
REM ============================================================
REM MP5录播器 Windows版 — 构建脚本
REM 将 Python 脚本打包为 Windows 可执行文件 (.exe)
REM
REM 与 build.py 完全一致的参数，确保打包结果相同
REM
REM 作者: 大米斗（Aniseedaliao）
REM 版本: 1.0.20
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
python -m pip install --upgrade pip >nul 2>&1
pip install pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [警告] 安装 PyInstaller 失败，尝试继续...
)

echo [2/4] 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist MP5Player.spec del MP5Player.spec

REM 获取脚本所在目录（解决从其他目录运行的问题）
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

echo [3/4] 打包中...
REM 与 build.py 参数完全一致：
REM   --paths          : 让 PyInstaller 在此目录搜索模块
REM   --hidden-import   : 显式声明所有模块（保险）
REM   --collect-submodules : 递归收集子模块
REM
REM 先用 --console 打包，如果有错误会显示在控制台
pyinstaller --onefile --console --name MP5Player ^
    --noconfirm ^
    --clean ^
    --paths "%SCRIPT_DIR%" ^
    --hidden-import mp5_box ^
    --hidden-import mp5_parser ^
    --hidden-import sync_engine ^
    --hidden-import exporters ^
    --hidden-import gpx_importer ^
    --hidden-import track_generator ^
    --hidden-import vlc ^
    --collect-submodules mp5_box ^
    --collect-submodules mp5_parser ^
    --collect-submodules sync_engine ^
    --collect-submodules exporters ^
    --collect-submodules gpx_importer ^
    --collect-submodules track_generator ^
    mp5_player.py

if errorlevel 1 (
    echo.
    echo [错误] 打包失败！请检查上方错误信息
    pause
    exit /b 1
)

echo [4/4] 重新打包（无控制台窗口模式）...
REM 第二阶段：去掉控制台窗口，生成正式发行版
if exist build rmdir /s /q build
del MP5Player.spec
pyinstaller --onefile --windowed --name MP5Player ^
    --noconfirm ^
    --clean ^
    --paths "%SCRIPT_DIR%" ^
    --hidden-import mp5_box ^
    --hidden-import mp5_parser ^
    --hidden-import sync_engine ^
    --hidden-import exporters ^
    --hidden-import gpx_importer ^
    --hidden-import track_generator ^
    --hidden-import vlc ^
    --collect-submodules mp5_box ^
    --collect-submodules mp5_parser ^
    --collect-submodules sync_engine ^
    --collect-submodules exporters ^
    --collect-submodules gpx_importer ^
    --collect-submodules track_generator ^
    mp5_player.py

if errorlevel 1 (
    echo [警告] 无窗口模式打包失败，但控制台版可用
    echo 可执行文件位于: dist\MP5Player.exe
    pause
    exit /b 0
)

echo.
echo 构建完成!
echo.
echo 可执行文件位于: dist\MP5Player.exe
echo.
echo 提示:
echo   - 如果 exe 闪退，请在命令行中运行 dist\MP5Player.exe 查看错误
echo   - 需要安装 VLC 播放器才能内嵌播放视频
echo   - 也可以使用 build.py 进行跨平台构建: python build.py
echo.
pause