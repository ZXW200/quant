"""
一键打包量化监控系统为独立 exe。

使用方法:
    py build_exe.py

打包后生成:
    dist/量化监控.exe   (单文件可执行程序)

在任何 Windows 电脑上双击即可运行，无需安装 Python。
"""

import subprocess
import sys
import os

BASE = os.path.dirname(os.path.abspath(__file__))


def main():
    # 1. 确保安装 pyinstaller
    print("=" * 50)
    print("  量化监控系统 - 打包工具")
    print("=" * 50)
    print()
    print("[1/3] 检查 PyInstaller ...")
    try:
        import PyInstaller
        print(f"      已安装 PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("      正在安装 PyInstaller ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("      PyInstaller 安装完成")

    # 2. 构建 PyInstaller 命令
    print()
    print("[2/3] 开始打包 (这可能需要几分钟) ...")
    print()

    web_templates = os.path.join(BASE, 'web', 'templates')
    web_static = os.path.join(BASE, 'web', 'static')
    strategy_dir = os.path.join(BASE, 'strategy')
    prediction_file = os.path.join(BASE, 'prediction.py')
    storage_file = os.path.join(BASE, 'storage.py')
    init_file = os.path.join(BASE, '__init__.py')

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                              # 打成单个 exe
        "--name", "量化监控",                      # exe 名称
        "--icon", "NONE",                         # 无图标
        # 添加数据文件
        "--add-data", f"{web_templates};web/templates",
        "--add-data", f"{strategy_dir};quant_backtest/strategy",
        "--add-data", f"{prediction_file};quant_backtest",
        "--add-data", f"{storage_file};quant_backtest",
        "--add-data", f"{init_file};quant_backtest",
        # 隐式导入
        "--hidden-import", "flask",
        "--hidden-import", "flask_socketio",
        "--hidden-import", "engineio.async_drivers.threading",
        "--hidden-import", "yfinance",
        "--hidden-import", "akshare",
        "--hidden-import", "sklearn",
        "--hidden-import", "sklearn.ensemble",
        "--hidden-import", "sklearn.model_selection",
        "--hidden-import", "pandas",
        "--hidden-import", "numpy",
        "--hidden-import", "quant_backtest",
        "--hidden-import", "quant_backtest.strategy",
        "--hidden-import", "quant_backtest.strategy.indicators",
        "--hidden-import", "quant_backtest.storage",
        "--hidden-import", "quant_backtest.prediction",
        # 排除不需要的大型库（显著减小 exe 体积）
        "--exclude-module", "torch",
        "--exclude-module", "torchvision",
        "--exclude-module", "torchaudio",
        "--exclude-module", "matplotlib",
        "--exclude-module", "mplfinance",
        "--exclude-module", "tkinter",
        "--exclude-module", "PIL",
        "--exclude-module", "IPython",
        "--exclude-module", "notebook",
        "--exclude-module", "pytest",
        "--exclude-module", "tensorboard",
        "--exclude-module", "tqdm",
        "--exclude-module", "tabulate",
        # 不弹出控制台窗口（改为后台，浏览器访问）
        # "--noconsole",    # 注释掉: 保留控制台窗口方便查看日志
        "--distpath", os.path.join(BASE, "dist"),
        "--workpath", os.path.join(BASE, "build"),
        "--specpath", BASE,
        os.path.join(BASE, "web_server.py"),
    ]

    # 如果 web/static 目录存在才添加
    if os.path.isdir(web_static):
        idx = cmd.index("--hidden-import")
        cmd.insert(idx, f"{web_static};web/static")
        cmd.insert(idx, "--add-data")

    subprocess.check_call(cmd)

    # 3. 完成
    exe_path = os.path.join(BASE, "dist", "量化监控.exe")
    print()
    print("=" * 50)
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / 1024 / 1024
        print(f"  打包成功!")
        print(f"  文件: {exe_path}")
        print(f"  大小: {size_mb:.1f} MB")
        print()
        print("  使用方法:")
        print("    1. 把 量化监控.exe 复制到任意电脑")
        print("    2. 双击运行")
        print("    3. 打开浏览器访问 http://127.0.0.1:5000")
        print()
        print("  数据库 (data.db) 会自动创建在 exe 同目录下")
    else:
        print("  打包可能失败，请检查上方日志")
    print("=" * 50)


if __name__ == '__main__':
    main()
