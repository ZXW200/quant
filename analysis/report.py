"""
绩效报告生成器。
在控制台打印格式化的回测报告。
"""

from typing import Dict
import pandas as pd


class ReportGenerator:
    """绩效报告生成器"""

    @staticmethod
    def print_summary(
        metrics: Dict[str, float],
        strategy_name: str,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> None:
        """打印格式化的绩效摘要"""
        print()
        print("=" * 60)
        print(f"  回测报告: {strategy_name}")
        print(f"  标的: {symbol}  |  {start_date} ~ {end_date}")
        print("=" * 60)

        # 指标格式化规则
        formatters = {
            '总收益率': lambda v: f"{v:>10.2%}",
            '年化收益率': lambda v: f"{v:>10.2%}",
            '最大回撤': lambda v: f"{v:>10.2%}",
            '最大回撤持续天数': lambda v: f"{int(v):>8} 天",
            '夏普比率': lambda v: f"{v:>10.3f}",
            '索提诺比率': lambda v: f"{v:>10.3f}",
            '卡玛比率': lambda v: f"{v:>10.3f}",
            '年化波动率': lambda v: f"{v:>10.2%}",
            '胜率': lambda v: f"{v:>10.2%}",
            '盈亏比': lambda v: f"{v:>10.2f}",
            '总交易次数': lambda v: f"{int(v):>8} 笔",
        }

        print(f"  {'指标':<16} {'数值':>12}")
        print("-" * 60)
        for name, value in metrics.items():
            fmt = formatters.get(name, lambda v: f"{v:>10.4f}")
            print(f"  {name:<16} {fmt(value)}")
        print("=" * 60)
        print()

    @staticmethod
    def print_trades(trades: pd.DataFrame, top_n: int = 20) -> None:
        """打印最近的交易记录"""
        if trades.empty:
            print("  无交易记录。")
            return

        print(f"  最近 {min(top_n, len(trades))} 笔交易:")
        print("-" * 80)
        print(f"  {'日期':<12} {'方向':<6} {'价格':>10} {'数量':>8} {'手续费':>10}")
        print("-" * 80)

        display = trades.tail(top_n)
        for _, row in display.iterrows():
            date_str = row['datetime'].strftime('%Y-%m-%d') if hasattr(row['datetime'], 'strftime') else str(row['datetime'])[:10]
            print(f"  {date_str:<12} {row['direction']:<6} {row['price']:>10.2f} {row['quantity']:>8} {row['commission']:>10.2f}")

        print("-" * 80)
        print()
