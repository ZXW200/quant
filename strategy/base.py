"""
策略抽象基类和策略运行上下文。

编写自己的策略只需继承 Strategy 并实现两个方法:
    init()   - 初始化，预计算指标
    on_bar() - 每根K线的交易逻辑

示例:
    class MyStrategy(Strategy):
        def init(self):
            self.sma = sma(self.ctx.data['close'], 20)

        def on_bar(self, bar):
            if bar['close'] > self.sma.iloc[self.ctx.current_idx]:
                self.buy()
            elif self.position > 0:
                self.sell()
"""

from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd

from ..engine.event import SignalEvent


class Strategy(ABC):
    """
    策略抽象基类。
    用户继承此类，实现 init() 和 on_bar() 即可。
    """

    def __init__(self, name: str = "BaseStrategy"):
        self.name: str = name
        self._context: Optional['StrategyContext'] = None

    def set_context(self, context: 'StrategyContext') -> None:
        """由引擎调用，注入策略运行时上下文"""
        self._context = context

    @property
    def ctx(self) -> 'StrategyContext':
        """策略上下文的快捷访问"""
        return self._context

    @abstractmethod
    def init(self) -> None:
        """
        策略初始化，在回测开始前调用一次。
        在此方法中预计算技术指标。
        """
        pass

    @abstractmethod
    def on_bar(self, bar) -> None:
        """
        每根K线触发的回调，策略核心逻辑所在。

        参数:
            bar: pd.Series，当前K线数据，包含 open/high/low/close/volume
                 bar.name 为当前日期 (pd.Timestamp)
        """
        pass

    def on_order_filled(self, fill_event) -> None:
        """订单成交回调（可选覆写）"""
        pass

    # ---- 便捷下单方法 ----

    def buy(
        self,
        volume: int = 0,
        price: Optional[float] = None,
        order_type: str = "MARKET"
    ) -> None:
        """
        发出买入信号。

        参数:
            volume: 买入数量（0=自动计算全仓）
            price: 限价单价格（市价单不需要）
            order_type: "MARKET"=市价单, "LIMIT"=限价单
        """
        bar = self._context.get_current_bar()
        signal = SignalEvent(
            datetime=bar.name,
            symbol=self._context._engine.symbol,
            direction="BUY",
            volume=volume,
            order_type=order_type,
            limit_price=price
        )
        self._context._engine.event_queue.append(signal)

    def sell(
        self,
        volume: int = 0,
        price: Optional[float] = None,
        order_type: str = "MARKET"
    ) -> None:
        """
        发出卖出信号。

        参数:
            volume: 卖出数量（0=卖出全部持仓）
            price: 限价单价格
            order_type: "MARKET"=市价单, "LIMIT"=限价单
        """
        bar = self._context.get_current_bar()
        # 默认卖出全部持仓
        if volume <= 0:
            volume = self.position
        signal = SignalEvent(
            datetime=bar.name,
            symbol=self._context._engine.symbol,
            direction="SELL",
            volume=volume,
            order_type=order_type,
            limit_price=price
        )
        self._context._engine.event_queue.append(signal)

    @property
    def position(self) -> int:
        """当前持仓数量"""
        return self._context.get_position()

    @property
    def cash(self) -> float:
        """当前可用资金"""
        return self._context.get_cash()


class StrategyContext:
    """
    策略运行时上下文。
    由引擎创建，为策略提供数据访问和交易能力。
    这是策略与引擎之间的桥梁。
    """

    def __init__(self, engine):
        self._engine = engine
        self._data: pd.DataFrame = engine.data
        self._current_idx: int = 0

    @property
    def data(self) -> pd.DataFrame:
        """获取完整的历史数据（用于 init 阶段预计算指标）"""
        return self._data

    @property
    def current_idx(self) -> int:
        """当前K线在数据中的索引位置"""
        return self._current_idx

    def get_current_bar(self) -> pd.Series:
        """获取当前K线数据"""
        return self._data.iloc[self._current_idx]

    def get_history(self, n: int = 1) -> pd.DataFrame:
        """获取最近 n 根K线的历史数据（含当前bar）"""
        start = max(0, self._current_idx - n + 1)
        end = self._current_idx + 1
        return self._data.iloc[start:end]

    def get_position(self) -> int:
        """获取当前持仓数量"""
        return self._engine.portfolio.position

    def get_cash(self) -> float:
        """获取当前可用资金"""
        return self._engine.portfolio.cash
