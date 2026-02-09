"""
事件驱动回测引擎。

工作流程:
    1. 逐根推送 K 线 -> MarketEvent
    2. Strategy.on_bar() 处理 MarketEvent -> 可能产生 SignalEvent
    3. 引擎将 SignalEvent 转换为 OrderEvent
    4. Broker 执行 OrderEvent -> 产生 FillEvent
    5. Portfolio 处理 FillEvent，更新持仓和资金

使用方法:
    engine = BacktestEngine(data, strategy, capital=100000)
    result = engine.run()
    result.report()
    result.plot()
"""

from collections import deque
from typing import Optional
import pandas as pd

from .event import EventType, MarketEvent, SignalEvent, OrderEvent, FillEvent
from .portfolio import Portfolio
from ..broker.base import Broker
from ..broker.simulated import SimulatedBroker


class BacktestEngine:
    """
    事件驱动回测引擎。

    参数:
        data: 标准化的 OHLCV DataFrame (DatetimeIndex)
        strategy: 策略实例（继承自 Strategy 基类）
        capital: 初始资金，默认 10 万
        commission: 佣金费率，默认万三
        slippage: 滑点比例，默认千一
        broker: Broker 实例，默认使用 SimulatedBroker
        market: "A"=A股, "US"=美股
        symbol: 股票代码
    """

    def __init__(
        self,
        data: pd.DataFrame,
        strategy,
        capital: float = 100000.0,
        commission: float = 0.0003,
        slippage: float = 0.001,
        broker: Optional[Broker] = None,
        market: str = "A",
        symbol: str = "UNKNOWN"
    ):
        self.data = data
        self.strategy = strategy
        self.symbol = symbol
        self.market = market

        # 事件队列
        self.event_queue: deque = deque()

        # 组合管理器
        self.portfolio = Portfolio(
            initial_capital=capital,
            commission_rate=commission,
            slippage=slippage,
            market=market
        )

        # 经纪商
        self.broker = broker or SimulatedBroker()

        # 策略上下文（延迟导入避免循环引用）
        from ..strategy.base import StrategyContext
        self._context = StrategyContext(self)
        self.strategy.set_context(self._context)

    def run(self):
        """
        执行回测主循环。

        返回:
            BacktestResult: 封装了所有回测结果的对象
        """
        # 延迟导入避免循环引用
        from ..analysis.result import BacktestResult

        # 1. 策略初始化（预计算指标等）
        self.strategy.init()

        # 2. 逐根K线推送
        total_bars = len(self.data)
        for idx in range(total_bars):
            self._context._current_idx = idx
            bar = self.data.iloc[idx]

            # 2a. 生成市场事件
            market_event = MarketEvent(datetime=bar.name)
            self.event_queue.append(market_event)

            # 2b. 处理事件队列（可能产生连锁事件）
            while self.event_queue:
                event = self.event_queue.popleft()
                self._process_event(event, bar)

            # 2c. 更新当日权益
            self.portfolio.update_market_value(
                datetime=bar.name,
                close_price=bar['close']
            )

        # 3. 构建回测结果
        return BacktestResult(
            equity_curve=self.portfolio.get_equity_df(),
            trades=self.portfolio.get_trades_df(),
            initial_capital=self.portfolio.initial_capital,
            data=self.data,
            strategy_name=self.strategy.name,
            symbol=self.symbol
        )

    def _process_event(self, event, current_bar) -> None:
        """根据事件类型分发处理"""
        if event.type == EventType.MARKET:
            self._handle_market(event, current_bar)
        elif event.type == EventType.SIGNAL:
            self._handle_signal(event, current_bar)
        elif event.type == EventType.ORDER:
            self._handle_order(event, current_bar)
        elif event.type == EventType.FILL:
            self._handle_fill(event)

    def _handle_market(self, event, bar) -> None:
        """处理市场事件：调用策略的 on_bar"""
        self.strategy.on_bar(bar)

    def _handle_signal(self, signal: SignalEvent, bar) -> None:
        """处理信号事件：转换为订单事件"""
        quantity = signal.volume
        if quantity <= 0:
            # 如果信号未指定数量，自动计算
            quantity = self._calculate_order_quantity(signal, bar)

        if quantity <= 0:
            return

        order = OrderEvent(
            datetime=signal.datetime,
            symbol=signal.symbol,
            direction=signal.direction,
            order_type=signal.order_type,
            quantity=quantity,
            price=signal.limit_price
        )
        self.event_queue.append(order)

    def _handle_order(self, order: OrderEvent, bar) -> None:
        """处理订单事件：交给 Broker 执行"""
        fill = self.broker.execute_order(order, bar, self.portfolio)
        if fill is not None:
            self.event_queue.append(fill)

    def _handle_fill(self, fill: FillEvent) -> None:
        """处理成交事件：更新组合"""
        self.portfolio.execute_fill(fill)
        self.strategy.on_order_filled(fill)

    def _calculate_order_quantity(self, signal: SignalEvent, bar) -> int:
        """
        根据信号计算下单数量。

        买入: 使用 95% 可用资金全仓买入
        卖出: 卖出全部持仓
        A股: 按100股(一手)取整
        """
        if signal.direction == "SELL":
            return self.portfolio.position

        # 买入数量计算
        available = self.portfolio.cash * 0.95  # 预留 5% 资金
        price = bar['close']
        if price <= 0:
            return 0

        quantity = int(available / price)

        # A股按手取整（100股的整数倍）
        if self.market == "A":
            quantity = (quantity // 100) * 100

        return max(quantity, 0)
