"""
量化监控 Web 服务器。
提供前端控制面板，支持实时日志推送、启停监控、增删股票。
"""

import sys
import os
import time
import threading
from datetime import datetime, timedelta

# ---- 路径处理（兼容 PyInstaller 打包） ----
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后: 资源在 sys._MEIPASS, 运行目录用 exe 所在目录
    BASE_DIR = sys._MEIPASS
    RUN_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RUN_DIR = BASE_DIR
    sys.path.insert(0, os.path.dirname(BASE_DIR))

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO

import pandas as pd
from quant_backtest.strategy.indicators import sma, rsi, bollinger_bands
from quant_backtest.storage import Storage
from quant_backtest.prediction import full_prediction

# 数据库放在运行目录（exe 旁边），这样数据不会丢
db = Storage(db_path=os.path.join(RUN_DIR, 'data.db'))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'web', 'templates'),
    static_folder=os.path.join(BASE_DIR, 'web', 'static'),
)
app.config['SECRET_KEY'] = 'quant-monitor-2024'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')


# ============================================================
#  全局状态
# ============================================================

class MonitorState:
    """监控全局状态"""
    def __init__(self):
        self.running = False
        self.thread = None
        self.interval = 1800  # 默认30分钟
        self.stocks = [
            # A股
            {"symbol": "600519",    "name": "贵州茅台",    "market": "A"},
            {"symbol": "000001",    "name": "平安银行",    "market": "A"},
            {"symbol": "600036",    "name": "招商银行",    "market": "A"},
            {"symbol": "000858",    "name": "五粮液",      "market": "A"},
            {"symbol": "601318",    "name": "中国平安",    "market": "A"},
            {"symbol": "300750",    "name": "宁德时代",    "market": "A"},
            {"symbol": "002594",    "name": "比亚迪",      "market": "A"},
            # 美股大公司
            {"symbol": "AAPL",      "name": "苹果",        "market": "US"},
            {"symbol": "MSFT",      "name": "微软",        "market": "US"},
            {"symbol": "GOOGL",     "name": "谷歌",        "market": "US"},
            {"symbol": "AMZN",      "name": "亚马逊",      "market": "US"},
            {"symbol": "TSLA",      "name": "特斯拉",      "market": "US"},
            {"symbol": "NVDA",      "name": "英伟达",      "market": "US"},
            {"symbol": "META",      "name": "Meta",        "market": "US"},
            # 商品
            {"symbol": "GC=F",      "name": "黄金(USD)",   "market": "US"},
            {"symbol": "SI=F",      "name": "白银(USD)",   "market": "US"},
            # 汇率
            {"symbol": "USDCNY=X",  "name": "美元/人民币",  "market": "FX"},
            {"symbol": "GBPCNY=X",  "name": "英镑/人民币",  "market": "FX"},
        ]
        self.last_signals = {}  # 避免重复信号
        self.scan_count = 0
        self.usdcny_rate = None  # 缓存美元兑人民币汇率

state = MonitorState()


# ============================================================
#  数据获取
# ============================================================

def _fetch_a_share(symbol, start_date, end_date):
    """
    获取A股K线数据。
    优先 akshare(东方财富)，失败则回退 yfinance(雅虎财经)。
    """
    # ---- 方案1: akshare ----
    try:
        import akshare as ak
        start_fmt = start_date.replace("-", "")
        end_fmt = end_date.replace("-", "")
        df = ak.stock_zh_a_hist(
            symbol=symbol, period="daily",
            start_date=start_fmt, end_date=end_fmt, adjust="qfq"
        )
        if df is not None and not df.empty:
            col_map = {
                '日期': 'datetime', '开盘': 'open', '收盘': 'close',
                '最高': 'high', '最低': 'low', '成交量': 'volume',
            }
            df = df.rename(columns=col_map)
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime')
            df = df[['open', 'high', 'low', 'close', 'volume']]
            return df
    except Exception:
        pass  # akshare 失败，回退到 yfinance

    # ---- 方案2: yfinance (上交所=.SS 深交所=.SZ) ----
    try:
        import yfinance as yf
        suffix = '.SS' if symbol.startswith('6') else '.SZ'
        yf_symbol = symbol + suffix
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(start=start_date, end=end_date)
        if df is not None and not df.empty:
            df.columns = [c.lower() for c in df.columns]
            keep = [c for c in ['open', 'high', 'low', 'close', 'volume'] if c in df.columns]
            df = df[keep]
            df.index.name = 'datetime'
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            return df
    except Exception as e:
        emit_log(f"[错误] yfinance 获取 {symbol} 失败: {e}", "error")

    return None


