"""
回测可视化图表模块。
包含: 价格+买卖标记、资金曲线、回撤曲线、持仓变化、K线图。
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Optional

# 设置中文字体（解决 matplotlib 中文显示问题）
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class BacktestCharts:
    """
    回测可视化图表。

    使用方法（通常通过 BacktestResult 间接调用）:
        result = engine.run()
        result.plot()              # 4合1综合图表
        result.plot_candlestick()  # K线图
    """

    def __init__(
        self,
        data: pd.DataFrame,
        equity_curve: pd.DataFrame,
        trades: pd.DataFrame,
        strategy_name: str,
        symbol: str
    ):
        self.data = data
        self.equity_curve = equity_curve
        self.trades = trades
        self.strategy_name = strategy_name
        self.symbol = symbol

    def plot_all(self, figsize: tuple = (16, 14)) -> None:
        """
        绘制完整的回测报告图表（4个子图）:
            1. 价格走势 + 买卖标记
            2. 资金曲线（策略 vs 基准买入持有）
            3. 回撤曲线
            4. 持仓变化
        """
        fig, axes = plt.subplots(
            4, 1, figsize=figsize,
            gridspec_kw={'height_ratios': [3, 2, 1, 1]}
        )
        fig.suptitle(
            f'{self.strategy_name} - {self.symbol} 回测报告',
            fontsize=16, fontweight='bold', y=0.98
        )

        self._plot_price_with_trades(axes[0])
        self._plot_equity_curve(axes[1])
        self._plot_drawdown(axes[2])
        self._plot_position(axes[3])

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.show()

    def _plot_price_with_trades(self, ax) -> None:
        """子图1: 价格走势 + 买卖标记点"""
        ax.plot(
            self.data.index, self.data['close'],
            color='#333333', linewidth=0.8, label='收盘价'
        )

        if not self.trades.empty:
            # 买入标记（红色上三角 - A股红涨）
            buys = self.trades[self.trades['direction'] == 'BUY']
            if not buys.empty:
                ax.scatter(
                    buys['datetime'], buys['price'],
                    marker='^', color='red', s=80,
                    label='买入', zorder=5, edgecolors='darkred'
                )

            # 卖出标记（绿色下三角 - A股绿跌）
            sells = self.trades[self.trades['direction'] == 'SELL']
            if not sells.empty:
                ax.scatter(
                    sells['datetime'], sells['price'],
                    marker='v', color='green', s=80,
                    label='卖出', zorder=5, edgecolors='darkgreen'
                )

        ax.set_title('价格走势与交易信号', fontsize=12)
        ax.legend(loc='upper left', fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.set_ylabel('价格')

    def _plot_equity_curve(self, ax) -> None:
        """子图2: 资金曲线（含基准对比）"""
        if self.equity_curve.empty:
            return

        equity = self.equity_curve['total_equity']
        ax.plot(
            equity.index, equity, color='#1f77b4',
            linewidth=1.2, label='策略净值'
        )

        # 基准: 买入持有（第一天全仓买入，持有到最后）
        initial = equity.iloc[0]
        benchmark = (self.data['close'] / self.data['close'].iloc[0]) * initial
        ax.plot(
            self.data.index, benchmark, color='#ff7f0e',
            linewidth=1.0, linestyle='--', label='基准(买入持有)'
        )

        # 盈亏区域填充
        ax.fill_between(
            equity.index, equity, initial,
            where=equity >= initial, alpha=0.1, color='green'
        )
        ax.fill_between(
            equity.index, equity, initial,
            where=equity < initial, alpha=0.1, color='red'
        )

        ax.set_title('资金曲线', fontsize=12)
        ax.legend(loc='upper left', fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.set_ylabel('资金 (元)')

    def _plot_drawdown(self, ax) -> None:
        """子图3: 回撤曲线"""
        if self.equity_curve.empty:
            return

        equity = self.equity_curve['total_equity']
        running_max = np.maximum.accumulate(equity)
        drawdown = (running_max - equity) / running_max * 100

        ax.fill_between(equity.index, 0, -drawdown, color='red', alpha=0.3)
        ax.plot(equity.index, -drawdown, color='red', linewidth=0.8)

        ax.set_title('回撤曲线', fontsize=12)
        ax.set_ylabel('回撤 (%)')
        ax.grid(True, alpha=0.3)

    def _plot_position(self, ax) -> None:
        """子图4: 持仓变化"""
        if self.equity_curve.empty:
            return

        pos = self.equity_curve['position']
        ax.fill_between(pos.index, 0, pos, color='#1f77b4', alpha=0.4)
        ax.plot(pos.index, pos, color='#1f77b4', linewidth=0.8)

        ax.set_title('持仓数量', fontsize=12)
        ax.set_ylabel('股数')
        ax.set_xlabel('日期')
        ax.grid(True, alpha=0.3)

    def plot_candlestick(self, last_n: int = 120) -> None:
        """
        绘制K线图（含成交量和买卖标记）。
        使用 mplfinance 库。

        参数:
            last_n: 显示最后 n 根K线，默认120
        """
        try:
            import mplfinance as mpf
        except ImportError:
            print("请安装 mplfinance: pip install mplfinance")
            print("将使用简单折线图替代...")
            self._plot_simple_price(last_n)
            return

        plot_data = self.data.tail(last_n).copy()
        # mplfinance 要求列名首字母大写
        plot_data.columns = [c.capitalize() for c in plot_data.columns]

        # 构建买卖标记
        addplots = []
        buy_signals = self._build_signal_series(plot_data, 'BUY')
        sell_signals = self._build_signal_series(plot_data, 'SELL')

        if buy_signals is not None:
            addplots.append(mpf.make_addplot(
                buy_signals, type='scatter', marker='^',
                markersize=100, color='red'
            ))
        if sell_signals is not None:
            addplots.append(mpf.make_addplot(
                sell_signals, type='scatter', marker='v',
                markersize=100, color='green'
            ))

        mpf.plot(
            plot_data,
            type='candle',
            style='charles',
            title=f'\n{self.symbol} K线图 (最近{last_n}天)',
            volume=True if 'Volume' in plot_data.columns else False,
            addplot=addplots if addplots else None,
            figsize=(16, 8)
        )

    def _build_signal_series(
        self, data: pd.DataFrame, direction: str
    ) -> Optional[pd.Series]:
        """将交易记录转换为与K线对齐的信号序列（NaN填充无信号位置）"""
        if self.trades.empty:
            return None

        signals = self.trades[self.trades['direction'] == direction]
        if signals.empty:
            return None

        signal_series = pd.Series(np.nan, index=data.index)
        for _, trade in signals.iterrows():
            dt = trade['datetime']
            if dt in data.index:
                signal_series[dt] = trade['price']

        if signal_series.isna().all():
            return None
        return signal_series

    def _plot_simple_price(self, last_n: int) -> None:
        """简单折线图（mplfinance 不可用时的备选方案）"""
        plot_data = self.data.tail(last_n)
        fig, ax = plt.subplots(figsize=(16, 8))
        ax.plot(plot_data.index, plot_data['close'], color='#333', linewidth=1)
        ax.set_title(f'{self.symbol} 价格走势 (最近{last_n}天)')
        ax.set_ylabel('价格')
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()
