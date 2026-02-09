"""
数据持久化存储模块（SQLite）。

所有监控数据存储在 C:/quant_backtest/data.db 中，包含三张表:
    1. quotes    - 每次扫描的行情快照（价格、RSI、均线等）
    2. signals   - 检测到的交易信号
    3. scan_logs - 扫描日志

使用方法:
    from quant_backtest.storage import Storage
    db = Storage()
    db.save_quote(...)
    df = db.get_quotes("600519", limit=100)
"""

import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd

# 数据库文件路径
DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')


class Storage:
    """SQLite 数据存储"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_conn()
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT,
                market TEXT,
                price REAL,
                change_pct REAL,
                rsi REAL,
                sma5 REAL,
                sma20 REAL,
                volume REAL
            );

            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT,
                direction TEXT,
                strategy TEXT,
                reason TEXT,
                price REAL
            );

            CREATE TABLE IF NOT EXISTS scan_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                level TEXT,
                message TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_quotes_symbol ON quotes(symbol);
            CREATE INDEX IF NOT EXISTS idx_quotes_time ON quotes(time);
            CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
            CREATE INDEX IF NOT EXISTS idx_signals_time ON signals(time);
        ''')
        conn.commit()
        conn.close()

    # ---- 写入 ----

    def save_quote(self, symbol: str, name: str, market: str,
                   price: float, change_pct: float,
                   rsi: float, sma5: float, sma20: float,
                   volume: float = 0):
        """保存一条行情快照"""
        conn = self._get_conn()
        conn.execute(
            '''INSERT INTO quotes (time, symbol, name, market, price, change_pct, rsi, sma5, sma20, volume)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
             symbol, name, market, price, change_pct, rsi, sma5, sma20, volume)
        )
        conn.commit()
        conn.close()

    def save_signal(self, symbol: str, name: str,
                    direction: str, strategy: str,
                    reason: str, price: float):
        """保存一条交易信号"""
        conn = self._get_conn()
        conn.execute(
            '''INSERT INTO signals (time, symbol, name, direction, strategy, reason, price)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
             symbol, name, direction, strategy, reason, price)
        )
        conn.commit()
        conn.close()

    def save_log(self, level: str, message: str):
        """保存一条扫描日志"""
        conn = self._get_conn()
        conn.execute(
            '''INSERT INTO scan_logs (time, level, message)
               VALUES (?, ?, ?)''',
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), level, message)
        )
        conn.commit()
        conn.close()

    # ---- 查询 ----

    def get_quotes(self, symbol: Optional[str] = None,
                   limit: int = 200) -> pd.DataFrame:
        """
        查询行情记录。
        symbol=None 时返回所有股票的记录。
        """
        conn = self._get_conn()
        if symbol:
            df = pd.read_sql_query(
                'SELECT * FROM quotes WHERE symbol=? ORDER BY time DESC LIMIT ?',
                conn, params=(symbol, limit)
            )
        else:
            df = pd.read_sql_query(
                'SELECT * FROM quotes ORDER BY time DESC LIMIT ?',
                conn, params=(limit,)
            )
        conn.close()
        return df

    def get_signals(self, symbol: Optional[str] = None,
                    limit: int = 100) -> pd.DataFrame:
        """查询交易信号"""
        conn = self._get_conn()
        if symbol:
            df = pd.read_sql_query(
                'SELECT * FROM signals WHERE symbol=? ORDER BY time DESC LIMIT ?',
                conn, params=(symbol, limit)
            )
        else:
            df = pd.read_sql_query(
                'SELECT * FROM signals ORDER BY time DESC LIMIT ?',
                conn, params=(limit,)
            )
        conn.close()
        return df

    def get_logs(self, limit: int = 200) -> pd.DataFrame:
        """查询扫描日志"""
        conn = self._get_conn()
        df = pd.read_sql_query(
            'SELECT * FROM scan_logs ORDER BY time DESC LIMIT ?',
            conn, params=(limit,)
        )
        conn.close()
        return df

    def clear_data(self, tables: List[str] = None):
        """
        清空数据。
        tables: 要清空的表名列表，如 ['quotes','signals','scan_logs']
                None 则清空全部三张表
        """
        allowed = {'quotes', 'signals', 'scan_logs'}
        if tables is None:
            tables = list(allowed)
        conn = self._get_conn()
        for t in tables:
            if t in allowed:
                conn.execute(f'DELETE FROM {t}')
        conn.commit()
        conn.execute('VACUUM')          # 回收磁盘空间
        conn.close()

    def get_stats(self) -> Dict:
        """获取数据库统计信息"""
        conn = self._get_conn()
        cur = conn.cursor()
        quotes_count = cur.execute('SELECT COUNT(*) FROM quotes').fetchone()[0]
        signals_count = cur.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
        logs_count = cur.execute('SELECT COUNT(*) FROM scan_logs').fetchone()[0]

        # 数据库文件大小
        db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        conn.close()

        return {
            'quotes_count': quotes_count,
            'signals_count': signals_count,
            'logs_count': logs_count,
            'db_size_kb': round(db_size / 1024, 1),
            'db_path': self.db_path,
        }
