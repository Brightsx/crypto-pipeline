"""用户自定义因子模板"""
import pandas as pd
import numpy as np
from factors.registry import factor


# ==================== 用户自定义因子示例 ====================

@factor("my_custom_ma", "1m", "我的自定义移动平均线")
def my_custom_moving_average(df: pd.DataFrame) -> pd.Series:
    """
    自定义移动平均线示例
    
    用户可以在这里实现自己的因子逻辑
    函数接收完整的K线DataFrame，返回对应的因子Series
    """
    # 示例：加权移动平均，权重递减
    window = 10
    weights = np.arange(1, window + 1)
    
    def weighted_mean(series):
        if len(series) < window:
            return series.mean()  # 如果数据不足，使用简单平均
        return np.average(series, weights=weights)
    
    return df['close'].rolling(window=window, min_periods=1).apply(weighted_mean)


@factor("price_volume_correlation", "5m", "价格与成交量5周期相关性")
def price_volume_correlation(df: pd.DataFrame) -> pd.Series:
    """
    价格与成交量的滚动相关性
    """
    window = 5
    
    # 使用pandas的rolling corr方法
    return df['close'].rolling(window=window, min_periods=2).corr(df['volume'])


@factor("momentum_reversal", "1m", "动量反转因子")
def momentum_reversal_factor(df: pd.DataFrame) -> pd.Series:
    """
    动量反转因子：结合短期动量和长期反转
    """
    # 短期动量（3周期）
    short_momentum = df['close'] / df['close'].shift(3) - 1
    
    # 长期反转（20周期）
    long_momentum = df['close'] / df['close'].shift(20) - 1
    
    # 反转因子：长期动量的负值
    reversal = -long_momentum
    
    # 结合短期动量和长期反转
    factor = short_momentum + 0.5 * reversal
    
    # 标准化处理
    return (factor - factor.rolling(50, min_periods=1).mean()) / (
        factor.rolling(50, min_periods=1).std() + 1e-8
    )


# ==================== 高级因子示例 ====================

@factor("multi_timeframe_strength", "1m", "多时间框架强度因子")
def multi_timeframe_strength(df: pd.DataFrame) -> pd.Series:
    """
    多时间框架强度因子：综合不同周期的价格强度
    """
    # 不同周期的价格变化
    ret_1 = df['close'].pct_change(1, fill_method=None)  # 1周期
    ret_5 = df['close'].pct_change(5, fill_method=None)  # 5周期
    ret_10 = df['close'].pct_change(10, fill_method=None)  # 10周期
    
    # 加权综合，短期权重更高
    strength = 0.5 * ret_1 + 0.3 * ret_5 + 0.2 * ret_10
    
    # 滚动标准化
    return (strength - strength.rolling(20, min_periods=1).mean()) / (
        strength.rolling(20, min_periods=1).std() + 1e-8
    )


@factor("volume_price_trend", "1m", "量价趋势一致性")
def volume_price_trend_consistency(df: pd.DataFrame) -> pd.Series:
    """
    量价趋势一致性因子
    """
    # 价格趋势（使用移动平均斜率）
    price_ma = df['close'].rolling(10, min_periods=1).mean()
    price_trend = price_ma - price_ma.shift(5)
    
    # 成交量趋势
    volume_ma = df['volume'].rolling(10, min_periods=1).mean()
    volume_trend = volume_ma - volume_ma.shift(5)
    
    # 趋势方向一致性（同为正或同为负）
    consistency = np.sign(price_trend) * np.sign(volume_trend)
    
    # 平滑处理
    return consistency.rolling(3, min_periods=1).mean()


# ==================== 用户开发指南 ====================
"""
用户开发因子的指南：

1. 使用 @factor 装饰器注册因子：
   - name: 因子名称（必须唯一）
   - kline_window: 使用的K线窗口，如 "1m", "5m", "15m", "1h"
   - description: 因子描述

2. 函数签名：
   def your_factor_name(df: pd.DataFrame) -> pd.Series:
   
3. 输入参数：
   - df: 完整的K线数据DataFrame，包含所有列（见配置文件中的列名）
   - 数据已按时间排序，时间列为 'end_time'（毫秒时间戳转换后的datetime）
   
4. 返回值：
   - 必须返回 pd.Series，长度与输入DataFrame相同
   - 索引应与输入DataFrame的索引对应
   - 值为计算得到的因子值

5. 注意事项：
   - 避免使用未来函数（不能使用未来的数据计算当前因子）
   - 使用 .rolling() 等pandas函数进行滚动计算
   - 处理 NaN 值，可以使用 min_periods 参数
   - 对于数值稳定性，在除法中加入小的常数（如 1e-8）

6. 可用的数据列（参考）：
   - 基础OHLCV: open, high, low, close, volume, amount
   - 时间相关: start_time, end_time, trade_duration_ms
   - 交易相关: trade_count, buy_volume, sell_volume, vwap
   - 衍生指标: price_volatility, order_flow_imbalance 等

7. 示例模式：
   # 简单滚动统计
   return df['close'].rolling(window=20).mean()
   
   # 多列计算
   return (df['high'] - df['low']) / df['close']
   
   # 复杂逻辑
   def complex_calculation(series):
       # 自定义计算逻辑
       return result
   return df['close'].rolling(window=10).apply(complex_calculation)
   
8. 测试建议：
   - 在小数据集上测试因子函数
   - 检查返回值的长度和类型
   - 验证没有使用未来数据
"""