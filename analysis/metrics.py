"""
核心绩效指标计算模块。
包含量化交易中最重要的评价指标。
"""

import pandas as pd
import numpy as np
from typing import Dict, List


def total_return(equity_curve: pd.Series) -> float:
    """
    总收益率 = (期末资产 - 期初资产) / 期初资产

    示例: 10万 -> 15万，总收益率 = 50%
    """
    return (equity_curve.iloc[-1] - equity_curve.iloc[0]) / equity_curve.iloc[0]


def annualized_return(
    equity_curve: pd.Series,
    trading_days: int = 252
) -> float:
    """
    年化收益率 = (1 + 总收益率) ^ (252 / 交易天数) - 1

    将不同时间段的收益率统一换算到年度，便于横向比较。
    A股每年约 252 个交易日。
    """
    total_ret = total_return(equity_curve)
    n_days = len(equity_curve)
    if n_days <= 1:
        return 0.0
    return (1 + total_ret) ** (trading_days / n_days) - 1


def max_drawdown(equity_curve: pd.Series) -> float:
    """
    最大回撤 = max((历史最高点 - 当前值) / 历史最高点)

    衡量策略在最坏情况下的亏损幅度。
    例如: 最大回撤 20% 表示资金最多从高点回落 20%。
    """
    running_max = np.maximum.accumulate(equity_curve)
    drawdowns = (running_max - equity_curve) / running_max
    return drawdowns.max()


def max_drawdown_duration(equity_curve: pd.Series) -> int:
    """
    最大回撤持续天数。
    从资金创新高到下一次创新高之间的最长天数。
    """
    running_max = np.maximum.accumulate(equity_curve)
    in_drawdown = equity_curve < running_max

    if not in_drawdown.any():
        return 0

    # 计算连续回撤的最大长度
    groups = (~in_drawdown).cumsum()
    max_duration = in_drawdown.groupby(groups).sum().max()
    return int(max_duration)


def sharpe_ratio(
    equity_curve: pd.Series,
    risk_free_rate: float = 0.03,
    trading_days: int = 252
) -> float:
    """
    夏普比率 = sqrt(252) * (平均日超额收益) / 日收益标准差

    衡量每承担一单位风险所获得的超额收益。
    一般认为:
        > 2.0: 非常好
        > 1.0: 较好
        > 0.5: 一般
        < 0:   亏损
    """
    daily_returns = equity_curve.pct_change().dropna()
    if len(daily_returns) == 0 or daily_returns.std() == 0:
        return 0.0
    daily_rf = risk_free_rate / trading_days
    excess_returns = daily_returns - daily_rf
    return np.sqrt(trading_days) * excess_returns.mean() / excess_returns.std()


def sortino_ratio(
    equity_curve: pd.Series,
    risk_free_rate: float = 0.03,
    trading_days: int = 252
) -> float:
    """
    索提诺比率：只考虑下行波动的风险调整收益。
    与夏普比率类似，但只惩罚下跌风险，不惩罚上涨波动。
    """
    daily_returns = equity_curve.pct_change().dropna()
    daily_rf = risk_free_rate / trading_days
    excess_returns = daily_returns - daily_rf
    downside = excess_returns[excess_returns < 0]
    if len(downside) == 0 or downside.std() == 0:
        return 0.0
    return np.sqrt(trading_days) * excess_returns.mean() / downside.std()


def calmar_ratio(
    equity_curve: pd.Series,
    trading_days: int = 252
) -> float:
    """
    卡玛比率 = 年化收益率 / 最大回撤
    衡量收益与最大风险的比值。越高越好。
    """
    ann_ret = annualized_return(equity_curve, trading_days)
    mdd = max_drawdown(equity_curve)
    return ann_ret / mdd if mdd > 0 else 0.0


def volatility(
    equity_curve: pd.Series,
    trading_days: int = 252
) -> float:
    """
    年化波动率 = 日收益标准差 * sqrt(252)
    衡量收益的不确定性，越低表示策略越稳定。
    """
    daily_returns = equity_curve.pct_change().dropna()
    if len(daily_returns) == 0:
        return 0.0
    return daily_returns.std() * np.sqrt(trading_days)


def _pair_trades(trades: pd.DataFrame) -> List[Dict]:
    """
    将买卖交易配对（FIFO），计算每笔完整交易的盈亏。

    例如: 买100股@10元 + 卖100股@12元 = 盈利 200元
    """
    paired = []
    buy_stack = []

    for _, trade in trades.iterrows():
        if trade['direction'] == 'BUY':
            buy_stack.append(trade)
        elif trade['direction'] == 'SELL' and buy_stack:
            buy = buy_stack.pop(0)  # FIFO: 先买的先卖
            pnl = (trade['price'] - buy['price']) * trade['quantity']
            pnl -= (buy['commission'] + trade['commission'])
            paired.append({
                'buy_date': buy['datetime'],
                'sell_date': trade['datetime'],
                'buy_price': buy['price'],
                'sell_price': trade['price'],
                'quantity': trade['quantity'],
                'pnl': pnl,
                'return': (trade['price'] - buy['price']) / buy['price'],
                'holding_days': (trade['datetime'] - buy['datetime']).days
            })
    return paired


def win_rate(trades: pd.DataFrame) -> float:
    """
    胜率 = 盈利交易次数 / 总交易次数

    注意: 高胜率不一定意味着策略好，还需要看盈亏比。
    """
    if trades.empty:
        return 0.0
    paired = _pair_trades(trades)
    if not paired:
        return 0.0
    profitable = sum(1 for t in paired if t['pnl'] > 0)
    return profitable / len(paired)


def profit_loss_ratio(trades: pd.DataFrame) -> float:
    """
    盈亏比 = 平均盈利金额 / 平均亏损金额

    盈亏比 > 1 表示平均每笔赚的比亏的多。
    即使胜率低于50%，高盈亏比也可能整体盈利。
    """
    paired = _pair_trades(trades)
    if not paired:
        return 0.0
    profits = [t['pnl'] for t in paired if t['pnl'] > 0]
    losses = [abs(t['pnl']) for t in paired if t['pnl'] < 0]
    avg_profit = np.mean(profits) if profits else 0
    avg_loss = np.mean(losses) if losses else 1
    return avg_profit / avg_loss if avg_loss > 0 else float('inf')


def calculate_all_metrics(
    equity_curve: pd.Series,
    trades: pd.DataFrame,
    risk_free_rate: float = 0.03,
    trading_days: int = 252
) -> Dict[str, float]:
    """
    一次性计算所有核心指标。

    返回字典:
        总收益率, 年化收益率, 最大回撤, 夏普比率,
        索提诺比率, 卡玛比率, 年化波动率, 胜率, 盈亏比, ...
    """
    return {
        '总收益率': total_return(equity_curve),
        '年化收益率': annualized_return(equity_curve, trading_days),
        '最大回撤': max_drawdown(equity_curve),
        '最大回撤持续天数': max_drawdown_duration(equity_curve),
        '夏普比率': sharpe_ratio(equity_curve, risk_free_rate, trading_days),
        '索提诺比率': sortino_ratio(equity_curve, risk_free_rate, trading_days),
        '卡玛比率': calmar_ratio(equity_curve, trading_days),
        '年化波动率': volatility(equity_curve, trading_days),
        '胜率': win_rate(trades),
        '盈亏比': profit_loss_ratio(trades),
        '总交易次数': len(_pair_trades(trades)) if not trades.empty else 0,
    }
