#!/usr/bin/env python3
"""
MP5录播器 — 跨平台构建脚本
在 Windows / Linux / macOS 上均可运行，使用 PyInstaller 打包为单文件可执行程序

修复的问题:
  1. 原 build.bat 缺少 gpx_importer.py 和 track_generator.py 模块
  2. 原方式用 --add-data 把 .py 当数据文件复制，PyInstaller 无法正确导入
  3. 原方式 --windowed 隐藏了启动错误，exe 闪退无法排查
  4. .bat 只能在 Windows 运行，本脚本可在任意平台运行

用法:
  python build.py              # 默认无控制台窗口
  python build.py --console    # 保留控制台窗口（调试用）
  python build.py --clean      # 清理后构建

作者: 大米斗（Aniseedaliao）
版本: 1.0.20
"""

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path

# 脚本所在目录（windows/）
SCRIPT_DIR = Path(__file__).parent.resolve()

# 所有需要确保被 PyInstaller 发现的模块
HIDDEN_IMPORTS = [
    'mp5_box',
    'mp5_parser',
    'sync_engine',
    'exporters',
    'gpx_importer',
    'track_generator',
]

# 可选的第三方依赖（可能需要 hidden-import）
OPTIONAL_IMPORTS = [
    'vlc',       # python-vlc（可选，缺失时回退到系统播放器）
]

def check_python():
    """检查 Python 版本"""
    version = sys.version_info
    if version < (3, 8):
        print(f'[错误] 需要 Python 3.8+，当前 {version.major}.{version.minor}')
        sys.exit(1)
    print(f'[OK] Python {platform.python_version()} ({platform.machine()})')


def check_pyinstaller():
    """检查 PyInstaller 是否安装"""
    try:
        import PyInstaller
        print(f'[OK] PyInstaller {PyInstaller.__version__}')
    except ImportError:
        print('[...] 安装 PyInstaller...')
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
        print('[OK] PyInstaller 已安装')


def clean_build_artifacts():
    """清理旧的构建产物"""
    dirs_to_clean = ['build', 'dist']
    files_to_clean = ['MP5Player.spec']

    for d in dirs_to_clean:
        path = SCRIPT_DIR / d
        if path.exists():
            print(f'[清理] {path}')
            shutil.rmtree(path)

    for f in files_to_clean:
        path = SCRIPT_DIR / f
        if path.exists():
            path.unlink()
            print(f'[清理] {path}')


def build(console_mode=False):
    """
    使用 PyInstaller 构建

    @param console_mode: True=保留控制台窗口（调试用），False=无窗口（发行版）
    """
    entry_script = SCRIPT_DIR / 'mp5_player.py'
    if not entry_script.exists():
        print(f'[错误] 入口文件不存在: {entry_script}')
        sys.exit(1)

    # 构建 PyInstaller 命令
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--name', 'MP5Player',
        '--noconfirm',
        '--clean',
    ]

    if console_mode:
        cmd.append('--console')
    else:
        cmd.append('--windowed')

    # 确保所有模块被发现
    for mod in HIDDEN_IMPORTS:
        cmd.extend(['--hidden-import', mod])

    # 可选依赖（缺失不报错）
    for mod in OPTIONAL_IMPORTS:
        cmd.extend(['--hidden-import', mod])

    # 添加工作目录到 Python 路径
    cmd.extend(['--paths', str(SCRIPT_DIR)])

    # 收集 mp5_box 等模块的二进制依赖（如果有）
    for mod in HIDDEN_IMPORTS:
        cmd.extend(['--collect-submodules', mod])

    # 入口文件
    cmd.append(str(entry_script))

    # 添加图标（如果存在）
    icon_path = SCRIPT_DIR / 'mp5player.ico'
    if icon_path.exists():
        cmd.extend(['--icon', str(icon_path)])

    # 平台特定参数
    if platform.system() == 'Windows':
        # Windows: 确保不使用 UPX（有时会导致问题）
        pass
    elif platform.system() == 'Darwin':
        # macOS: 设置最低系统版本
        pass

    # 打印命令
    print(f'[构建] 运行: {" ".join(cmd[:6])}...')
    print(f'[构建] 模式: {"控制台" if console_mode else "无窗口"}')
    print(f'[构建] 平台: {platform.system()} {platform.machine()}')

    # 执行
    result = subprocess.run(cmd, cwd=str(SCRIPT_DIR))

    if result.returncode != 0:
        print(f'[错误] PyInstaller 打包失败 (exit code: {result.returncode})')
        if not console_mode:
            print('[提示] 请尝试: python build.py --console 查看详细错误')
        sys.exit(1)

    # 检查输出
    if platform.system() == 'Windows':
        exe_path = SCRIPT_DIR / 'dist' / 'MP5Player.exe'
    else:
        exe_path = SCRIPT_DIR / 'dist' / 'MP5Player'

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f'\n[完成] 可执行文件: {exe_path}')
        print(f'[完成] 文件大小: {size_mb:.1f} MB')
        print(f'[完成] 模式: {"控制台" if console_mode else "无窗口"}')
    else:
        print(f'[警告] 预期的输出文件不存在: {exe_path}')


def main():
    import argparse
    parser = argparse.ArgumentParser(description='MP5录播器构建脚本')
    parser.add_argument('--console', action='store_true',
                        help='保留控制台窗口（调试模式，可看到错误输出）')
    parser.add_argument('--clean', action='store_true',
                        help='清理旧构建产物后重新构建')
    parser.add_argument('--no-clean', action='store_true',
                        help='不清理旧构建产物')
    args = parser.parse_args()

    print('=' * 50)
    print('  MP5录播器构建脚本')
    print('=' * 50)
    print()

    check_python()
    check_pyinstaller()

    # 清理
    if not args.no_clean:
        clean_build_artifacts()

    # 构建
    build(console_mode=args.console)

    print()
    print('提示:')
    print('  - 需要 VLC 播放器才能内嵌播放视频')
    print('  - 如果 exe 闪退，用 --console 模式重新构建排查')
    print('  - Windows: 双击 dist/MP5Player.exe 运行')
    print('  - Linux/macOS: ./dist/MP5Player 运行')
    print()


if __name__ == '__main__':
    main()