"""
A股数据加载器，基于 akshare 库。
使用东方财富接口获取日线历史数据。
"""

import pandas as pd
from .base import DataLoader


class AStockData(DataLoader):
    """
    A股数据加载器。

    使用方法:
        loader = AStockData()
        df = loader.load("600519", "2020-01-01", "2024-01-01")
    """

    # akshare 返回的中文列名 -> 标准英文列名
    COLUMN_MAP = {
        '日期': 'datetime',
        '开盘': 'open',
        '收盘': 'close',
        '最高': 'high',
        '最低': 'low',
        '成交量': 'volume',
        '成交额': 'amount',
    }

    def load(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq"
    ) -> pd.DataFrame:
        """
        从 akshare 加载A股历史数据。

        参数:
            symbol: 6位股票代码，如 "600519"（贵州茅台）
            start_date: "YYYY-MM-DD" 格式
            end_date: "YYYY-MM-DD" 格式
            adjust: "qfq"(前复权) / "hfq"(后复权) / ""(不复权)
        """
        try:
            import akshare as ak
        except ImportError:
            raise ImportError("请安装 akshare: pip install akshare")

        # akshare 日期格式: "YYYYMMDD"
        start_fmt = start_date.replace("-", "")
        end_fmt = end_date.replace("-", "")

        # 调用 akshare 接口获取日K数据
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_fmt,
            end_date=end_fmt,
            adjust=adjust
        )

        # 重命名中文列
        df = df.rename(columns=self.COLUMN_MAP)

        # 设置 DatetimeIndex
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime')

        # 只保留标准列 + 额外的 amount 列
        keep_cols = self.REQUIRED_COLUMNS + ['amount']
        df = df[[c for c in keep_cols if c in df.columns]]

        # 验证数据格式
        df = self.validate(df)

        return df

    @staticmethod
    def search(keyword: str) -> pd.DataFrame:
        """
        根据关键词搜索A股股票代码。

        参数:
            keyword: 股票名称或代码关键词，如 "茅台" 或 "6005"

        返回:
            匹配的股票列表 (代码, 名称)
        """
        try:
            import akshare as ak
        except ImportError:
            raise ImportError("请安装 akshare: pip install akshare")

        spot = ak.stock_zh_a_spot_em()
        mask = (
            spot['名称'].str.contains(keyword, na=False) |
            spot['代码'].str.contains(keyword, na=False)
        )
        result = spot.loc[mask, ['代码', '名称', '最新价']].head(20)
        return result