def fetch_data(symbol, market, days=120):
    """获取最近 N 天K线数据"""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")

    try:
        if market == "A":
            df = _fetch_a_share(symbol, start_date, end_date)
            if df is None:
                return None
        elif market in ("US", "FX"):
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date)
            if df is None or df.empty:
                return None
            df.columns = [c.lower() for c in df.columns]
            keep = [c for c in ['open', 'high', 'low', 'close', 'volume'] if c in df.columns]
            df = df[keep]
            df.index.name = 'datetime'
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            # 外汇数据通常无成交量，补0
            if 'volume' not in df.columns:
                df['volume'] = 0
        else:
            return None

        df = df.tail(days)
        if len(df) < 30:
            return None
        return df
    except Exception as e:
        emit_log(f"[错误] 获取 {symbol} 数据失败: {e}", "error")
        return None


# ============================================================
#  信号检测
# ============================================================

def detect_signals(symbol, df):
    """检测所有策略信号"""
    signals = []
    close = df['close']

    # SMA 交叉
    if len(df) >= 21:
        sma5 = sma(close, 5)
        sma20 = sma(close, 20)
        s_now, l_now = sma5.iloc[-1], sma20.iloc[-1]
        s_prev, l_prev = sma5.iloc[-2], sma20.iloc[-2]
        key = f"{symbol}_SMA"
        if s_prev <= l_prev and s_now > l_now:
            if is_new_signal(key, "BUY"):
                signals.append({
                    "strategy": "SMA交叉(5/20)", "direction": "BUY",
                    "reason": f"5日均线({s_now:.2f})上穿20日均线({l_now:.2f})",
                    "price": float(close.iloc[-1]),
                })
        elif s_prev >= l_prev and s_now < l_now:
            if is_new_signal(key, "SELL"):
                signals.append({
                    "strategy": "SMA交叉(5/20)", "direction": "SELL",
                    "reason": f"5日均线({s_now:.2f})下穿20日均线({l_now:.2f})",
                    "price": float(close.iloc[-1]),
                })

    # RSI
    if len(df) >= 15:
        rsi_val = rsi(close, 14).iloc[-1]
        key = f"{symbol}_RSI"
        if rsi_val < 30:
            if is_new_signal(key, "BUY"):
                signals.append({
                    "strategy": "RSI(14)", "direction": "BUY",
                    "reason": f"RSI={rsi_val:.1f} < 30 (超卖)",
                    "price": float(close.iloc[-1]),
                })
        elif rsi_val > 70:
            if is_new_signal(key, "SELL"):
                signals.append({
                    "strategy": "RSI(14)", "direction": "SELL",
                    "reason": f"RSI={rsi_val:.1f} > 70 (超买)",
                    "price": float(close.iloc[-1]),
                })
        else:
            state.last_signals.pop(key, None)

    # 布林带
    if len(df) >= 21:
        upper, middle, lower = bollinger_bands(close, 20, 2.0)
        c = float(close.iloc[-1])
        u, l = float(upper.iloc[-1]), float(lower.iloc[-1])
        key = f"{symbol}_BOLL"
        if c <= l:
            if is_new_signal(key, "BUY"):
                signals.append({
                    "strategy": "布林带(20,2)", "direction": "BUY",
                    "reason": f"价格({c:.2f})触及下轨({l:.2f})",
                    "price": c,
                })
        elif c >= u:
            if is_new_signal(key, "SELL"):
                signals.append({
                    "strategy": "布林带(20,2)", "direction": "SELL",
                    "reason": f"价格({c:.2f})触及上轨({u:.2f})",
                    "price": c,
                })
        else:
            state.last_signals.pop(key, None)

    return signals


def is_new_signal(key, direction):
    """避免同一信号重复提醒"""
    if state.last_signals.get(key) == direction:
        return False
    state.last_signals[key] = direction
    return True


