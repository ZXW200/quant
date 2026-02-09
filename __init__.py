"""
QuantBacktest - Python 量化交易策略回测框架

支持 A股 和 美股 的事件驱动回测。
内置均线交叉、RSI、布林带三种经典策略。

快速开始:
    from quant_backtest import Engine, SMAStrategy, AStockData

    data = AStockData().load("600519", "2020-01-01", "2024-01-01")
    engine = Engine(data, SMAStrategy(), capital=100000, market="A", symbol="600519")
    result = engine.run()
    result.report()
    result.plot()
"""

__version__ = "0.1.0"

# 核心导出
from .engine.engine import BacktestEngine as Engine
from .data.astock import AStockData
from .data.us_stock import USStockData
from .strategy.base import Strategy
from .strategy.sma_cross import SMACrossStrategy as SMAStrategy
from .strategy.rsi_strategy import RSIStrategy
from .strategy.bollinger_strategy import BollingerStrategy
from .broker.simulated import SimulatedBroker
from .analysis.result import BacktestResult

__all__ = [
    'Engine',
    'AStockData',
    'USStockData',
    'Strategy',
    'SMAStrategy',
    'RSIStrategy',
    'BollingerStrategy',
    'SimulatedBroker',
    'BacktestResult',
]
