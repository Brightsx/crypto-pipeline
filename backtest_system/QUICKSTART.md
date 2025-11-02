# 快速开始指南

本指南帮助您快速上手多币种合约回测系统。

## 第一步：准备数据

### 1. 目录结构

确保您的数据按以下结构组织：

```
data_futures/
├── BTCUSDT/
│   ├── aggTrades/
│   │   ├── BTCUSDT-aggTrades-2024-01-01.parquet
│   │   ├── BTCUSDT-aggTrades-2024-01-02.parquet
│   │   └── ...
│   └── fundingRate/
│       ├── BTCUSDT-fundingRate-2024-01.parquet
│       └── ...
├── ETHUSDT/
│   ├── aggTrades/
│   │   └── ...
│   └── fundingRate/
│       └── ...
└── signals/
    ├── timestamps.npy
    └── signals.npy
```

### 2. 数据格式说明

**重要提示**：为了让系统能够获取第一个时间点的价格，需要准备回测开始时间**前一天**的数据。例如，如果回测从 2024-01-01 00:00:00 开始，需要准备 2023-12-31 的aggtrade数据。

#### AggTrade数据（Parquet格式）
必需列：
- `agg_trade_id`: 聚合交易ID
- `price`: 成交价格
- `quantity`: 成交数量
- `first_trade_id`: 首个交易ID
- `last_trade_id`: 最后交易ID
- `transact_time`: 成交时间（毫秒时间戳）
- `is_buyer_maker`: 是否为买方挂单

#### 信号数据（NPY格式）

**timestamps.npy**:
```python
# 一维数组，毫秒时间戳
import numpy as np
timestamps = np.array([1704067200000, 1704067800000, ...])
np.save('timestamps.npy', timestamps)
```

**signals.npy**:
```python
# 字典格式，键为交易对，值为信号数组
signals = {
    'BTCUSDT': np.array([0.5, 0.3, -0.2, ...]),
    'ETHUSDT': np.array([0.1, -0.4, 0.6, ...])
}
np.save('signals.npy', signals)
```

#### 资金费率数据（Parquet格式）
必需列：
- `calc_time`: 结算时间（毫秒时间戳）
- `funding_interval_hours`: 资金费率周期（小时）
- `last_funding_rate`: 资金费率（如0.0001表示0.01%）

## 第二步：配置系统

编辑 `config/config.yaml`:

```yaml
backtest:
  start_time: "2024-01-01 00:00:00"  # 改为你的回测开始时间
  end_time: "2024-01-07 23:59:59"    # 改为你的回测结束时间
  frequency: "15min"                  # 选择回测频率
  initial_usdt: 100000.0              # 设置初始资金
  symbols:                            # 添加你的交易对
    - BTCUSDT
    - ETHUSDT

data_loader:
  aggtrade:
    path_template: "../data_futures/{symbol}/aggTrades/{symbol}-aggTrades-{YYYY}-{MM}-{DD}.parquet"
  signal:
    timestamp_path: "../data_futures/signals/timestamps.npy"
    signal_path: "../data_futures/signals/signals.npy"
```

## 第三步：运行回测

```bash
python main.py
```

## 第四步：查看结果

回测完成后，在 `results/` 目录下会生成：

1. **trade_log.csv**: 交易明细
2. **position_log.csv**: 仓位状态

### 分析结果

```python
import pandas as pd
import matplotlib.pyplot as plt

# 读取仓位数据
positions = pd.read_csv('results/position_log.csv')

# 绘制保证金曲线
plt.figure(figsize=(12, 6))
plt.plot(positions['time'], positions['usdt_balance'])
plt.title('保证金变化')
plt.xlabel('时间')
plt.ylabel('USDT')
plt.grid(True)
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('balance_curve.png')

# 查看收益统计
print(f"初始保证金: {positions.iloc[0]['usdt_balance']:.2f}")
print(f"最终保证金: {positions.iloc[-1]['usdt_balance']:.2f}")
print(f"收益率: {(positions.iloc[-1]['usdt_balance'] / positions.iloc[0]['usdt_balance'] - 1) * 100:.2f}%")
```

## 常见问题

### Q1: 如何调整交易频率？

在配置文件中修改 `frequency`:
- `"30s"`: 30秒
- `"1min"`: 1分钟
- `"5min"`: 5分钟
- `"15min"`: 15分钟
- `"1h"`: 1小时

### Q2: 如何修改手续费和滑点？

在配置文件的 `executor.params` 中修改：
```yaml
executor:
  params:
    fee_rate: 0.0004      # Maker费率通常更低，如0.0002
    slippage_rate: 0.0001 # 根据市场流动性调整
```

### Q3: 如何限制单个币种的最大仓位？

在优化器配置中设置：
```yaml
optimizer:
  params:
    max_position_value: 50000.0  # 单币种最大持仓价值（USDT）
```

### Q4: 数据加载太慢怎么办？

系统已实现缓存机制。如果仍然慢：
1. 减少回测时间范围
2. 减少交易对数量
3. 增大回测频率（如从1min改为15min）

### Q5: 如何添加新的交易对？

1. 准备该交易对的数据文件
2. 在配置文件的 `symbols` 列表中添加
3. 确保信号文件中包含该交易对的信号

### Q6: 爆仓了怎么办？

系统会自动检测爆仓（保证金≤0）并停止交易。避免爆仓：
1. 降低杠杆倍数
2. 减小单个仓位大小
3. 优化交易策略
4. 增加初始保证金

### Q7: 为什么第一个时间点无法获取价格？

这是因为缺少回测开始时间**前一天**的数据。系统需要历史数据来获取第一个时间点的"当前价格"。

**解决方法**：
- 如果回测从 2024-01-01 00:00:00 开始，确保有 2023-12-31 的aggtrade数据
- 使用 `generate_test_data.py` 会自动生成前一天的数据

## 下一步

### 自定义优化器

查看 `demo.py` 了解如何创建自定义优化器：

```bash
python demo.py
```

### 高级配置

1. **日志级别**: 在配置中设置 `logging.level` 为 `DEBUG` 查看详细信息
2. **输出目录**: 修改 `metrics.output_dir` 自定义结果保存位置
3. **执行参数**: 调整 `executor.params` 中的延迟和窗口大小

### 性能优化

1. **减少日志输出**: 设置日志级别为 `WARNING` 或 `ERROR`
2. **批量加载**: 系统默认按天加载数据，可通过修改代码按周加载
3. **并行处理**: 对于多个独立回测，可以使用多进程

## 技术支持

如遇到问题：
1. 检查日志输出中的错误信息
2. 验证数据文件格式是否正确
3. 确认时间范围内有完整数据
4. 查看 README.md 了解更多细节

## 最佳实践

1. **先用小时间段测试**: 确保系统运行正常后再做长期回测
2. **保存配置文件**: 为不同策略保存不同的配置文件
3. **定期保存结果**: 长时间回测建议定期保存中间结果
4. **验证数据质量**: 回测前检查数据的完整性和准确性
5. **合理设置参数**: 根据实盘情况调整手续费、滑点等参数

祝您回测顺利！