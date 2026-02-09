"""
技术指标计算模块。
所有指标函数接收 pd.Series，返回 pd.Series，便于向量化预计算。
"""

import pandas as pd
import numpy as np
from typing import Tuple


def sma(series: pd.Series, period: int) -> pd.Series:
    """
    简单移动平均线 (Simple Moving Average)。

    参数:
        series: 价格序列（通常用收盘价）
        period: 均线周期

    示例:
        sma5 = sma(df['close'], 5)   # 5日均线
        sma20 = sma(df['close'], 20) # 20日均线
    """
    return series.rolling(window=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """
    指数移动平均线 (Exponential Moving Average)。
    对近期数据赋予更大权重，比 SMA 更灵敏。
    """
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    相对强弱指标 (Relative Strength Index)。

    计算公式:
        RSI = 100 - 100 / (1 + RS)
        RS = 平均上涨幅度 / 平均下跌幅度

    一般认为:
        RSI > 70: 超买区间（可能下跌）
        RSI < 30: 超卖区间（可能上涨）

    参数:
        series: 价格序列
        period: 计算周期，默认14
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def bollinger_bands(
    series: pd.Series,
    period: int = 20,
    num_std: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    布林带 (Bollinger Bands)。

    由三条线组成:
        上轨 = 中轨 + num_std * 标准差
        中轨 = SMA(period)
        下轨 = 中轨 - num_std * 标准差

    价格触及上轨表示可能超买，触及下轨表示可能超卖。

    返回:
        (upper, middle, lower) 三条线的元组
    """
    middle = sma(series, period)
    std = series.rolling(window=period).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    return upper, middle, lower


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    MACD 指标 (Moving Average Convergence Divergence)。

    计算:
        MACD线 = EMA(fast) - EMA(slow)
        信号线 = EMA(MACD线, signal)
        柱状图 = MACD线 - 信号线

    金叉: MACD线上穿信号线 -> 买入信号
    死叉: MACD线下穿信号线 -> 卖出信号

    返回:
        (macd_line, signal_line, histogram)
    """
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_indicator(df: pd.DataFrame, name: str, **kwargs):
    """
    统一指标计算入口。

    参数:
        df: OHLCV DataFrame
        name: 指标名 "SMA", "EMA", "RSI", "BOLL", "MACD"
        **kwargs: 指标参数

    示例:
        sma20 = calculate_indicator(df, "SMA", period=20)
        rsi14 = calculate_indicator(df, "RSI", period=14)
    """
    source = kwargs.pop('source', 'close')
    series = df[source]

    dispatch = {
        'SMA': lambda: sma(series, kwargs.get('period', 20)),
        'EMA': lambda: ema(series, kwargs.get('period', 20)),
        'RSI': lambda: rsi(series, kwargs.get('period', 14)),
        'BOLL': lambda: bollinger_bands(series, **kwargs),
        'MACD': lambda: macd(series, **kwargs),
    }

    func = dispatch.get(name.upper())
    if func is None:
        raise ValueError(f"不支持的指标: {name}，可用: {list(dispatch.keys())}")
    return func()