def get_stock_info(df, decimals=2):
    """计算当前行情摘要"""
    close = float(df['close'].iloc[-1])
    prev_close = float(df['close'].iloc[-2])
    change = (close - prev_close) / prev_close * 100
    rsi_val = float(rsi(df['close'], 14).iloc[-1])
    sma5_val = float(sma(df['close'], 5).iloc[-1])
    sma20_val = float(sma(df['close'], 20).iloc[-1])
    return {
        "price": round(close, decimals),
        "change": round(change, 2),
        "rsi": round(rsi_val, 1),
        "sma5": round(sma5_val, decimals),
        "sma20": round(sma20_val, decimals),
    }


def fetch_usdcny_rate():
    """获取最新美元兑人民币汇率"""
    try:
        import yfinance as yf
        ticker = yf.Ticker("USDCNY=X")
        df = ticker.history(period="5d")
        if df is not None and not df.empty:
            rate = float(df['Close'].iloc[-1])
            state.usdcny_rate = rate
            return rate
    except Exception as e:
        emit_log(f"[警告] 获取美元/人民币汇率失败: {e}", "warning")
    return state.usdcny_rate  # 返回缓存值


def push_rmb_commodity(symbol_usd, name_rmb, usdcny_rate, df_usd):
    """
    将美元计价的商品转换为人民币价格并推送。
    黄金: 美元/盎司 → 人民币/克 (1盎司=31.1035克)
    白银: 美元/盎司 → 人民币/克
    """
    if df_usd is None or usdcny_rate is None:
        return

    oz_to_gram = 31.1035
    # 转换为人民币/克
    df_rmb = df_usd.copy()
    for col in ['open', 'high', 'low', 'close']:
        if col in df_rmb.columns:
            df_rmb[col] = df_rmb[col] * usdcny_rate / oz_to_gram

    rmb_symbol = symbol_usd.replace("=F", "_CNY")
    info = get_stock_info(df_rmb, decimals=2)

    stock_rmb = {"symbol": rmb_symbol, "name": name_rmb, "market": "CNY"}
    emit_quote(stock_rmb, info)
    try:
        db.save_quote(
            symbol=rmb_symbol, name=name_rmb,
            market="CNY", price=info['price'],
            change_pct=info['change'], rsi=info['rsi'],
            sma5=info['sma5'], sma20=info['sma20'],
            volume=0
        )
    except Exception:
        pass
    emit_log(
        f"{name_rmb} 价格:{info['price']}元/克 "
        f"({'+' if info['change'] >= 0 else ''}{info['change']:.2f}%) "
        f"RSI:{info['rsi']}"
    )

    # 信号检测
    signals = detect_signals(rmb_symbol, df_rmb)
    for sig in signals:
        emit_signal(stock_rmb, sig)
        direction_cn = "买入" if sig['direction'] == 'BUY' else "卖出"
        emit_log(
            f"!!! {direction_cn}信号 !!! {name_rmb} - "
            f"{sig['strategy']}: {sig['reason']}",
            "signal"
        )
        try:
            db.save_signal(
                symbol=rmb_symbol, name=name_rmb,
                direction=sig['direction'], strategy=sig['strategy'],
                reason=sig['reason'], price=sig['price']
            )
        except Exception:
            pass


# ============================================================
#  日志推送
# ============================================================

def emit_log(message, level="info"):
    """通过 WebSocket 推送日志到前端，同时存入数据库"""
    now = datetime.now().strftime("%H:%M:%S")
    socketio.emit('log', {
        'time': now,
        'message': message,
        'level': level,
    })
    try:
        db.save_log(level, message)
    except Exception:
        pass


def emit_signal(stock, signal):
    """推送交易信号到前端"""
    now = datetime.now().strftime("%H:%M:%S")
    socketio.emit('signal', {
        'time': now,
        'symbol': stock['symbol'],
        'name': stock['name'],
        'direction': signal['direction'],
        'strategy': signal['strategy'],
        'reason': signal['reason'],
        'price': signal['price'],
    })


def emit_quote(stock, info):
    """推送行情数据到前端"""
    socketio.emit('quote', {
        'symbol': stock['symbol'],
        'name': stock['name'],
        'market': stock['market'],
        **info,
    })


# ============================================================
#  监控线程
# ============================================================

