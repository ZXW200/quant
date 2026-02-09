"""
RSI 超买超卖策略。

原理:
    RSI (Relative Strength Index) 衡量价格动量的强弱。
    RSI < 超卖线 (默认30): 市场超卖，可能反弹 -> 买入
    RSI > 超买线 (默认70): 市场超买，可能回调 -> 卖出

适合震荡行情，趋势行情中可能频繁止损。
"""

from .base import Strategy
from .indicators import rsi as calc_rsi


class RSIStrategy(Strategy):
    """
    RSI 超买超卖策略。

    参数:
        period: RSI 计算周期，默认 14
        oversold: 超卖阈值，默认 30（RSI 低于此值买入）
        overbought: 超买阈值，默认 70（RSI 高于此值卖出）

    使用示例:
        strategy = RSIStrategy(period=14, oversold=30, overbought=70)
    """

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0
    ):
        super().__init__(name=f"RSI策略({period})")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.rsi_series = None

    def init(self) -> None:
        """预计算 RSI 序列"""
        data = self.ctx.data
        self.rsi_series = calc_rsi(data['close'], self.period)

    def on_bar(self, bar) -> None:
        """
        交易逻辑:
        - RSI 低于超卖线 + 无持仓 -> 买入
        - RSI 高于超买线 + 有持仓 -> 卖出
        """
        idx = self.ctx.current_idx
        if idx < self.period:
            return

        current_rsi = self.rsi_series.iloc[idx]

        # RSI 超卖 -> 买入
        if current_rsi < self.oversold and self.position == 0:
            self.buy()

        # RSI 超买 -> 卖出
        elif current_rsi > self.overbought and self.position > 0:
            self.sell()
