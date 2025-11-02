"""
多频率量价与微结构因子集（修正版）
适用于 BTCUSDT / ETHUSDT 等单标的K线数据
支持频率：3s, 1m, 5m, 15m, 1h
"""

import pandas as pd
import numpy as np
from .registry import factor


# ==================== 趋势类因子 ====================

@factor("momentum_10_1m", "1m", "10周期价格动量（1m）")
def momentum_10_1m(df: pd.DataFrame) -> pd.Series:
    """短期价格动量：当前价格相对10周期前的涨幅"""
    return df["close"] / df["close"].shift(10) - 1


@factor("trend_alignment_5m", "5m", "短中期趋势一致性（5m）")
def trend_alignment_5m(df: pd.DataFrame) -> pd.Series:
    """短中期EMA趋势方向一致性"""
    short = df["close"].ewm(span=5, adjust=False).mean()
    mid = df["close"].ewm(span=30, adjust=False).mean()
    return np.sign(short - mid)


@factor("price_trend_strength_15m", "15m", "15分钟趋势斜率强度（15m）")
def price_trend_strength_15m(df: pd.DataFrame) -> pd.Series:
    """线性回归斜率衡量价格趋势强度"""
    window = 10

    def slope(series):
        if len(series) < 2:
            return np.nan
        x = np.arange(len(series))
        return np.polyfit(x, series, 1)[0]

    return df["close"].rolling(window=window, min_periods=2).apply(slope)


# ==================== 波动类因子 ====================

@factor("volatility_20_1m", "1m", "20周期收益率波动率（1m）")
def volatility_20_1m(df: pd.DataFrame) -> pd.Series:
    """价格收益率标准差"""
    returns = df["close"].pct_change(fill_method=None)
    return returns.rolling(20, min_periods=5).std()


@factor("atr_14_1m", "1m", "14周期平均真实波幅ATR（1m）")
def atr_14_1m(df: pd.DataFrame) -> pd.Series:
    """平均真实波幅ATR"""
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(14, min_periods=1).mean()


@factor("intrabar_skew_3s", "3s", "K线内价格偏向度（3s）")
def intrabar_skew_3s(df: pd.DataFrame) -> pd.Series:
    """单根K线的收盘偏向：高收或低收"""
    return (df["close"] - df["open"]) / (df["high"] - df["low"] + 1e-8)


# ==================== 量价关系类因子 ====================

@factor("volume_spike_1m", "1m", "成交量突变强度（1m）")
def volume_spike_1m(df: pd.DataFrame) -> pd.Series:
    """成交量偏离其均值的标准化程度"""
    mean = df["volume"].rolling(20, min_periods=5).mean()
    std = df["volume"].rolling(20, min_periods=5).std()
    return (df["volume"] - mean) / (std + 1e-8)


@factor("vwap_deviation_1m", "1m", "价格相对VWAP偏离度（1m）")
def vwap_deviation_1m(df: pd.DataFrame) -> pd.Series:
    """收盘价与VWAP的相对偏离"""
    if "vwap" in df.columns:
        vwap = df["vwap"]
    else:
        vwap = (df["close"] * df["volume"]).rolling(20).sum() / df["volume"].rolling(20).sum()
    return (df["close"] - vwap) / (vwap + 1e-8)


@factor("volume_price_corr_15m", "15m", "量价相关性因子（15m）")
def volume_price_corr_15m(df: pd.DataFrame) -> pd.Series:
    """成交量与收益率的滚动相关性"""
    returns = df["close"].pct_change(fill_method=None)
    vol = df["volume"]
    return returns.rolling(20, min_periods=5).corr(vol)


# ==================== 微结构与订单流类因子 ====================

@factor("order_imbalance_3s", "3s", "买卖力量不平衡（3s）")
def order_imbalance_3s(df: pd.DataFrame) -> pd.Series:
    """买卖金额不平衡度"""
    if "buy_amount" in df.columns and "sell_amount" in df.columns:
        imbalance = (df["buy_amount"] - df["sell_amount"]) / (df["buy_amount"] + df["sell_amount"] + 1e-8)
        return imbalance.rolling(5, min_periods=1).mean()
    return pd.Series(index=df.index, dtype=float)


@factor("trade_intensity_1m", "1m", "成交笔数活跃度（1m）")
def trade_intensity_1m(df: pd.DataFrame) -> pd.Series:
    """成交笔数相对均值的放大倍数"""
    if "buy_count" in df.columns and "sell_count" in df.columns:
        count = df["buy_count"] + df["sell_count"]
        return count / (count.rolling(30, min_periods=5).mean() + 1e-8)
    return pd.Series(index=df.index, dtype=float)


@factor("order_flow_pressure_1m", "1m", "订单流买卖压力（1m）")
def order_flow_pressure_1m(df: pd.DataFrame) -> pd.Series:
    """买入成交次数与卖出成交次数的差异"""
    if "buy_aggtrade_count" in df.columns and "sell_aggtrade_count" in df.columns:
        diff = df["buy_aggtrade_count"] - df["sell_aggtrade_count"]
        total = df["buy_aggtrade_count"] + df["sell_aggtrade_count"] + 1e-8
        return diff / total
    return pd.Series(index=df.index, dtype=float)


# ==================== 复合因子（多维特征整合） ====================

@factor("volume_weighted_momentum_5m", "5m", "成交量加权动能（5m）")
def volume_weighted_momentum_5m(df: pd.DataFrame) -> pd.Series:
    """成交量加权后的价格动量"""
    price_change = df["close"].pct_change(fill_method=None)
    weight = df["volume"] / (df["volume"].rolling(20).mean() + 1e-8)
    return (price_change * weight).rolling(10, min_periods=3).mean()


@factor("volatility_adjusted_return_1h", "1h", "波动率调整收益（1h）")
def volatility_adjusted_return_1h(df: pd.DataFrame) -> pd.Series:
    """收益率与波动率的比值，衡量风险收益比"""
    ret = df["close"].pct_change(fill_method=None)
    vol = ret.rolling(30, min_periods=5).std()
    return ret / (vol + 1e-8)
