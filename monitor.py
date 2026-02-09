"""
实时股票监控程序。

功能:
    - 定时获取最新行情数据
    - 同时运行 SMA交叉 / RSI / 布林带 三种策略
    - 检测到买卖信号时发出声音提醒
    - 支持 A股 和 美股 混合监控

使用方法:
    py C:/quant_backtest/monitor.py

    或者自定义参数:
    py C:/quant_backtest/monitor.py --stocks 600519 000001 AAPL --interval 300

按 Ctrl+C 停止监控。
"""

import sys
import os
import time
import argparse
import winsound
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import pandas as pd
import numpy as np

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from quant_backtest.strategy.indicators import sma, rsi, bollinger_bands


# ============================================================
#  配置
# ============================================================

# 默认监控的股票列表
DEFAULT_STOCKS = [
    {"symbol": "600519", "name": "贵州茅台", "market": "A"},
    {"symbol": "AAPL",   "name": "苹果",     "market": "US"},
]

# 声音提醒配置 (频率Hz, 持续时间ms)
SOUND_BUY  = (1000, 500)   # 买入信号: 高音
SOUND_SELL = (500, 500)    # 卖出信号: 低音
SOUND_ALERT = (800, 200)   # 普通提醒


# ============================================================
#  数据获取
# ============================================================

def fetch_latest_data(symbol: str, market: str, days: int = 120) -> Optional[pd.DataFrame]:
    """
    获取最近 N 天的日K线数据（用于指标计算）。

    参数:
        symbol: 股票代码
        market: "A" 或 "US"
        days: 获取最近多少天的数据
    """
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")

    try:
        if market == "A":
            import akshare as ak
            start_fmt = start_date.replace("-", "")
            end_fmt = end_date.replace("-", "")
            df = ak.stock_zh_a_hist(
                symbol=symbol, period="daily",
                start_date=start_fmt, end_date=end_fmt, adjust="qfq"
            )
            column_map = {
                '日期': 'datetime', '开盘': 'open', '收盘': 'close',
                '最高': 'high', '最低': 'low', '成交量': 'volume',
            }
            df = df.rename(columns=column_map)
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime')
            df = df[['open', 'high', 'low', 'close', 'volume']]

        elif market == "US":
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date)
            if df is None or df.empty:
                print(f"  [警告] {symbol} 未获取到数据")
                return None
            df.columns = [c.lower() for c in df.columns]
            keep = [c for c in ['open', 'high', 'low', 'close', 'volume'] if c in df.columns]
            df = df[keep]
            df.index.name = 'datetime'
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)

        # 只保留最近 days 根K线
        df = df.tail(days)

        if len(df) < 30:
            print(f"  [警告] {symbol} 数据不足 ({len(df)} 根K线)")
            return None

        return df

    except Exception as e:
        print(f"  [错误] 获取 {symbol} 数据失败: {e}")
        return None


# ============================================================
#  信号检测
# ============================================================

