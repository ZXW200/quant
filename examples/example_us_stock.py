"""
示例3: 美股 布林带策略回测

以苹果(AAPL)为例，使用布林带突破策略。
价格触及下轨买入，触及上轨卖出。

运行方式:
    cd C:\
    python -m quant_backtest.examples.example_us_stock
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from quant_backtest import Engine, BollingerStrategy, USStockData


def main():
    print("=" * 60)
    print("  美股 布林带策略回测 - 苹果(AAPL)")
    print("=" * 60)

    # 加载美股数据
    print("\n正在加载数据...")
    loader = USStockData()
    data = loader.load("AAPL", "2020-01-01", "2024-01-01")
    print(f"加载完成! 共 {len(data)} 根K线")

    # 创建布林带策略
    strategy = BollingerStrategy(
        period=20,       # 20日均线作为中轨
        num_std=2.0      # 2倍标准差
    )

    # 运行回测（注意美股参数设置）
    print("运行回测...")
    engine = Engine(
        data=data,
        strategy=strategy,
        capital=50000,       # 初始资金 5 万美元
        commission=0.001,    # 佣金千一
        slippage=0.0005,     # 滑点万五
        market="US",         # 美股市场
        symbol="AAPL"
    )
    result = engine.run()

    # 查看结果
    result.report()

    try:
        result.plot()
    except Exception as e:
        print(f"可视化跳过: {e}")

    return result


if __name__ == "__main__":
    main()
