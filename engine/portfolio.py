"""
投资组合管理器。
负责资金管理、持仓跟踪、手续费/滑点计算、权益曲线记录。
支持 A 股和美股不同的费用模型。
"""

from dataclasses import dataclass
from typing import List, Dict
import pandas as pd


@dataclass
class Trade:
    """单笔交易记录"""
    datetime: pd.Timestamp
    symbol: str
    direction: str       # "BUY" / "SELL"
    price: float         # 实际成交价（含滑点）
    quantity: int
    commission: float    # 手续费
    slippage: float      # 滑点成本


class Portfolio:
    """
    投资组合管理器。

    费用模型:
        A股: 佣金(万三, 最低5元) + 印花税(千一, 仅卖出)
        美股: 佣金(按比例, 无最低限制)

    参数:
        initial_capital: 初始资金，默认 10 万
        commission_rate: 佣金费率，A股默认万三(0.0003)
        slippage: 滑点比例，默认千一(0.001)
        min_commission: 最低佣金(仅A股)，默认5元
        stamp_tax: 印花税(仅A股卖出)，默认千一(0.001)
        market: "A"=A股, "US"=美股
    """

    def __init__(
        self,
        initial_capital: float = 100000.0,
        commission_rate: float = 0.0003,
        slippage: float = 0.001,
        min_commission: float = 5.0,
        stamp_tax: float = 0.001,
        market: str = "A"
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission_rate = commission_rate
        self.slippage = slippage
        self.min_commission = min_commission
        self.stamp_tax = stamp_tax
        self.market = market

        # 持仓状态
        self.position: int = 0           # 持仓数量
        self.position_avg_cost: float = 0.0  # 持仓均价

        # 历史记录
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict] = []

    def calculate_slippage(self, price: float, direction: str) -> float:
        """
        计算滑点后的实际成交价。
        买入时价格上滑，卖出时价格下滑。
        """
        if direction == "BUY":
            return round(price * (1 + self.slippage), 4)
        else:
            return round(price * (1 - self.slippage), 4)

    def calculate_commission(
        self, price: float, quantity: int, direction: str
    ) -> float:
        """
        计算交易手续费。

        A股:
            佣金 = max(成交额 * 费率, 最低佣金)
            卖出时额外加印花税 = 成交额 * 0.001
        美股:
            佣金 = 成交额 * 费率（无最低限制）
        """
        trade_amount = price * quantity

        if self.market == "A":
            commission = max(trade_amount * self.commission_rate, self.min_commission)
            if direction == "SELL":
                commission += trade_amount * self.stamp_tax
        else:
            commission = trade_amount * self.commission_rate

        return round(commission, 2)

    def execute_fill(self, fill_event) -> bool:
        """
        处理成交事件，更新持仓和资金。

        参数:
            fill_event: FillEvent 成交事件

        返回:
            True=执行成功, False=执行失败
        """
        cost = fill_event.fill_price * fill_event.quantity

        if fill_event.direction == "BUY":
            total_cost = cost + fill_event.commission
            if total_cost > self.cash:
                return False

            # 更新持仓均价
            total_value = self.position_avg_cost * self.position + cost
            self.position += fill_event.quantity
            if self.position > 0:
                self.position_avg_cost = total_value / self.position

            # 扣减资金
            self.cash -= total_cost

        elif fill_event.direction == "SELL":
            if fill_event.quantity > self.position:
                return False

            # 卖出收入
            revenue = cost - fill_event.commission
            self.cash += revenue
            self.position -= fill_event.quantity

            # 清仓时重置均价
            if self.position == 0:
                self.position_avg_cost = 0.0

        # 记录交易
        self.trades.append(Trade(
            datetime=fill_event.datetime,
            symbol=fill_event.symbol,
            direction=fill_event.direction,
            price=fill_event.fill_price,
            quantity=fill_event.quantity,
            commission=fill_event.commission,
            slippage=fill_event.slippage_cost
        ))

        return True

    def update_market_value(
        self, datetime: pd.Timestamp, close_price: float
    ) -> None:
        """
        每根K线结束后更新组合市值，记录权益曲线点。
        总资产 = 现金 + 持仓市值
        """
        market_value = self.position * close_price
        total_equity = self.cash + market_value
        self.equity_curve.append({
            'datetime': datetime,
            'cash': round(self.cash, 2),
            'market_value': round(market_value, 2),
            'total_equity': round(total_equity, 2),
            'position': self.position,
        })

    def get_equity_df(self) -> pd.DataFrame:
        """将权益曲线转换为 DataFrame"""
        if not self.equity_curve:
            return pd.DataFrame()
        return pd.DataFrame(self.equity_curve).set_index('datetime')

    def get_trades_df(self) -> pd.DataFrame:
        """将交易记录转换为 DataFrame"""
        if not self.trades:
            return pd.DataFrame(
                columns=['datetime', 'symbol', 'direction', 'price',
                         'quantity', 'commission', 'slippage']
            )
        return pd.DataFrame([
            {
                'datetime': t.datetime,
                'symbol': t.symbol,
                'direction': t.direction,
                'price': t.price,
                'quantity': t.quantity,
                'commission': t.commission,
                'slippage': t.slippage,
            }
            for t in self.trades
        ])
