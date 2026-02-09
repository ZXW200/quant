"""
趋势预测模块。

包含三种预测方法:
    1. 机器学习预测 (随机森林) — 预测未来涨跌概率
    2. 多指标综合评分 — SMA/RSI/BOLL/MACD 打分，给出看涨/看跌/中性
    3. 支撑位/阻力位 — 根据历史价格计算关键价位

注意: 所有预测仅供学习参考，不构成投资建议。
"""

import numpy as np
import pandas as pd
from quant_backtest.strategy.indicators import sma, ema, rsi, bollinger_bands, macd


# ============================================================
#  1. 机器学习预测 (随机森林)
# ============================================================

def ml_predict(df, forecast_days=3):
    """
    使用随机森林预测未来涨跌概率。

    特征: 过去N天的收益率、RSI、SMA偏离度、波动率、成交量变化
    标签: 未来 forecast_days 天的涨跌 (1=涨, 0=跌)

    返回:
        {
            "up_prob": 0.65,        # 上涨概率
            "down_prob": 0.35,      # 下跌概率
            "direction": "看涨",    # 预测方向
            "confidence": "中等",   # 置信度
            "features": {...},      # 当前特征值
        }
    """
    try:
        from sklearn.ensemble import RandomForestClassifier
    except ImportError:
        return {"error": "需要安装 scikit-learn: pip install scikit-learn"}

    close = df['close'].values.astype(float)

    if len(close) < 60:
        return {"error": "数据不足，至少需要60根K线"}

    # ---- 构造特征 ----
    features = _build_features(df)
    if features is None:
        return {"error": "特征构造失败"}

    feature_df = features.dropna()
    if len(feature_df) < 40:
        return {"error": "有效数据不足"}

    # ---- 构造标签: 未来N天涨跌 ----
    future_return = df['close'].pct_change(forecast_days).shift(-forecast_days)
    labels = (future_return > 0).astype(int)

    # 合并特征和标签，去掉NaN
    combined = feature_df.copy()
    combined['label'] = labels
    combined = combined.dropna()

    if len(combined) < 30:
        return {"error": "训练数据不足"}

    X = combined.drop(columns=['label']).values
    y = combined['label'].values

    # 用前80%训练，后20%测试
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    # 训练随机森林
    model = RandomForestClassifier(
        n_estimators=100, max_depth=5,
        random_state=42, n_jobs=-1
    )
    model.fit(X_train, y_train)

    # 测试集准确率
    accuracy = model.score(X_test, y_test) if len(X_test) > 0 else 0

    # 预测当前（最新一行特征）
    latest_features = feature_df.iloc[-1:].values
    prob = model.predict_proba(latest_features)[0]

    # 确保 prob 有两个值 (class 0 和 class 1)
    if len(model.classes_) == 2:
        up_prob = float(prob[list(model.classes_).index(1)])
        down_prob = 1 - up_prob
    else:
        up_prob = 0.5
        down_prob = 0.5

    # 置信度判断
    max_prob = max(up_prob, down_prob)
    if max_prob >= 0.7:
        confidence = "较高"
    elif max_prob >= 0.6:
        confidence = "中等"
    else:
        confidence = "较低"

    direction = "看涨" if up_prob > 0.5 else "看跌"

    # 特征重要性
    feat_names = ['ret_1d', 'ret_3d', 'ret_5d', 'rsi_14', 'sma5_dev',
                  'sma20_dev', 'volatility', 'vol_change', 'bb_position', 'macd_hist']
    importances = dict(zip(feat_names, model.feature_importances_.tolist()))

    return {
        "up_prob": round(up_prob, 3),
        "down_prob": round(down_prob, 3),
        "direction": direction,
        "confidence": confidence,
        "accuracy": round(accuracy, 3),
        "forecast_days": forecast_days,
        "features": {k: round(float(feature_df[k].iloc[-1]), 4) for k in feature_df.columns},
        "importances": importances,
    }


