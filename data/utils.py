"""
数据工具函数：收益率计算、K线重采样、缺失填充等。
"""

import pandas as pd
import numpy as np


def calc_returns(series: pd.Series, method: str = "simple") -> pd.Series:
    """
    计算收益率序列。

    参数:
        series: 价格序列
        method: "simple"=简单收益率, "log"=对数收益率
    """
    if method == "simple":
        return series.pct_change()
    elif method == "log":
        return np.log(series / series.shift(1))
    else:
        raise ValueError(f"不支持的收益率计算方法: {method}")


def resample_bars(df: pd.DataFrame, freq: str = "W") -> pd.DataFrame:
    """
    K线数据重采样（日线 -> 周线/月线）。

    参数:
        df: OHLCV DataFrame
        freq: "W"=周线, "M"=月线, "Q"=季线
    """
    return df.resample(freq).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()


def fill_missing_dates(df: pd.DataFrame, method: str = "ffill") -> pd.DataFrame:
    """
    填充非交易日缺失数据。

    参数:
        df: OHLCV DataFrame
        method: "ffill"=前值填充, "bfill"=后值填充
    """
    full_idx = pd.date_range(df.index.min(), df.index.max(), freq='D')
    df = df.reindex(full_idx)
    if method == "ffill":
        df = df.ffill()
    elif method == "bfill":
        df = df.bfill()
    return df.dropna()
