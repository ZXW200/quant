"""
Broker 抽象基类。
定义订单执行的统一接口，回测和实盘均需实现此接口。
"""

from abc import ABC, abstractmethod
from typing import Optional


class Broker(ABC):
    """
    经纪商抽象基类。

    回测: 使用 SimulatedBroker
    实盘: 继承此类实现 LiveBroker（对接券商 API）
    """

    @abstractmethod
    def execute_order(self, order, current_bar, portfolio) -> Optional[object]:
        """
        执行订单。

        参数:
            order: OrderEvent 订单事件
            current_bar: 当前K线数据 (pd.Series)
            portfolio: 组合管理器（用于检查资金/持仓）

        返回:
            FillEvent 或 None（订单无法执行时）
        """
        pass
