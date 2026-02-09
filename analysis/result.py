"""
回测结果封装类。
提供 report() 和 plot() 两个核心方法，让用户一行代码查看结果。
"""

import pandas as pd
from typing import Optional, Dict
from .metrics import calculate_all_metrics
from .report import ReportGenerator


class BacktestResult:
    """
    回测结果封装。

    使用方法:
        result = engine.run()
        result.report()               # 打印绩效报告
        result.plot()                  # 生成可视化图表
        result.plot_candlestick()      # K线图
        result.to_csv("output")        # 导出CSV
        print(result.metrics)          # 查看所有指标
    """

    def __init__(
        self,
        equity_curve: pd.DataFrame,
        trades: pd.DataFrame,
        initial_capital: float,
        data: pd.DataFrame,
        strategy_name: str,
        symbol: str,
        risk_free_rate: float = 0.03,
        trading_days: int = 252
    ):
        self.equity_curve = equity_curve
        self.trades = trades
        self.initial_capital = initial_capital
        self.data = data
        self.strategy_name = strategy_name
        self.symbol = symbol

        # 计算所有指标
        if not equity_curve.empty:
            self.metrics: Dict[str, float] = calculate_all_metrics(
                equity_curve=equity_curve['total_equity'],
                trades=trades,
                risk_free_rate=risk_free_rate,
                trading_days=trading_days
            )
        else:
            self.metrics = {}

    def report(self) -> None:
        """打印绩效报告到控制台"""
        if self.data.empty:
            print("无数据，无法生成报告。")
            return

        start = self.data.index[0].strftime('%Y-%m-%d')
        end = self.data.index[-1].strftime('%Y-%m-%d')
        ReportGenerator.print_summary(
            self.metrics, self.strategy_name,
            self.symbol, start, end
        )
        ReportGenerator.print_trades(self.trades)

    def plot(self, figsize: tuple = (16, 14)) -> None:
        """生成可视化图表（价格+买卖点、资金曲线、回撤、持仓）"""
        from ..visualization.charts import BacktestCharts
        charts = BacktestCharts(
            data=self.data,
            equity_curve=self.equity_curve,
            trades=self.trades,
            strategy_name=self.strategy_name,
            symbol=self.symbol
        )
        charts.plot_all(figsize=figsize)

    def plot_candlestick(self, last_n: int = 120) -> None:
        """绘制K线图（含买卖标记）"""
        from ..visualization.charts import BacktestCharts
        charts = BacktestCharts(
            data=self.data,
            equity_curve=self.equity_curve,
            trades=self.trades,
            strategy_name=self.strategy_name,
            symbol=self.symbol
        )
        charts.plot_candlestick(last_n=last_n)

    def get_metric(self, name: str) -> Optional[float]:
        """获取单个指标值"""
        return self.metrics.get(name)

    def to_csv(self, path: str) -> None:
        """导出权益曲线和交易记录到 CSV"""
        self.equity_curve.to_csv(f"{path}_equity.csv")
        self.trades.to_csv(f"{path}_trades.csv", index=False)
        print(f"已导出: {path}_equity.csv, {path}_trades.csv")
