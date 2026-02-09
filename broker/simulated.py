"""
模拟经纪商（回测专用）。
模拟市价单和限价单的执行，包含滑点和手续费计算。
"""

from typing import Optional
from ..engine.event import FillEvent
from .base import Broker


class SimulatedBroker(Broker):
    """
    模拟经纪商。

    功能:
        - 市价单: 以当前K线收盘价成交（含滑点）
        - 限价单: 检查当日价格范围是否触及限价
        - 资金检查: 验证是否有足够资金/持仓
    """

    def __init__(self):
        self._order_count: int = 0

    def execute_order(self, order, current_bar, portfolio) -> Optional[FillEvent]:
        """
        模拟订单执行。

        参数:
            order: OrderEvent
            current_bar: 当前K线 pd.Series (含 open/high/low/close/volume)
            portfolio: Portfolio 组合管理器
        """
        self._order_count += 1

        # 1. 确定基础成交价
        if order.order_type == "MARKET":
            fill_price = current_bar['close']
        elif order.order_type == "LIMIT":
            if order.direction == "BUY":
                # 买入限价单：限价 >= 当日最低价才能成交
                if order.price < current_bar['low']:
                    return None
                fill_price = min(order.price, current_bar['close'])
            else:
                # 卖出限价单：限价 <= 当日最高价才能成交
                if order.price > current_bar['high']:
                    return None
                fill_price = max(order.price, current_bar['close'])
        else:
            return None

        # 2. 应用滑点
        actual_price = portfolio.calculate_slippage(fill_price, order.direction)

        # 3. 计算手续费
        commission = portfolio.calculate_commission(
            actual_price, order.quantity, order.direction
        )

        # 4. 资金/持仓检查
        if order.direction == "BUY":
            cost = actual_price * order.quantity + commission
            if cost > portfolio.cash:
                return None  # 资金不足
        elif order.direction == "SELL":
            if order.quantity > portfolio.position:
                return None  # 持仓不足

        # 5. 生成成交事件
        slippage_cost = abs(actual_price - fill_price) * order.quantity
        return FillEvent(
            datetime=order.datetime,
            symbol=order.symbol,
            direction=order.direction,
            quantity=order.quantity,
            fill_price=actual_price,
            commission=commission,
            slippage_cost=slippage_cost
        )