def _build_features(df):
    """构造机器学习特征"""
    close = df['close']
    try:
        feat = pd.DataFrame(index=df.index)

        # 收益率
        feat['ret_1d'] = close.pct_change(1)
        feat['ret_3d'] = close.pct_change(3)
        feat['ret_5d'] = close.pct_change(5)

        # RSI
        feat['rsi_14'] = rsi(close, 14) / 100.0

        # 均线偏离度
        sma5 = sma(close, 5)
        sma20 = sma(close, 20)
        feat['sma5_dev'] = (close - sma5) / sma5
        feat['sma20_dev'] = (close - sma20) / sma20

        # 波动率 (10日)
        feat['volatility'] = close.pct_change().rolling(10).std()

        # 成交量变化
        if 'volume' in df.columns and df['volume'].sum() > 0:
            vol_ma = df['volume'].rolling(10).mean()
            feat['vol_change'] = (df['volume'] / vol_ma) - 1
        else:
            feat['vol_change'] = 0.0

        # 布林带位置 (0=下轨, 1=上轨)
        upper, middle, lower = bollinger_bands(close, 20, 2.0)
        feat['bb_position'] = (close - lower) / (upper - lower)

        # MACD 柱状图
        macd_line, signal_line, hist = macd(close)
        feat['macd_hist'] = hist / close  # 归一化

        return feat
    except Exception:
        return None


# ============================================================
#  2. 多指标综合评分
# ============================================================

