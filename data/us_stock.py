"""
美股数据加载器，基于 yfinance 库。
从 Yahoo Finance 获取历史行情数据。
"""

import pandas as pd
from .base import DataLoader


class USStockData(DataLoader):
    """
    美股数据加载器。

    使用方法:
        loader = USStockData()
        df = loader.load("AAPL", "2020-01-01", "2024-01-01")
    """

    def load(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq"
    ) -> pd.DataFrame:
        """
        从 yfinance 加载美股历史数据。

        参数:
            symbol: 美股代码，如 "AAPL", "MSFT", "GOOGL"
            start_date: "YYYY-MM-DD" 格式
            end_date: "YYYY-MM-DD" 格式
            adjust: 默认自动复权
        """
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError("请安装 yfinance: pip install yfinance")

        # 下载历史数据（auto_adjust=True 自动复权）
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date)

        if df.empty:
            raise ValueError(f"未获取到 {symbol} 的数据，请检查代码和日期范围")

        # yfinance 列名: Open, High, Low, Close, Volume -> 转小写
        df.columns = [c.lower() for c in df.columns]

        # 只保留标准 OHLCV 列
        df = df[self.REQUIRED_COLUMNS]

        # 确保索引名一致
        df.index.name = 'datetime'

        # 去除时区信息（如有）
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        # 验证数据格式
        df = self.validate(df)

        return df
