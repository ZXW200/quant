"""
双均线交叉策略 (SMA Crossover)。

原理:
    短期均线从下方穿越长期均线（金叉）-> 买入
    短期均线从上方穿越长期均线（死叉）-> 卖出

这是最经典的趋势跟踪策略之一，适合作为入门学习。
"""

from .base import Strategy
from .indicators import sma


class SMACrossStrategy(Strategy):
    """
    双均线交叉策略。

    参数:
        short_period: 短期均线周期，默认 5（代表5日均线）
        long_period: 长期均线周期，默认 20（代表20日均线）

    使用示例:
        strategy = SMACrossStrategy(short_period=5, long_period=20)
    """

    def __init__(self, short_period: int = 5, long_period: int = 20):
        super().__init__(name=f"SMA交叉策略({short_period}/{long_period})")
        self.short_period = short_period
        self.long_period = long_period
        self.sma_short = None
        self.sma_long = None

    def init(self) -> None:
        """预计算两条均线（向量化计算，只算一次）"""
        data = self.ctx.data
        self.sma_short = sma(data['close'], self.short_period)
        self.sma_long = sma(data['close'], self.long_period)

    def on_bar(self, bar) -> None:
        """
        每根K线的判断逻辑:
        1. 等待长期均线有足够数据
        2. 比较当前和前一根K线的均线关系
        3. 金叉 + 无持仓 -> 买入
        4. 死叉 + 有持仓 -> 卖出
        """
        idx = self.ctx.current_idx
        # 等待均线数据充分
        if idx < self.long_period:
            return

        # 当前均线值
        short_now = self.sma_short.iloc[idx]
        long_now = self.sma_long.iloc[idx]
        # 前一根K线的均线值
        short_prev = self.sma_short.iloc[idx - 1]
        long_prev = self.sma_long.iloc[idx - 1]

        # 金叉: 短均线从下方穿越长均线
        if short_prev <= long_prev and short_now > long_now:
            if self.position == 0:
                self.buy()  # 全仓买入

        # 死叉: 短均线从上方穿越长均线
        elif short_prev >= long_prev and short_now < long_now:
            if self.position > 0:
                self.sell()  # 卖出全部