def monitor_loop():
    """监控主循环（在后台线程运行）"""
    emit_log("监控已启动", "success")
    emit_log(f"监控标的: {', '.join(s['name']+'('+s['symbol']+')' for s in state.stocks)}")
    emit_log(f"刷新间隔: {state.interval} 秒")

    while state.running:
        state.scan_count += 1
        emit_log(f"--- 第 {state.scan_count} 次扫描 ---", "info")

        # 先获取美元/人民币汇率（用于后续人民币换算）
        emit_log("获取美元/人民币汇率...")
        usdcny = fetch_usdcny_rate()
        if usdcny:
            emit_log(f"当前汇率: 1 USD = {usdcny:.4f} CNY")
        else:
            emit_log("汇率获取失败，人民币价格将跳过", "warning")

        # 缓存美元商品数据，用于后续人民币换算
        commodity_data = {}  # symbol -> df
        # 本轮所有信号收集（用于汇总邮件）
        all_signals_this_scan = []

        for stock in list(state.stocks):
            if not state.running:
                break

            emit_log(f"获取 {stock['name']}({stock['symbol']}) 数据...")
            df = fetch_data(stock['symbol'], stock['market'])

            if df is None:
                emit_log(f"{stock['symbol']} 数据获取失败", "warning")
                continue

            # 外汇用4位小数，其它用2位
            decimals = 4 if stock['market'] == 'FX' else 2

            # 推送行情并存入数据库
            info = get_stock_info(df, decimals=decimals)
            emit_quote(stock, info)
            try:
                vol = float(df['volume'].iloc[-1]) if 'volume' in df.columns else 0
                db.save_quote(
                    symbol=stock['symbol'], name=stock['name'],
                    market=stock['market'], price=info['price'],
                    change_pct=info['change'], rsi=info['rsi'],
                    sma5=info['sma5'], sma20=info['sma20'],
                    volume=vol
                )
            except Exception:
                pass

            change_str = f"+{info['change']:.2f}%" if info['change'] >= 0 else f"{info['change']:.2f}%"
            emit_log(
                f"{stock['name']} 价格:{info['price']} ({change_str}) "
                f"RSI:{info['rsi']} MA5:{info['sma5']} MA20:{info['sma20']}"
            )

            # 缓存黄金/白银的USD数据
            if stock['symbol'] in ('GC=F', 'SI=F'):
                commodity_data[stock['symbol']] = df

            # 检测信号
            signals = detect_signals(stock['symbol'], df)
            for sig in signals:
                emit_signal(stock, sig)
                direction_cn = "买入" if sig['direction'] == 'BUY' else "卖出"
                emit_log(
                    f"!!! {direction_cn}信号 !!! {stock['name']} - "
                    f"{sig['strategy']}: {sig['reason']}",
                    "signal"
                )
                try:
                    db.save_signal(
                        symbol=stock['symbol'], name=stock['name'],
                        direction=sig['direction'], strategy=sig['strategy'],
                        reason=sig['reason'], price=sig['price']
                    )
                except Exception:
                    pass
                # 收集信号用于汇总邮件
                all_signals_this_scan.append({
                    'name': stock['name'], 'symbol': stock['symbol'],
                    'direction': direction_cn, 'strategy': sig['strategy'],
                    'price': sig['price'], 'reason': sig['reason'],
                })

        # 推送人民币计价的黄金/白银
        if usdcny and state.running:
            if 'GC=F' in commodity_data:
                push_rmb_commodity('GC=F', '黄金(人民币/克)', usdcny, commodity_data['GC=F'])
            if 'SI=F' in commodity_data:
                push_rmb_commodity('SI=F', '白银(人民币/克)', usdcny, commodity_data['SI=F'])

        # 汇总发送一封邮件（本轮所有信号）
        if all_signals_this_scan:
            try:
                buy_list = [s for s in all_signals_this_scan if s['direction'] == '买入']
                sell_list = [s for s in all_signals_this_scan if s['direction'] == '卖出']
                now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
                subject = f"[量化监控] 第{state.scan_count}次扫描: {len(buy_list)}个买入 {len(sell_list)}个卖出"
                rows = ""
                for s in all_signals_this_scan:
                    color = '#2dd4bf' if s['direction'] == '买入' else '#f87171'
                    rows += (
                        f"<tr>"
                        f"<td style='padding:8px;border-bottom:1px solid #333;color:{color};font-weight:bold'>{s['direction']}</td>"
                        f"<td style='padding:8px;border-bottom:1px solid #333'>{s['name']}({s['symbol']})</td>"
                        f"<td style='padding:8px;border-bottom:1px solid #333'>{s['strategy']}</td>"
                        f"<td style='padding:8px;border-bottom:1px solid #333'>{s['price']}</td>"
                        f"<td style='padding:8px;border-bottom:1px solid #333'>{s['reason']}</td>"
                        f"</tr>"
                    )
                body = (
                    f"<div style='font-family:Arial,sans-serif;max-width:700px;margin:0 auto;background:#1a1a2e;color:#eee;padding:20px;border-radius:8px'>"
                    f"<h2 style='color:#58a6ff;margin-bottom:4px'>量化监控信号汇总</h2>"
                    f"<p style='color:#888;margin-top:0'>扫描时间: {now_str} | 第 {state.scan_count} 次扫描</p>"
                    f"<table style='width:100%;border-collapse:collapse;margin:16px 0'>"
                    f"<tr style='background:#2a2a3e'>"
                    f"<th style='padding:8px;text-align:left;border-bottom:2px solid #444'>方向</th>"
                    f"<th style='padding:8px;text-align:left;border-bottom:2px solid #444'>标的</th>"
                    f"<th style='padding:8px;text-align:left;border-bottom:2px solid #444'>策略</th>"
                    f"<th style='padding:8px;text-align:left;border-bottom:2px solid #444'>价格</th>"
                    f"<th style='padding:8px;text-align:left;border-bottom:2px solid #444'>原因</th>"
                    f"</tr>"
                    f"{rows}"
                    f"</table>"
                    f"<p style='color:#666;font-size:12px;margin-top:16px'>— 量化监控系统自动发送</p>"
                    f"</div>"
                )
                send_email_notification(subject, body)
            except Exception:
                pass

        if state.running:
            emit_log(f"下次扫描: {state.interval} 秒后...")
            # 分段 sleep 以便及时响应停止
            for _ in range(state.interval):
                if not state.running:
                    break
                time.sleep(1)

    emit_log("监控已停止", "warning")


