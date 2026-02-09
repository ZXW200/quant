"""
布林带突破策略 (Bollinger Bands)。

原理:
    布林带由三条线组成: 上轨、中轨(SMA)、下轨。
    价格触及下轨 -> 价格被低估，买入
    价格触及上轨 -> 价格被高估，卖出

    布林带会根据波动率自动调整宽度:
    - 波动大时带宽扩大
    - 波动小时带宽收窄（可能预示即将突破）
"""

from .base import Strategy
from .indicators import bollinger_bands


class BollingerStrategy(Strategy):
    """
    布林带突破策略。

    参数:
        period: 中轨均线周期，默认 20
        num_std: 标准差倍数，默认 2.0

    使用示例:
        strategy = BollingerStrategy(period=20, num_std=2.0)
    """

    def __init__(self, period: int = 20, num_std: float = 2.0):
        super().__init__(name=f"布林带策略({period}, {num_std})")
        self.period = period
        self.num_std = num_std
        self.upper = None
        self.middle = None
        self.lower = None

    def init(self) -> None:
        """预计算布林带三条线"""
        data = self.ctx.data
        self.upper, self.middle, self.lower = bollinger_bands(
            data['close'], self.period, self.num_std
        )

    def on_bar(self, bar) -> None:
        """
        交易逻辑:
        - 收盘价 <= 下轨 + 无持仓 -> 买入（价格被低估）
        - 收盘价 >= 上轨 + 有持仓 -> 卖出（价格被高估）
        """
        idx = self.ctx.current_idx
        if idx < self.period:
            return

        close = bar['close']
        upper = self.upper.iloc[idx]
        lower = self.lower.iloc[idx]

        # 价格触及下轨 -> 买入
        if close <= lower and self.position == 0:
            self.buy()

        # 价格触及上轨 -> 卖出
        elif close >= upper and self.position > 0:
            self.sell()
