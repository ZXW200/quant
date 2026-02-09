# QuantMonitor - 量化监控系统

一个功能完整的量化交易监控与回测系统，支持 **A股、美股、外汇、大宗商品** 的实时监控、技术分析、策略回测和趋势预测。

提供 Web 控制面板（深色主题），双击 exe 即可在任意 Windows 电脑上运行，无需安装 Python。

---

## 功能亮点

- **实时监控** - 18+ 标的同时监控，WebSocket 实时推送行情和信号
- **K线图表** - TradingView 风格专业K线，叠加均线/布林带/买卖标记
- **策略回测** - SMA交叉 / RSI / 布林带 / 买入持有 四策略对比，资金曲线可视化
- **趋势预测** - 机器学习(随机森林) + 多指标评分 + 支撑阻力位，三维度分析
- **邮件通知** - 检测到买卖信号时自动发送汇总邮件（SMTP）
- **一键打包** - PyInstaller 打包为单个 exe，复制到任意电脑双击即用
- **双数据源** - akshare(东方财富) + yfinance(雅虎财经) 自动回退，确保数据可用
- **人民币计价** - 黄金白银自动换算为 人民币/克

---

## 功能页面

### 实时监控
左侧股票列表实时更新价格、涨跌幅、RSI 指标。右侧实时日志流，信号触发时高亮提示。支持一键启停监控、调整刷新间隔。

### K线图表
TradingView lightweight-charts 渲染的专业K线图，支持：
- MA5 / MA20 均线叠加
- 布林带上下轨
- 买入(绿色箭头) / 卖出(红色箭头) 信号标记
- 自定义时间范围

### 回测对比
四种策略同时回测并对比：
- **SMA交叉(5/20)** - 金叉买入，死叉卖出
- **RSI(14)** - 超卖(<30)买入，超买(>70)卖出
- **布林带(20,2)** - 触碰下轨买入，上轨卖出
- **买入持有(基准)** - 第一天买入持有到最后

展示总收益率、交易次数、胜率、最大回撤、资金曲线图。

### 趋势预测
三种预测方法综合分析：
- **机器学习** - RandomForest 分类器，10个特征，输出涨跌概率和置信度
- **指标评分** - 5大指标(SMA/RSI/布林带/MACD/成交量) 综合打分 -100~+100
- **支撑阻力** - 经典 Pivot Point + 近期高低点，3档支撑位 + 3档阻力位

### 历史行情 & 历史信号
查看所有历史价格记录和交易信号记录，支持数据清空。

---

## 快速开始

### 方式一：exe 直接运行（推荐）

1. 从 Releases 下载 `量化监控.exe`
2. 双击运行
3. 打开浏览器访问 **http://127.0.0.1:5000**
4. 点击「开始监控」

> 数据库 `data.db` 会自动创建在 exe 同目录下。

### 方式二：Python 运行

```bash
# 克隆项目
git clone https://github.com/yourname/quant_backtest.git
cd quant_backtest

# 安装依赖
pip install -r requirements.txt
pip install flask flask-socketio scikit-learn

# 启动 Web 服务器
python web_server.py

# 指定端口
python web_server.py 5001
```

打开浏览器访问 **http://127.0.0.1:5000**

### 方式三：命令行监控

```bash
python monitor.py
```

---

## 打包为 exe

```bash
python build_exe.py
```

生成 `dist/量化监控.exe`，可复制到任意 Windows 电脑直接运行。

---

## 项目结构

```
quant_backtest/
├── web_server.py              # Web 服务器主程序（Flask + SocketIO）
├── prediction.py              # 趋势预测模块（ML + 评分 + 支撑阻力）
├── storage.py                 # SQLite 数据持久化
├── monitor.py                 # 命令行监控工具
├── build_exe.py               # PyInstaller 打包脚本
├── requirements.txt           # 依赖列表
│
├── strategy/                  # 交易策略
│   ├── indicators.py          # 技术指标（SMA/EMA/RSI/MACD/布林带）
│   ├── base.py                # 策略基类
│   ├── sma_cross.py           # 均线交叉策略
│   ├── rsi_strategy.py        # RSI 策略
│   └── bollinger_strategy.py  # 布林带策略
│
├── engine/                    # 事件驱动回测引擎
│   ├── engine.py              # 回测主循环
│   ├── event.py               # 事件类型（Market/Signal/Order/Fill）
│   └── portfolio.py           # 组合管理（资金/持仓）
│
├── broker/                    # 交易执行
│   ├── base.py                # Broker 抽象基类（预留实盘接口）
│   ├── simulated.py           # 模拟 Broker
│   └── order.py               # 订单结构
│
├── analysis/                  # 绩效分析
│   ├── metrics.py             # 夏普比率、最大回撤、胜率等
│   ├── report.py              # 报告生成
│   └── result.py              # 回测结果封装
│
├── data/                      # 数据获取
│   ├── astock.py              # A股数据
│   └── us_stock.py            # 美股数据
│
├── web/templates/
│   └── index.html             # Web 控制面板前端
│
└── examples/                  # 使用示例
    ├── example_sma.py         # 均线交叉回测
    ├── example_rsi.py         # RSI 策略回测
    └── example_us_stock.py    # 美股回测
```

