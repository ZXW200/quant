"""
示例2: A股 RSI 超买超卖策略回测

以平安银行(000001)为例，使用 RSI 策略。
RSI < 30 买入（超卖），RSI > 70 卖出（超买）。

运行方式:
    cd C:\
    python -m quant_backtest.examples.example_rsi
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from quant_backtest import Engine, RSIStrategy, AStockData


def main():
    print("=" * 60)
    print("  A股 RSI 策略回测 - 平安银行(000001)")
    print("=" * 60)

    # 加载数据
    print("\n正在加载数据...")
    loader = AStockData()
    data = loader.load("000001", "2020-01-01", "2024-01-01")
    print(f"加载完成! 共 {len(data)} 根K线")

    # 创建 RSI 策略
    strategy = RSIStrategy(
        period=14,        # 14日RSI
        oversold=30.0,    # 低于30买入
        overbought=70.0   # 高于70卖出
    )

    # 运行回测
    print("运行回测...")
    engine = Engine(
        data=data,
        strategy=strategy,
        capital=100000,
        market="A",
        symbol="000001"
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
