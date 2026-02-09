"""
示例1: A股 均线交叉策略回测

以贵州茅台(600519)为例，使用5日/20日双均线交叉策略。
金叉买入，死叉卖出。

运行方式:
    cd C:\
    python -m quant_backtest.examples.example_sma
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from quant_backtest import Engine, SMAStrategy, AStockData


def main():
    print("=" * 60)
    print("  A股 均线交叉策略回测 - 贵州茅台(600519)")
    print("=" * 60)

    # 第一步: 加载数据
    print("\n[1/4] 正在加载数据...")
    loader = AStockData()
    data = loader.load("600519", "2020-01-01", "2024-01-01")
    print(f"  加载完成! 共 {len(data)} 根K线")
    print(f"  日期范围: {data.index[0].strftime('%Y-%m-%d')} ~ {data.index[-1].strftime('%Y-%m-%d')}")
    print(f"  价格范围: {data['close'].min():.2f} ~ {data['close'].max():.2f}")

    # 第二步: 创建策略
    print("\n[2/4] 创建策略: 5日/20日均线交叉")
    strategy = SMAStrategy(short_period=5, long_period=20)

    # 第三步: 创建引擎并运行回测
    print("\n[3/4] 运行回测...")
    engine = Engine(
        data=data,
        strategy=strategy,
        capital=100000,     # 初始资金 10 万元
        commission=0.0003,  # 佣金万三
        slippage=0.001,     # 滑点千一
        market="A",         # A股市场
        symbol="600519"
    )
    result = engine.run()
    print("  回测完成!")

    # 第四步: 查看结果
    print("\n[4/4] 生成报告...")
    result.report()

    # 可视化（需要图形界面环境）
    try:
        result.plot()
    except Exception as e:
        print(f"  可视化跳过 (无图形界面): {e}")

    return result


if __name__ == "__main__":
    main()
