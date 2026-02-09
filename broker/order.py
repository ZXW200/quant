"""
订单数据结构定义。
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
import pandas as pd


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderType(Enum):
    """订单类型"""
    MARKET = "MARKET"   # 市价单
    LIMIT = "LIMIT"     # 限价单


class OrderDirection(Enum):
    """订单方向"""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:
    """完整的订单对象"""
    order_id: int
    datetime: pd.Timestamp
    symbol: str
    direction: str
    order_type: str
    quantity: int
    price: Optional[float] = None
    status: str = "PENDING"
    filled_price: Optional[float] = None
    filled_quantity: int = 0
    commission: float = 0.0
