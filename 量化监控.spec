# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\quant_backtest\\web_server.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\quant_backtest\\web\\templates', 'web/templates'), ('C:\\quant_backtest\\strategy', 'quant_backtest/strategy'), ('C:\\quant_backtest\\prediction.py', 'quant_backtest'), ('C:\\quant_backtest\\storage.py', 'quant_backtest'), ('C:\\quant_backtest\\__init__.py', 'quant_backtest'), ('C:\\quant_backtest\\web\\static', 'web/static')],
    hiddenimports=['flask', 'flask_socketio', 'engineio.async_drivers.threading', 'yfinance', 'akshare', 'sklearn', 'sklearn.ensemble', 'sklearn.model_selection', 'pandas', 'numpy', 'quant_backtest', 'quant_backtest.strategy', 'quant_backtest.strategy.indicators', 'quant_backtest.storage', 'quant_backtest.prediction'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio', 'matplotlib', 'mplfinance', 'tkinter', 'PIL', 'IPython', 'notebook', 'pytest', 'tensorboard', 'tqdm', 'tabulate'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='量化监控',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='NONE',
)