---

## 技术栈

| 模块 | 技术 |
|------|------|
| 后端 | Python, Flask, Flask-SocketIO |
| 前端 | HTML/CSS/JS, lightweight-charts (TradingView) |
| 数据源 | akshare (A股), yfinance (美股/外汇/商品) |
| 数据库 | SQLite |
| 机器学习 | scikit-learn (RandomForestClassifier) |
| 实时通信 | WebSocket (Socket.IO) |
| 打包 | PyInstaller |

---

## 支持的市场与标的

### 默认监控列表

| 市场 | 标的 |
|------|------|
| A股 | 贵州茅台、平安银行、招商银行、五粮液、中国平安、宁德时代、比亚迪 |
| 美股 | AAPL、MSFT、GOOGL、AMZN、TSLA、NVDA、META |
| 大宗商品 | 黄金(GC=F)、白银(SI=F) + 自动换算人民币/克 |
| 外汇 | 美元/人民币(USDCNY=X)、英镑/人民币(GBPCNY=X) |

### 添加自定义标的

在 Web 界面左侧面板「添加股票」输入：
- A股：6位代码，如 `000002`
- 美股：英文代码，如 `NFLX`
- 外汇：带 `=X` 后缀，如 `EURUSD=X`

---

## API 参考

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 获取监控状态 |
| `/api/start` | POST | 启动监控 |
| `/api/stop` | POST | 停止监控 |
| `/api/stocks` | GET | 获取监控列表 |
| `/api/stocks` | POST | 添加标的 |
| `/api/stocks/<symbol>` | DELETE | 删除标的 |
| `/api/interval` | POST | 设置刷新间隔 |
| `/api/chart/<symbol>` | GET | 获取K线+指标+信号 |
| `/api/backtest/<symbol>` | GET | 运行策略回测对比 |
| `/api/predict/<symbol>` | GET | 获取趋势预测 |
| `/api/predict/all` | GET | 获取所有标的预测 |
| `/api/db/stats` | GET | 数据库统计 |
| `/api/db/clear` | POST | 清空数据 |
| `/api/email/config` | GET/POST | 邮件配置 |
| `/api/email/test` | POST | 发送测试邮件 |
| `/api/history/quotes` | GET | 历史行情记录 |
| `/api/history/signals` | GET | 历史信号记录 |

---

## 配置说明

### 邮件通知

在 Web 界面左侧「邮件通知」面板配置：

1. 启用 → 选择「开」
2. SMTP 服务器 → `smtp.qq.com`（QQ邮箱）
3. 端口 → `465`
4. 发件人邮箱 → 你的邮箱
5. 密码 → **邮箱授权码**（不是登录密码）
6. 收件人邮箱
7. 保存 → 发送测试

每次扫描结束后，如果有信号，会汇总为一封邮件发送，包含所有买入/卖出信号的表格。

**获取授权码：**
- QQ邮箱：设置 → 账户 → 开启 IMAP/SMTP → 获取授权码
- 163邮箱：设置 → POP3/SMTP → 开启 → 设置授权密码
- Gmail：安全性 → 应用专用密码

### 刷新间隔

默认 30 分钟扫描一次，可在 Web 界面调整（30秒 ~ 24小时）。

---

## 信号策略说明

| 策略 | 买入条件 | 卖出条件 |
|------|----------|----------|
| SMA交叉(5/20) | 5日均线上穿20日均线（金叉） | 5日均线下穿20日均线（死叉） |
| RSI(14) | RSI < 30（超卖） | RSI > 70（超买） |
| 布林带(20,2) | 价格触碰下轨 | 价格触碰上轨 |

---

## 依赖安装

```bash
pip install -r requirements.txt
pip install flask flask-socketio scikit-learn
```

核心依赖：
- `pandas` / `numpy` - 数据处理
- `akshare` - A股数据（东方财富）
- `yfinance` - 美股/外汇/商品数据（雅虎财经）
- `flask` / `flask-socketio` - Web 服务器
- `scikit-learn` - 机器学习预测

---

## 免责声明

本项目仅供 **学习和研究** 使用，不构成任何投资建议。

- 预测结果和交易信号仅基于历史数据的技术分析，不保证未来收益
- 量化策略存在过拟合风险，回测表现不代表实盘结果
- 投资有风险，使用本系统产生的任何损失由使用者自行承担

---

## License

MIT