def score_indicators(df):
    """
    综合打分系统: 将多个指标转换为 -100 到 +100 的分数。

    正分=看涨，负分=看跌，0附近=中性。

    返回:
        {
            "total_score": 35,
            "rating": "看涨",
            "details": [
                {"name": "SMA趋势", "score": 20, "reason": "..."},
                ...
            ]
        }
    """
    close = df['close']
    details = []
    total = 0

    # ---- 1. SMA 趋势 (满分 ±20) ----
    if len(df) >= 21:
        sma5_val = float(sma(close, 5).iloc[-1])
        sma20_val = float(sma(close, 20).iloc[-1])
        sma60_val = float(sma(close, min(60, len(df))).iloc[-1]) if len(df) >= 60 else sma20_val
        price = float(close.iloc[-1])

        score = 0
        reasons = []
        if price > sma5_val:
            score += 5
            reasons.append("价格在MA5上方")
        else:
            score -= 5
            reasons.append("价格在MA5下方")

        if price > sma20_val:
            score += 7
            reasons.append("价格在MA20上方")
        else:
            score -= 7
            reasons.append("价格在MA20下方")

        if sma5_val > sma20_val:
            score += 8
            reasons.append("MA5>MA20(多头排列)")
        else:
            score -= 8
            reasons.append("MA5<MA20(空头排列)")

        details.append({"name": "SMA趋势", "score": score, "max": 20, "reason": "; ".join(reasons)})
        total += score

    # ---- 2. RSI (满分 ±20) ----
    if len(df) >= 15:
        rsi_val = float(rsi(close, 14).iloc[-1])
        if rsi_val < 30:
            score = 20
            reason = f"RSI={rsi_val:.1f} 超卖区间(强烈看涨)"
        elif rsi_val < 40:
            score = 10
            reason = f"RSI={rsi_val:.1f} 偏低(看涨)"
        elif rsi_val > 70:
            score = -20
            reason = f"RSI={rsi_val:.1f} 超买区间(强烈看跌)"
        elif rsi_val > 60:
            score = -10
            reason = f"RSI={rsi_val:.1f} 偏高(看跌)"
        else:
            score = 0
            reason = f"RSI={rsi_val:.1f} 中性区间"

        details.append({"name": "RSI", "score": score, "max": 20, "reason": reason})
        total += score

    # ---- 3. 布林带位置 (满分 ±20) ----
    if len(df) >= 21:
        upper, middle, lower = bollinger_bands(close, 20, 2.0)
        c = float(close.iloc[-1])
        u, l, m = float(upper.iloc[-1]), float(lower.iloc[-1]), float(middle.iloc[-1])
        band_width = u - l
        if band_width > 0:
            position = (c - l) / band_width  # 0~1
        else:
            position = 0.5

        if position <= 0.1:
            score = 20
            reason = f"价格触及下轨(强力支撑,看涨)"
        elif position <= 0.3:
            score = 10
            reason = f"价格靠近下轨(看涨)"
        elif position >= 0.9:
            score = -20
            reason = f"价格触及上轨(强力压制,看跌)"
        elif position >= 0.7:
            score = -10
            reason = f"价格靠近上轨(看跌)"
        else:
            score = 0
            reason = f"价格在布林带中间(中性)"

        details.append({"name": "布林带", "score": score, "max": 20, "reason": reason})
        total += score

    # ---- 4. MACD (满分 ±20) ----
    if len(df) >= 35:
        macd_line, signal_line, hist = macd(close)
        h_now = float(hist.iloc[-1])
        h_prev = float(hist.iloc[-2])
        m_now = float(macd_line.iloc[-1])

        score = 0
        reasons = []
        if m_now > 0:
            score += 5
            reasons.append("MACD在零轴上方")
        else:
            score -= 5
            reasons.append("MACD在零轴下方")

        if h_now > 0:
            score += 5
            reasons.append("柱状图为正")
        else:
            score -= 5
            reasons.append("柱状图为负")

        if h_now > h_prev:
            score += 10
            reasons.append("动能增强")
        else:
            score -= 10
            reasons.append("动能减弱")

        details.append({"name": "MACD", "score": score, "max": 20, "reason": "; ".join(reasons)})
        total += score

    # ---- 5. 成交量趋势 (满分 ±20) ----
    if 'volume' in df.columns and len(df) >= 10 and df['volume'].sum() > 0:
        vol_now = float(df['volume'].iloc[-1])
        vol_ma5 = float(df['volume'].rolling(5).mean().iloc[-1])
        vol_ma10 = float(df['volume'].rolling(10).mean().iloc[-1])
        price_change = float(close.iloc[-1] - close.iloc[-2])

        score = 0
        reasons = []
        if vol_now > vol_ma5 * 1.5:
            if price_change > 0:
                score = 15
                reasons.append("放量上涨(看涨)")
            else:
                score = -15
                reasons.append("放量下跌(看跌)")
        elif vol_now > vol_ma5:
            if price_change > 0:
                score = 5
                reasons.append("温和放量上涨")
            else:
                score = -5
                reasons.append("温和放量下跌")
        else:
            score = 0
            reasons.append("成交量萎缩(观望)")

        details.append({"name": "成交量", "score": score, "max": 20, "reason": "; ".join(reasons)})
        total += score
    else:
        details.append({"name": "成交量", "score": 0, "max": 20, "reason": "无成交量数据"})

    # ---- 综合评级 ----
    if total >= 40:
        rating = "强烈看涨"
    elif total >= 20:
        rating = "看涨"
    elif total >= 5:
        rating = "偏多"
    elif total >= -5:
        rating = "中性"
    elif total >= -20:
        rating = "偏空"
    elif total >= -40:
        rating = "看跌"
    else:
        rating = "强烈看跌"

    return {
        "total_score": total,
        "max_score": 100,
        "rating": rating,
        "details": details,
    }


# ============================================================
#  3. 支撑位/阻力位
# ============================================================

