# 用户开发因子指南

## 快速开始

### 1. 最简单的因子

```python
from factors.registry import factor

@factor("my_sma_10", "1m", "10周期简单移动平均")
def simple_moving_average(df):
    return df['close'].rolling(10).mean()
```

### 2. 运行程序

```bash
python main.py
```

结果将保存在 `factor_results/` 目录下。

## 详细开发指南

### 因子函数模板

```python
@factor("因子名称", "K线窗口", "因子描述")
def your_factor_name(df: pd.DataFrame) -> pd.Series:
    """
    因子计算函数
    
    Args:
        df: K线数据，包含 open, high, low, close, volume 等列
    
    Returns:
        pd.Series: 与输入长度相同的因子值序列
    """
    # 你的计算逻辑
    result = df['close'].rolling(window=20).mean()
    return result
```

### 常见因子模式

#### 1. 简单滚动统计
```python
@factor("volatility_20", "1m", "20周期波动率")
def volatility(df):
    returns = df['close'].pct_change()
    return returns.rolling(20, min_periods=1).std()
```

#### 2. 多列计算
```python
@factor("price_range", "1m", "价格范围")
def price_range(df):
    return (df['high'] - df['low']) / df['close']
```

#### 3. 复杂逻辑
```python
@factor("rsi_14", "1m", "14周期RSI")
def rsi(df):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(14, min_periods=1).mean()
    avg_loss = loss.rolling(14, min_periods=1).mean()
    
    rs = avg_gain / (avg_loss + 1e-8)
    return 100 - (100 / (1 + rs))
```

#### 4. 使用不同K线窗口
```python
@factor("trend_5m", "5m", "5分钟趋势强度")
def trend_5m(df):
    # 基于5分钟K线的计算
    ma_fast = df['close'].rolling(5).mean()
    ma_slow = df['close'].rolling(20).mean()
    return (ma_fast - ma_slow) / ma_slow
```

### 可用的数据列

基础OHLCV：
- `open`, `high`, `low`, `close`, `volume`, `amount`

时间相关：
- `start_time`, `end_time` (已转为datetime格式)
- `trade_duration_ms`

交易相关：
- `trade_count`, `buy_volume`, `sell_volume`
- `buy_amount`, `sell_amount`
- `vwap` (成交量加权平均价格)

高级指标：
- `price_volatility`, `order_flow_imbalance`
- `large_trade_ratio`, `price_momentum`
- 等等...（见配置文件中的完整列表）

### 注意事项

#### ✅ 正确做法

```python
# 使用min_periods处理边界
df['close'].rolling(20, min_periods=1).mean()

# 避免除零错误
ratio = numerator / (denominator + 1e-8)

# 正确的时间序列操作
df['close'].shift(1)  # 获取前一期数据
```

#### ❌ 错误做法

```python
# 使用未来数据（未来函数）
df['close'].shift(-1)  # 错误：使用了未来数据

# 返回错误类型
return df[['close', 'volume']]  # 错误：应返回Series

# 长度不匹配
return df['close'].rolling(20).mean().dropna()  # 错误：长度改变
```

### 测试你的因子

创建简单测试：

```python
import pandas as pd
import numpy as np

# 创建测试数据
test_data = pd.DataFrame({
    'close': np.random.randn(100).cumsum() + 100,
    'volume': np.random.randint(100, 1000, 100),
    'open': np.random.randn(100) + 100,
    'high': np.random.randn(100) + 101,
    'low': np.random.randn(100) + 99,
})

# 测试你的因子
result = your_factor_name(test_data)
print(f"Result type: {type(result)}")
print(f"Result length: {len(result)}")
print(f"Sample values: {result.tail()}")
```

### 因子分类建议

#### 按计算复杂度
- **简单因子**：单列简单变换
- **滚动因子**：基于滚动窗口的统计
- **复合因子**：多列或多步骤计算

#### 按时间窗口
- **高频因子**：基于3s, 1m数据
- **中频因子**：基于5m, 15m数据  
- **低频因子**：基于1h或更长时间

#### 按金融含义
- **价格因子**：基于价格序列
- **成交量因子**：基于成交量
- **波动率因子**：衡量价格波动
- **动量因子**：衡量趋势强度
- **订单流因子**：基于买卖盘数据

### 性能优化建议

1. **向量化计算**：使用pandas/numpy的向量化操作
2. **合理的窗口大小**：避免过大的滚动窗口
3. **内存效率**：避免创建不必要的中间变量
4. **缓存结果**：对于复杂计算，可以缓存中间结果

### 调试技巧

1. **单步测试**：先在小数据集上测试
2. **数据检查**：验证输入数据的质量
3. **边界测试**：检查滚动窗口边界的处理
4. **日志输出**：在复杂因子中添加日志

这样你就可以开始开发自己的因子了！记住保持简单，一次只关注一个指标，然后逐步构建更复杂的因子。