class SignalDetector:
    """
    多策略信号检测器。
    同时检测 SMA交叉、RSI、布林带 三种策略的信号。
    """

    def __init__(self):
        # 记录上一次的状态，避免重复报警
        self._last_signals: Dict[str, Dict[str, str]] = {}

    def detect(self, symbol: str, df: pd.DataFrame) -> List[Dict]:
        """
        检测所有策略的信号。

        返回:
            信号列表 [{"strategy": "SMA交叉", "direction": "BUY", "reason": "..."}, ...]
        """
        signals = []

        # 1. SMA 均线交叉
        sig = self._check_sma(symbol, df)
        if sig:
            signals.append(sig)

        # 2. RSI 超买超卖
        sig = self._check_rsi(symbol, df)
        if sig:
            signals.append(sig)

        # 3. 布林带突破
        sig = self._check_bollinger(symbol, df)
        if sig:
            signals.append(sig)

        return signals

    def _check_sma(self, symbol: str, df: pd.DataFrame) -> Optional[Dict]:
        """检测 SMA 金叉/死叉"""
        close = df['close']
        sma5 = sma(close, 5)
        sma20 = sma(close, 20)

        if len(df) < 21:
            return None

        short_now = sma5.iloc[-1]
        long_now = sma20.iloc[-1]
        short_prev = sma5.iloc[-2]
        long_prev = sma20.iloc[-2]

        key = f"{symbol}_SMA"

        # 金叉
        if short_prev <= long_prev and short_now > long_now:
            if self._is_new_signal(key, "BUY"):
                return {
                    "strategy": "SMA交叉(5/20)",
                    "direction": "BUY",
                    "reason": f"5日均线({short_now:.2f})上穿20日均线({long_now:.2f})",
                    "price": close.iloc[-1],
                }

        # 死叉
        elif short_prev >= long_prev and short_now < long_now:
            if self._is_new_signal(key, "SELL"):
                return {
                    "strategy": "SMA交叉(5/20)",
                    "direction": "SELL",
                    "reason": f"5日均线({short_now:.2f})下穿20日均线({long_now:.2f})",
                    "price": close.iloc[-1],
                }

        return None

    def _check_rsi(self, symbol: str, df: pd.DataFrame) -> Optional[Dict]:
        """检测 RSI 超买超卖"""
        close = df['close']
        rsi_series = rsi(close, 14)

        if len(df) < 15:
            return None

        current_rsi = rsi_series.iloc[-1]
        key = f"{symbol}_RSI"

        if current_rsi < 30:
            if self._is_new_signal(key, "BUY"):
                return {
                    "strategy": "RSI(14)",
                    "direction": "BUY",
                    "reason": f"RSI={current_rsi:.1f} < 30 (超卖区间)",
                    "price": close.iloc[-1],
                }
        elif current_rsi > 70:
            if self._is_new_signal(key, "SELL"):
                return {
                    "strategy": "RSI(14)",
                    "direction": "SELL",
                    "reason": f"RSI={current_rsi:.1f} > 70 (超买区间)",
                    "price": close.iloc[-1],
                }
        else:
            # RSI 回到中间区域，重置信号状态
            self._last_signals.pop(key, None)

        return None

    def _check_bollinger(self, symbol: str, df: pd.DataFrame) -> Optional[Dict]:
        """检测布林带突破"""
        close = df['close']
        upper, middle, lower = bollinger_bands(close, 20, 2.0)

        if len(df) < 21:
            return None

        current_close = close.iloc[-1]
        current_upper = upper.iloc[-1]
        current_lower = lower.iloc[-1]
        key = f"{symbol}_BOLL"

        if current_close <= current_lower:
            if self._is_new_signal(key, "BUY"):
                return {
                    "strategy": "布林带(20,2)",
                    "direction": "BUY",
                    "reason": f"价格({current_close:.2f})触及下轨({current_lower:.2f})",
                    "price": current_close,
                }
        elif current_close >= current_upper:
            if self._is_new_signal(key, "SELL"):
                return {
                    "strategy": "布林带(20,2)",
                    "direction": "SELL",
                    "reason": f"价格({current_close:.2f})触及上轨({current_upper:.2f})",
                    "price": current_close,
                }
        else:
            self._last_signals.pop(key, None)

        return None

    def _is_new_signal(self, key: str, direction: str) -> bool:
        """检查是否是新信号（避免同一信号重复提醒）"""
        last = self._last_signals.get(key)
        if last == direction:
            return False  # 已经报过这个信号了
        self._last_signals[key] = direction
        return True


# ============================================================
#  通知
# ============================================================

def alert_signal(stock: Dict, signal: Dict):
    """
    发出信号提醒（声音 + 控制台）。
    """
    now = datetime.now().strftime("%H:%M:%S")
    direction = signal['direction']
    emoji_dir = "买入" if direction == "BUY" else "卖出"

    # 控制台输出
    print()
    print("=" * 60)
    print(f"  !!! {emoji_dir}信号 !!!  {now}")
    print(f"  股票: {stock['name']}({stock['symbol']})")
    print(f"  策略: {signal['strategy']}")
    print(f"  方向: {emoji_dir}")
    print(f"  价格: {signal['price']:.2f}")
    print(f"  原因: {signal['reason']}")
    print("=" * 60)
    print()

    # 声音提醒
    try:
        if direction == "BUY":
            # 买入信号: 连续两声高音
            winsound.Beep(SOUND_BUY[0], SOUND_BUY[1])
            time.sleep(0.1)
            winsound.Beep(SOUND_BUY[0], SOUND_BUY[1])
        else:
            # 卖出信号: 连续两声低音
            winsound.Beep(SOUND_SELL[0], SOUND_SELL[1])
            time.sleep(0.1)
            winsound.Beep(SOUND_SELL[0], SOUND_SELL[1])
    except Exception:
        pass  # 非 Windows 系统跳过声音