def support_resistance(df, levels_count=3):
    """
    计算支撑位和阻力位。

    方法:
        - 枢轴点 (Pivot Point) 经典公式
        - 历史高低点聚类

    返回:
        {
            "current_price": 1880.50,
            "pivot": 1875.00,
            "supports": [1860.00, 1845.00, 1830.00],
            "resistances": [1890.00, 1905.00, 1920.00],
            "nearest_support": 1860.00,
            "nearest_resistance": 1890.00,
            "position": "接近阻力位",
        }
    """
    high = df['high'].values.astype(float)
    low = df['low'].values.astype(float)
    close_arr = df['close'].values.astype(float)

    current = float(close_arr[-1])
    prev_high = float(high[-2])
    prev_low = float(low[-2])
    prev_close = float(close_arr[-2])

    # ---- 经典枢轴点 ----
    pivot = (prev_high + prev_low + prev_close) / 3

    # 三个支撑位
    s1 = 2 * pivot - prev_high
    s2 = pivot - (prev_high - prev_low)
    s3 = prev_low - 2 * (prev_high - pivot)

    # 三个阻力位
    r1 = 2 * pivot - prev_low
    r2 = pivot + (prev_high - prev_low)
    r3 = prev_high + 2 * (pivot - prev_low)

    # ---- 历史关键价位 (近30天高低点) ----
    lookback = min(30, len(df))
    recent_high = float(high[-lookback:].max())
    recent_low = float(low[-lookback:].min())

    # 合并并排序
    all_supports = sorted(set([round(s, 2) for s in [s1, s2, s3, recent_low]]), reverse=True)
    all_resistances = sorted(set([round(r, 2) for r in [r1, r2, r3, recent_high]]))

    # 只保留在当前价格下方的支撑、上方的阻力
    supports = [s for s in all_supports if s < current][:levels_count]
    resistances = [r for r in all_resistances if r > current][:levels_count]

    # 如果不够，用计算值补充
    if not supports:
        supports = [round(s1, 2)]
    if not resistances:
        resistances = [round(r1, 2)]

    nearest_support = supports[0] if supports else s1
    nearest_resistance = resistances[0] if resistances else r1

    # 判断当前位置
    total_range = nearest_resistance - nearest_support
    if total_range > 0:
        pos_ratio = (current - nearest_support) / total_range
        if pos_ratio >= 0.8:
            position = "接近阻力位"
        elif pos_ratio <= 0.2:
            position = "接近支撑位"
        else:
            position = "区间中部"
    else:
        position = "无法判断"

    return {
        "current_price": round(current, 2),
        "pivot": round(pivot, 2),
        "supports": [round(s, 2) for s in supports],
        "resistances": [round(r, 2) for r in resistances],
        "nearest_support": round(nearest_support, 2),
        "nearest_resistance": round(nearest_resistance, 2),
        "position": position,
        "recent_high": round(recent_high, 2),
        "recent_low": round(recent_low, 2),
    }


# ============================================================
#  综合预测
# ============================================================

def full_prediction(df, symbol="", forecast_days=3):
    """
    运行所有三种预测，返回综合结果。
    """
    result = {
        "symbol": symbol,
        "current_price": round(float(df['close'].iloc[-1]), 2),
    }

    # 1. 综合评分（最快，始终可用）
    result["scoring"] = score_indicators(df)

    # 2. 支撑阻力位
    result["levels"] = support_resistance(df)

    # 3. 机器学习预测
    result["ml"] = ml_predict(df, forecast_days)

    # 综合建议
    score = result["scoring"]["total_score"]
    ml_dir = result["ml"].get("direction", "")
    ml_prob = result["ml"].get("up_prob", 0.5)

    if score >= 20 and ml_dir == "看涨" and ml_prob >= 0.6:
        result["summary"] = "多数指标看涨，建议关注买入机会"
    elif score <= -20 and ml_dir == "看跌" and ml_prob <= 0.4:
        result["summary"] = "多数指标看跌，建议谨慎或考虑减仓"
    elif score >= 20 or (ml_dir == "看涨" and ml_prob >= 0.6):
        result["summary"] = "部分指标偏多，可适当关注"
    elif score <= -20 or (ml_dir == "看跌" and ml_prob <= 0.4):
        result["summary"] = "部分指标偏空，建议观望"
    else:
        result["summary"] = "信号不明确，建议观望等待"

    result["disclaimer"] = "以上预测仅供学习参考，不构成投资建议"

    return result
