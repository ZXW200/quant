"""
示例4: 自定义策略 - 均线 + RSI 双重确认

演示如何编写自己的策略。
只需继承 Strategy 类，实现 init() 和 on_bar() 两个方法。

买入条件: 5日均线 > 20日均线 (趋势向上) 且 RSI < 40 (未超买)
卖出条件: 5日均线 < 20日均线 (趋势向下) 或 RSI > 80 (超买)

运行方式:
    cd C:\
    python -m quant_backtest.examples.example_custom
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from quant_backtest import Engine, Strategy, AStockData
from quant_backtest.strategy.indicators import sma, rsi


class MyStrategy(Strategy):
    """
    自定义策略: 均线趋势 + RSI 过滤

    思路:
        均线判断趋势方向，RSI 过滤入场时机。
        只在趋势向上且 RSI 未超买时买入，避免追高。
    """

    def __init__(self):
        super().__init__(name="均线RSI双确认策略")
        self.sma5 = None
        self.sma20 = None
        self.rsi14 = None

    def init(self):
        """初始化: 预计算所有需要的技术指标"""
        data = self.ctx.data
        self.sma5 = sma(data['close'], 5)    # 5日均线
        self.sma20 = sma(data['close'], 20)  # 20日均线
        self.rsi14 = rsi(data['close'], 14)  # 14日RSI

    def on_bar(self, bar):
        """
        每根K线的交易逻辑:
        1. 等待指标数据充分（至少20天）
        2. 判断均线关系和RSI位置
        3. 满足条件时发出买卖信号
        """
        idx = self.ctx.current_idx
        if idx < 20:  # 等待指标计算充分
            return

        # 获取当前指标值
        s5 = self.sma5.iloc[idx]
        s20 = self.sma20.iloc[idx]
        r = self.rsi14.iloc[idx]

        # 买入条件: 均线多头排列 + RSI 低位
        if s5 > s20 and r < 40 and self.position == 0:
            self.buy()

        # 卖出条件: 均线死叉 或 RSI 超买
        if (s5 < s20 or r > 80) and self.position > 0:
            self.sell()


def main():
    print("=" * 60)
    print("  自定义策略回测 - 均线RSI双确认")
    print("=" * 60)

    # 加载数据
    print("\n正在加载数据...")
    loader = AStockData()
    data = loader.load("600519", "2020-01-01", "2024-01-01")
    print(f"加载完成! 共 {len(data)} 根K线")

    # 使用自定义策略
    strategy = MyStrategy()

    # 运行回测
    print("运行回测...")
    engine = Engine(
        data=data,
        strategy=strategy,
        capital=100000,
        market="A",
        symbol="600519"
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