def print_status(stock: Dict, df: pd.DataFrame):
    """打印当前行情摘要"""
    close = df['close'].iloc[-1]
    prev_close = df['close'].iloc[-2]
    change = (close - prev_close) / prev_close * 100
    change_str = f"+{change:.2f}%" if change >= 0 else f"{change:.2f}%"

    rsi_val = rsi(df['close'], 14).iloc[-1]
    sma5_val = sma(df['close'], 5).iloc[-1]
    sma20_val = sma(df['close'], 20).iloc[-1]

    print(f"  {stock['name']:>8}({stock['symbol']:<8}) "
          f"价格:{close:>10.2f} ({change_str:>8}) "
          f"RSI:{rsi_val:>5.1f}  "
          f"MA5:{sma5_val:>8.2f}  MA20:{sma20_val:>8.2f}")


# ============================================================
#  主循环
# ============================================================

def run_monitor(stocks: List[Dict], interval: int = 1800):
    """
    主监控循环。

    参数:
        stocks: 股票列表 [{"symbol": "600519", "name": "贵州茅台", "market": "A"}, ...]
        interval: 刷新间隔（秒），默认 1800（30分钟）
    """
    detector = SignalDetector()

    print()
    print("=" * 60)
    print("  量化交易信号监控系统")
    print("=" * 60)
    print(f"  监控标的: {', '.join(s['name'] + '(' + s['symbol'] + ')' for s in stocks)}")
    print(f"  监控策略: SMA交叉(5/20) + RSI(14) + 布林带(20,2)")
    print(f"  刷新间隔: {interval} 秒 ({interval // 60} 分钟)")
    print(f"  通知方式: 声音提醒 + 控制台输出")
    print(f"  按 Ctrl+C 停止监控")
    print("=" * 60)

    # 启动提示音
    try:
        winsound.Beep(SOUND_ALERT[0], SOUND_ALERT[1])
    except Exception:
        pass

    cycle = 0
    while True:
        cycle += 1
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n--- 第 {cycle} 次扫描 | {now} ---")

        for stock in stocks:
            # 获取数据
            df = fetch_latest_data(stock['symbol'], stock['market'])
            if df is None:
                continue

            # 打印当前行情
            print_status(stock, df)

            # 检测信号
            signals = detector.detect(stock['symbol'], df)
            for sig in signals:
                alert_signal(stock, sig)

        # 等待下一次扫描
        print(f"\n下次扫描: {interval} 秒后...")
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n监控已停止。")
            break


# ============================================================
#  命令行入口
# ============================================================

def parse_stocks(stock_args: List[str]) -> List[Dict]:
    """解析命令行输入的股票代码"""
    stocks = []
    for s in stock_args:
        s = s.strip()
        if not s:
            continue
        # 判断是A股还是美股
        if s.isdigit() and len(s) == 6:
            stocks.append({"symbol": s, "name": s, "market": "A"})
        else:
            stocks.append({"symbol": s.upper(), "name": s.upper(), "market": "US"})
    return stocks


def main():
    parser = argparse.ArgumentParser(description="量化交易信号监控")
    parser.add_argument(
        '--stocks', nargs='+', default=None,
        help='股票代码列表，如: 600519 000001 AAPL MSFT'
    )
    parser.add_argument(
        '--interval', type=int, default=1800,
        help='刷新间隔（秒），默认1800（30分钟）'
    )
    args = parser.parse_args()

    if args.stocks:
        stocks = parse_stocks(args.stocks)
    else:
        stocks = DEFAULT_STOCKS

    if not stocks:
        print("错误: 没有指定监控股票")
        return

    try:
        run_monitor(stocks, args.interval)
    except KeyboardInterrupt:
        print("\n\n监控已停止。")


if __name__ == "__main__":
    main()
