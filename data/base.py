"""
数据加载器抽象基类。
所有数据源（A股、美股等）必须继承 DataLoader 并实现 load() 方法。
统一返回格式：DatetimeIndex 的 DataFrame，列名为 ['open', 'high', 'low', 'close', 'volume']
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Iterator
import pandas as pd


@dataclass
class BarData:
    """单根K线数据的标准化容器"""
    datetime: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: Optional[float] = None  # 成交额（A股特有）


class DataLoader(ABC):
    """
    数据加载器抽象基类。

    使用方法:
        loader = AStockData()   # 或 USStockData()
        df = loader.load("600519", "2020-01-01", "2024-01-01")
    """

    # 标准列名
    REQUIRED_COLUMNS = ['open', 'high', 'low', 'close', 'volume']

    @abstractmethod
    def load(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq"
    ) -> pd.DataFrame:
        """
        加载历史行情数据。

        参数:
            symbol: 股票代码，如 "600519"（A股）或 "AAPL"（美股）
            start_date: 开始日期，格式 "YYYY-MM-DD"
            end_date: 结束日期，格式 "YYYY-MM-DD"
            adjust: 复权类型 "qfq"(前复权) / "hfq"(后复权) / ""(不复权)

        返回:
            pd.DataFrame，DatetimeIndex，列: open/high/low/close/volume
        """
        pass

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        """验证并标准化 DataFrame 格式"""
        # 检查必需列
        for col in self.REQUIRED_COLUMNS:
            if col not in df.columns:
                raise ValueError(f"缺少必需列: {col}")

        # 确保索引为 DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("索引必须为 DatetimeIndex")

        # 按日期升序排序
        df = df.sort_index()

        # 去除 NaN 行
        df = df.dropna(subset=self.REQUIRED_COLUMNS)

        # 确保数值类型
        for col in self.REQUIRED_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        return df

    def to_bar_iterator(self, df: pd.DataFrame) -> Iterator[BarData]:
        """将 DataFrame 转换为 BarData 逐行迭代器"""
        for idx, row in df.iterrows():
            yield BarData(
                datetime=idx,
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=row['volume'],
                amount=row.get('amount')
            )
