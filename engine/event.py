"""
事件定义模块。
事件驱动回测的核心：4种事件在引擎中依次流转。

流转顺序:
    MarketEvent(新K线) -> SignalEvent(策略信号) -> OrderEvent(订单) -> FillEvent(成交)
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


class EventType(Enum):
    """事件类型枚举"""
    MARKET = "MARKET"   # 市场数据事件（新K线到达）
    SIGNAL = "SIGNAL"   # 策略信号事件（买/卖信号）
    ORDER = "ORDER"     # 订单事件（提交给 Broker）
    FILL = "FILL"       # 成交事件（Broker 执行结果）


@dataclass
class MarketEvent:
    """
    市场数据事件。
    当新的一根K线数据到达时由引擎产生。
    """
    type: EventType = field(default=EventType.MARKET, init=False)
    datetime: pd.Timestamp = None


@dataclass
class SignalEvent:
    """
    策略产生的交易信号。
    由策略的 on_bar() 方法通过 buy()/sell() 间接生成。
    """
    type: EventType = field(default=EventType.SIGNAL, init=False)
    datetime: pd.Timestamp = None
    symbol: str = ""
    direction: str = ""          # "BUY" / "SELL"
    volume: int = 0              # 下单数量
    order_type: str = "MARKET"   # "MARKET" / "LIMIT"
    limit_price: Optional[float] = None


@dataclass
class OrderEvent:
    """
    发送给 Broker 的订单。
    由引擎根据 SignalEvent 生成，包含具体的数量和价格。
    """
    type: EventType = field(default=EventType.ORDER, init=False)
    datetime: pd.Timestamp = None
    symbol: str = ""
    direction: str = ""          # "BUY" / "SELL"
    order_type: str = "MARKET"   # "MARKET" / "LIMIT"
    quantity: int = 0
    price: Optional[float] = None


@dataclass
class FillEvent:
    """
    订单成交事件。
    由 Broker 执行后返回，包含实际成交的价格和费用。
    """
    type: EventType = field(default=EventType.FILL, init=False)
    datetime: pd.Timestamp = None
    symbol: str = ""
    direction: str = ""          # "BUY" / "SELL"
    quantity: int = 0
    fill_price: float = 0.0
    commission: float = 0.0      # 手续费
    slippage_cost: float = 0.0   # 滑点成本