# ============================================================
#  Flask 路由
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    return jsonify({
        'running': state.running,
        'interval': state.interval,
        'stocks': state.stocks,
        'scan_count': state.scan_count,
    })


@app.route('/api/start', methods=['POST'])
def api_start():
    if state.running:
        return jsonify({'ok': False, 'msg': '监控已在运行'})

    data = request.get_json(silent=True) or {}
    state.interval = int(data.get('interval', state.interval))
    state.running = True
    state.scan_count = 0
    state.last_signals.clear()

    state.thread = threading.Thread(target=monitor_loop, daemon=True)
    state.thread.start()

    return jsonify({'ok': True, 'msg': '监控已启动'})


@app.route('/api/stop', methods=['POST'])
def api_stop():
    if not state.running:
        return jsonify({'ok': False, 'msg': '监控未在运行'})

    state.running = False
    return jsonify({'ok': True, 'msg': '正在停止...'})


@app.route('/api/stocks', methods=['GET'])
def api_get_stocks():
    return jsonify(state.stocks)


@app.route('/api/stocks', methods=['POST'])
def api_add_stock():
    data = request.get_json()
    symbol = data.get('symbol', '').strip()
    name = data.get('name', '').strip()

    if not symbol:
        return jsonify({'ok': False, 'msg': '代码不能为空'})

    # 判断市场类型
    if symbol.isdigit() and len(symbol) == 6:
        market = "A"
    else:
        symbol = symbol.upper()
        if symbol.endswith("=X"):
            market = "FX"  # 外汇
        else:
            market = "US"

    if not name:
        name = symbol

    # 检查重复
    for s in state.stocks:
        if s['symbol'] == symbol:
            return jsonify({'ok': False, 'msg': f'{symbol} 已在监控列表中'})

    stock = {"symbol": symbol, "name": name, "market": market}
    state.stocks.append(stock)
    emit_log(f"已添加监控: {name}({symbol})", "success")
    return jsonify({'ok': True, 'stock': stock})


@app.route('/api/stocks/<symbol>', methods=['DELETE'])
def api_remove_stock(symbol):
    before = len(state.stocks)
    state.stocks = [s for s in state.stocks if s['symbol'] != symbol]
    if len(state.stocks) < before:
        emit_log(f"已移除监控: {symbol}", "warning")
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'msg': '未找到该股票'})


