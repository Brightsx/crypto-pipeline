"""基础因子示例"""
import pandas as pd
import numpy as np
from factors.registry import factor


# ==================== 价格类因子 ====================

@factor("sma_5", "1m", "5周期简单移动平均")
def simple_moving_average_5(df: pd.DataFrame) -> pd.Series:
    """5周期简单移动平均"""
    return df['close'].rolling(window=5, min_periods=1).mean()


@factor("sma_20", "1m", "20周期简单移动平均")
def simple_moving_average_20(df: pd.DataFrame) -> pd.Series:
    """20周期简单移动平均"""
    return df['close'].rolling(window=20, min_periods=1).mean()


@factor("ema_12", "1m", "12周期指数移动平均")
def exponential_moving_average_12(df: pd.DataFrame) -> pd.Series:
    """12周期指数移动平均"""
    return df['close'].ewm(span=12, adjust=False).mean()


@factor("price_change", "1m", "价格变化率")
def price_change(df: pd.DataFrame) -> pd.Series:
    """价格变化率 (当前价格/前一价格 - 1)"""
    return df['close'].pct_change(fill_method=None)


@factor("price_momentum_5", "1m", "5周期价格动量")
def price_momentum_5(df: pd.DataFrame) -> pd.Series:
    """5周期价格动量 (当前价格/5周期前价格 - 1)"""
    return df['close'] / df['close'].shift(5) - 1


# ==================== 波动率类因子 ====================

@factor("volatility_20", "1m", "20周期价格波动率")
def volatility_20(df: pd.DataFrame) -> pd.Series:
    """20周期价格波动率（收益率标准差）"""
    returns = df['close'].pct_change(fill_method=None)
    return returns.rolling(window=20, min_periods=1).std()


@factor("atr_14", "1m", "14周期平均真实波幅")
def average_true_range_14(df: pd.DataFrame) -> pd.Series:
    """14周期平均真实波幅"""
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift(1))
    low_close = abs(df['low'] - df['close'].shift(1))
    
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=14, min_periods=1).mean()


# ==================== 成交量类因子 ====================

@factor("volume_ma_10", "1m", "10周期成交量移动平均")
def volume_moving_average_10(df: pd.DataFrame) -> pd.Series:
    """10周期成交量移动平均"""
    return df['volume'].rolling(window=10, min_periods=1).mean()


@factor("volume_ratio", "1m", "成交量比率")
def volume_ratio(df: pd.DataFrame) -> pd.Series:
    """成交量比率（当前成交量/平均成交量）"""
    volume_ma = df['volume'].rolling(window=20, min_periods=1).mean()
    return df['volume'] / volume_ma


@factor("vwap_deviation", "1m", "价格偏离VWAP程度")
def vwap_deviation(df: pd.DataFrame) -> pd.Series:
    """价格偏离VWAP的程度"""
    if 'vwap' in df.columns:
        return (df['close'] - df['vwap']) / df['vwap']
    else:
        # 如果没有预计算的VWAP，则计算简单版本
        vwap = (df['volume'] * df['close']).rolling(20).sum() / df['volume'].rolling(20).sum()
        return (df['close'] - vwap) / vwap


# ==================== 多频率因子示例 ====================

@factor("sma_5_5m", "5m", "5分钟K线的5周期移动平均")
def simple_moving_average_5_5m(df: pd.DataFrame) -> pd.Series:
    """基于5分钟K线的5周期简单移动平均"""
    return df['close'].rolling(window=5, min_periods=1).mean()


@factor("volume_spike_5m", "5m", "5分钟成交量突增因子")
def volume_spike_5m(df: pd.DataFrame) -> pd.Series:
    """基于5分钟K线的成交量突增因子"""
    volume_ma = df['volume'].rolling(window=10, min_periods=1).mean()
    volume_std = df['volume'].rolling(window=10, min_periods=1).std()
    return (df['volume'] - volume_ma) / (volume_std + 1e-8)


@factor("price_trend_15m", "15m", "15分钟价格趋势强度")
def price_trend_15m(df: pd.DataFrame) -> pd.Series:
    """基于15分钟K线的价格趋势强度"""
    # 计算线性回归斜率作为趋势强度
    window = 10
    
    def calc_slope(series):
        if len(series) < 2:
            return np.nan
        x = np.arange(len(series))
        slope = np.polyfit(x, series, 1)[0]
        return slope
    
    return df['close'].rolling(window=window, min_periods=2).apply(calc_slope)


# ==================== 复合因子示例 ====================

@factor("rsi_14", "1m", "14周期相对强弱指数")
def relative_strength_index_14(df: pd.DataFrame) -> pd.Series:
    """14周期RSI"""
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=14, min_periods=1).mean()
    avg_loss = loss.rolling(window=14, min_periods=1).mean()
    
    rs = avg_gain / (avg_loss + 1e-8)
    rsi = 100 - (100 / (1 + rs))
    return rsi


@factor("bollinger_position", "1m", "布林带位置")
def bollinger_band_position(df: pd.DataFrame) -> pd.Series:
    """价格在布林带中的位置（0-1之间）"""
    window = 20
    sma = df['close'].rolling(window=window, min_periods=1).mean()
    std = df['close'].rolling(window=window, min_periods=1).std()
    
    upper_band = sma + 2 * std
    lower_band = sma - 2 * std
    
    # 计算价格在布林带中的相对位置
    position = (df['close'] - lower_band) / (upper_band - lower_band + 1e-8)
    return position.clip(0, 1)


# ==================== 订单流因子示例 ====================

@factor("order_flow_imbalance_smooth", "1m", "平滑订单流不平衡")
def order_flow_imbalance_smooth(df: pd.DataFrame) -> pd.Series:
    """平滑的订单流不平衡"""
    if 'order_flow_imbalance' in df.columns:
        return df['order_flow_imbalance'].rolling(window=5, min_periods=1).mean()
    else:
        # 使用买卖量差异作为替代
        if 'buy_volume' in df.columns and 'sell_volume' in df.columns:
            imbalance = (df['buy_volume'] - df['sell_volume']) / (df['buy_volume'] + df['sell_volume'] + 1e-8)
            return imbalance.rolling(window=5, min_periods=1).mean()
    return pd.Series(index=df.index, dtype=float)


@factor("large_trade_ratio_ma", "1m", "大单交易比例移动平均")
def large_trade_ratio_ma(df: pd.DataFrame) -> pd.Series:
    """大单交易比例的移动平均"""
    if 'large_trade_ratio' in df.columns:
        return df['large_trade_ratio'].rolling(window=10, min_periods=1).mean()
    return pd.Series(index=df.index, dtype=float)