@app.route('/api/interval', methods=['POST'])
def api_set_interval():
    data = request.get_json()
    state.interval = int(data.get('interval', 1800))
    emit_log(f"刷新间隔已更新为 {state.interval} 秒")
    return jsonify({'ok': True, 'interval': state.interval})


@app.route('/api/history/quotes')
def api_history_quotes():
    """查询历史行情记录"""
    symbol = request.args.get('symbol')
    limit = int(request.args.get('limit', 200))
    df = db.get_quotes(symbol, limit)
    return jsonify(df.to_dict(orient='records'))


@app.route('/api/history/signals')
def api_history_signals():
    """查询历史交易信号"""
    symbol = request.args.get('symbol')
    limit = int(request.args.get('limit', 100))
    df = db.get_signals(symbol, limit)
    return jsonify(df.to_dict(orient='records'))


@app.route('/api/db/stats')
def api_db_stats():
    """数据库统计信息"""
    return jsonify(db.get_stats())


@app.route('/api/db/clear', methods=['POST'])
def api_db_clear():
    """清空数据库"""
    data = request.get_json(silent=True) or {}
    tables = data.get('tables', None)   # None = 全部清空
    try:
        db.clear_data(tables)
        stats = db.get_stats()
        socketio.emit('log', {
            'time': datetime.now().strftime('%H:%M:%S'),
            'msg': f"🗑️ 数据已清空: {', '.join(tables) if tables else '全部'}",
            'level': 'warning'
        })
        return jsonify({'ok': True, 'stats': stats})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/predict/<symbol>')
def api_predict(symbol):
    """对指定标的进行趋势预测"""
    # 从监控列表中找到该标的
    stock = None
    for s in state.stocks:
        if s['symbol'] == symbol:
            stock = s
            break

    if not stock:
        return jsonify({'error': f'{symbol} 不在监控列表中'})

    df = fetch_data(symbol, stock['market'], days=120)
    if df is None:
        return jsonify({'error': f'{symbol} 数据获取失败'})

    days = int(request.args.get('days', 3))
    result = full_prediction(df, symbol=symbol, forecast_days=days)
    result['name'] = stock['name']
    return jsonify(result)


@app.route('/api/predict/all')
def api_predict_all():
    """对所有监控标的进行预测"""
    results = []
    for stock in state.stocks:
        try:
            df = fetch_data(stock['symbol'], stock['market'], days=120)
            if df is None:
                results.append({'symbol': stock['symbol'], 'name': stock['name'], 'error': '数据获取失败'})
                continue
            pred = full_prediction(df, symbol=stock['symbol'], forecast_days=3)
            pred['name'] = stock['name']
            results.append(pred)
        except Exception as e:
            results.append({'symbol': stock['symbol'], 'name': stock['name'], 'error': str(e)})
    return jsonify(results)


@app.route('/api/chart/<symbol>')
def api_chart(symbol):
    """获取K线图表数据(OHLC+指标+信号)"""
    stock = None
    for s in state.stocks:
        if s['symbol'] == symbol:
            stock = s
            break
    if not stock:
        return jsonify({'error': f'{symbol} 不在监控列表中'})

    days = int(request.args.get('days', 60))
    df = fetch_data(symbol, stock['market'], days=days)
    if df is None:
        return jsonify({'error': '数据获取失败'})

    close = df['close']
    # K线数据
    candles = []
    for idx, row in df.iterrows():
        candles.append({
            'date': idx.strftime('%Y-%m-%d'),
            'open': round(float(row['open']), 4),
            'high': round(float(row['high']), 4),
            'low': round(float(row['low']), 4),
            'close': round(float(row['close']), 4),
            'volume': float(row.get('volume', 0)),
        })

    # 指标
    sma5_s = sma(close, 5)
    sma20_s = sma(close, 20)
    rsi_s = rsi(close, 14)
    upper, middle, lower = bollinger_bands(close, 20, 2.0)

    indicators = {
        'sma5': [round(float(v), 4) if not pd.isna(v) else None for v in sma5_s],
        'sma20': [round(float(v), 4) if not pd.isna(v) else None for v in sma20_s],
        'rsi': [round(float(v), 2) if not pd.isna(v) else None for v in rsi_s],
        'boll_upper': [round(float(v), 4) if not pd.isna(v) else None for v in upper],
        'boll_middle': [round(float(v), 4) if not pd.isna(v) else None for v in middle],
        'boll_lower': [round(float(v), 4) if not pd.isna(v) else None for v in lower],
    }

    # 买卖信号标记
    buy_signals = []
    sell_signals = []
    sma5_arr = sma5_s.values
    sma20_arr = sma20_s.values
    for i in range(1, len(df)):
        if i < 20:
            continue
        # SMA交叉信号
        if sma5_arr[i-1] <= sma20_arr[i-1] and sma5_arr[i] > sma20_arr[i]:
            buy_signals.append({'index': i, 'date': candles[i]['date'], 'price': candles[i]['close'], 'reason': 'SMA金叉'})
        elif sma5_arr[i-1] >= sma20_arr[i-1] and sma5_arr[i] < sma20_arr[i]:
            sell_signals.append({'index': i, 'date': candles[i]['date'], 'price': candles[i]['close'], 'reason': 'SMA死叉'})

    return jsonify({
        'symbol': symbol,
        'name': stock['name'],
        'candles': candles,
        'indicators': indicators,
        'buy_signals': buy_signals,
        'sell_signals': sell_signals,
    })


@app.route('/api/backtest/<symbol>')
def api_backtest(symbol):
    """对指定标的运行回测对比"""
    stock = None
    for s in state.stocks:
        if s['symbol'] == symbol:
            stock = s
            break
    if not stock:
        return jsonify({'error': f'{symbol} 不在监控列表中'})

    days = int(request.args.get('days', 120))
    capital = float(request.args.get('capital', 100000))
    df = fetch_data(symbol, stock['market'], days=days)
    if df is None:
        return jsonify({'error': '数据获取失败'})

    results = []
    close = df['close'].values.astype(float)
    dates = [d.strftime('%Y-%m-%d') for d in df.index]

    # 策略1: SMA交叉
    results.append(_run_simple_backtest(close, dates, capital, 'SMA交叉(5/20)', _sma_signals(df)))
    # 策略2: RSI
    results.append(_run_simple_backtest(close, dates, capital, 'RSI(14)', _rsi_signals(df)))
    # 策略3: 布林带
    results.append(_run_simple_backtest(close, dates, capital, '布林带(20,2)', _boll_signals(df)))
    # 基准: 买入持有
    buy_hold_return = (close[-1] / close[0] - 1) * 100
    results.append({
        'strategy': '买入持有(基准)',
        'total_return': round(buy_hold_return, 2),
        'trades': 1,
        'win_rate': 100.0 if buy_hold_return > 0 else 0.0,
        'max_drawdown': round(_calc_max_dd(close) * 100, 2),
        'equity_curve': [round(capital * close[i] / close[0], 2) for i in range(len(close))],
        'dates': dates,
    })

    return jsonify({
        'symbol': symbol,
        'name': stock['name'],
        'days': days,
        'capital': capital,
        'results': results,
    })


def _sma_signals(df):
    """SMA交叉信号列表: [(index, 'BUY'/'SELL'), ...]"""
    close = df['close']
    s5 = sma(close, 5).values
    s20 = sma(close, 20).values
    signals = []
    for i in range(21, len(df)):
        if s5[i-1] <= s20[i-1] and s5[i] > s20[i]:
            signals.append((i, 'BUY'))
        elif s5[i-1] >= s20[i-1] and s5[i] < s20[i]:
            signals.append((i, 'SELL'))
    return signals


def _rsi_signals(df):
    close = df['close']
    r = rsi(close, 14).values
    signals = []
    holding = False
    for i in range(15, len(df)):
        if not holding and r[i] < 30:
            signals.append((i, 'BUY'))
            holding = True
        elif holding and r[i] > 70:
            signals.append((i, 'SELL'))
            holding = False
    return signals


def _boll_signals(df):
    close = df['close']
    upper, middle, lower = bollinger_bands(close, 20, 2.0)
    u = upper.values
    l = lower.values
    c = close.values
    signals = []
    holding = False
    for i in range(21, len(df)):
        if not holding and c[i] <= l[i]:
            signals.append((i, 'BUY'))
            holding = True
        elif holding and c[i] >= u[i]:
            signals.append((i, 'SELL'))
            holding = False
    return signals


def _run_simple_backtest(close, dates, capital, name, signals):
    """简化回测引擎"""
    cash = capital
    shares = 0
    equity = [capital]
    trades = []
    buy_price = 0

    for i in range(1, len(close)):
        # 检查信号
        for si, sd in signals:
            if si == i:
                if sd == 'BUY' and shares == 0:
                    shares = int(cash / close[i])
                    buy_price = close[i]
                    cash -= shares * close[i]
                elif sd == 'SELL' and shares > 0:
                    cash += shares * close[i]
                    pnl = (close[i] - buy_price) / buy_price * 100
                    trades.append({'buy': buy_price, 'sell': close[i], 'pnl': round(pnl, 2)})
                    shares = 0
        equity.append(cash + shares * close[i])

    total_return = (equity[-1] / capital - 1) * 100
    wins = [t for t in trades if t['pnl'] > 0]
    win_rate = len(wins) / len(trades) * 100 if trades else 0

    # 最大回撤
    eq_arr = equity
    peak = eq_arr[0]
    max_dd = 0
    for v in eq_arr:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
        if dd > max_dd:
            max_dd = dd

    return {
        'strategy': name,
        'total_return': round(total_return, 2),
        'final_equity': round(equity[-1], 2),
        'trades': len(trades),
        'win_rate': round(win_rate, 1),
        'max_drawdown': round(max_dd * 100, 2),
        'equity_curve': [round(v, 2) for v in equity],
        'dates': dates,
        'trade_details': trades,
    }


def _calc_max_dd(close):
    peak = close[0]
    max_dd = 0
    for c in close:
        if c > peak:
            peak = c
        dd = (peak - c) / peak
        if dd > max_dd:
            max_dd = dd
    return max_dd


# ============================================================
#  邮件通知
# ============================================================

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 邮件配置 (用户需要修改为自己的邮箱信息)
EMAIL_CONFIG = {
    'enabled': False,           # 改为 True 启用邮件通知
    'smtp_server': 'smtp.qq.com',
    'smtp_port': 465,
    'sender': 'your_email@qq.com',
    'password': 'your_smtp_password',  # QQ邮箱用授权码
    'receiver': 'your_email@qq.com',
}


@app.route('/api/email/config', methods=['GET'])
def api_email_config_get():
    """获取邮件配置(隐藏密码)"""
    cfg = dict(EMAIL_CONFIG)
    cfg['password'] = '***' if cfg['password'] else ''
    return jsonify(cfg)


@app.route('/api/email/config', methods=['POST'])
def api_email_config_set():
    """更新邮件配置"""
    data = request.get_json()
    for key in ['enabled', 'smtp_server', 'smtp_port', 'sender', 'password', 'receiver']:
        if key in data:
            if key == 'password' and data[key] == '***':
                continue  # 不覆盖
            EMAIL_CONFIG[key] = data[key]
    emit_log(f"邮件配置已更新 (启用: {EMAIL_CONFIG['enabled']})", "success")
    return jsonify({'ok': True})


@app.route('/api/email/test', methods=['POST'])
def api_email_test():
    """发送测试邮件"""
    if not EMAIL_CONFIG['enabled']:
        return jsonify({'ok': False, 'msg': '请先启用邮件通知'})
    try:
        send_email_notification("测试邮件 - 量化监控", "<h2>测试成功</h2><p>邮件通知已配置正确！</p>")
        return jsonify({'ok': True, 'msg': '测试邮件已发送'})
    except Exception as e:
        return jsonify({'ok': False, 'msg': str(e)})


def send_email_notification(subject, body):
    """发送邮件通知"""
    cfg = EMAIL_CONFIG
    if not cfg['enabled']:
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = cfg['sender']
        msg['To'] = cfg['receiver']
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'html', 'utf-8'))

        server = smtplib.SMTP_SSL(cfg['smtp_server'], cfg['smtp_port'])
        server.login(cfg['sender'], cfg['password'])
        server.sendmail(cfg['sender'], cfg['receiver'], msg.as_string())
        server.quit()
        emit_log("邮件通知已发送", "success")
    except Exception as e:
        emit_log(f"邮件发送失败: {e}", "error")


# ============================================================
#  启动
# ============================================================

if __name__ == '__main__':
    print("=" * 50)
    print("  量化监控控制面板")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    print(f"  打开浏览器访问: http://127.0.0.1:{port}")
    print("  提示: 可用 py web_server.py 5001 指定其他端口")
    print("=" * 50)
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
