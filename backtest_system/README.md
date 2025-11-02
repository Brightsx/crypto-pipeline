# 多币种合约回测交易系统

一个功能完整、模块化设计的Python回测交易系统，支持多币种合约交易回测。

## 项目结构

```
backtest_system/
├── config/
│   └── config.yaml              # 配置文件
├── data_loader/                 # 数据加载模块
│   ├── __init__.py
│   ├── base_loader.py          # 基类
│   ├── aggtrade_loader.py      # 成交数据加载器
│   ├── signal_loader.py        # 信号数据加载器
│   └── funding_rate_loader.py  # 资金费率加载器
├── optimizer/                   # 优化模块
│   ├── __init__.py
│   ├── base_optimizer.py       # 优化器基类
│   └── simple_optimizer.py     # 简单优化器示例
├── executor/                    # 执行模块
│   ├── __init__.py
│   └── executor.py             # 交易执行器
├── metrics/                     # 统计模块
│   ├── __init__.py
│   └── recorder.py             # 记录器
├── utils/                       # 工具模块
│   ├── __init__.py
│   └── time_utils.py           # 时间工具
├── main.py                      # 主程序
└── README.md                    # 说明文档
```

## 功能特性

### 1. 数据加载模块
- **AggTrade数据**：按天动态加载Binance成交数据，支持缓存
- **信号数据**：一次性加载归一化后的信号值
- **资金费率数据**：按月加载资金费率数据
- **扩展性**：支持自定义数据加载器

### 2. 优化模块
- 将信号值映射为目标仓位
- 考虑当前持仓、价格、保证金余额
- 支持自定义优化策略
- 内置简单线性优化器示例

### 3. 执行模块
- 模拟真实交易过程
- 支持执行延迟和成交窗口
- VWAP成交价格计算
- 手续费和滑点模拟
- 成交量限制（不超过市场成交量的指定比例）

### 4. 资金费率模块
- 自动识别资金费率结算时间
- 精确计算多空仓位的资金费率损益
- 实时更新保证金余额

### 5. 统计模块
- 记录每个周期的交易明细
- 记录每个周期结束时的状态
- 分离计算trade PnL、hold PnL、fee PnL、funding PnL
- 输出详细的CSV报告

## 安装依赖

```bash
pip install pandas numpy pyarrow pyyaml
```

## 配置说明

配置文件 `config/config.yaml` 包含以下部分：

### 回测参数
```yaml
backtest:
  start_time: "2024-01-01 00:00:00"  # 开始时间(UTC)
  end_time: "2024-01-07 23:59:59"    # 结束时间(UTC)
  frequency: "15min"                  # 回测频率
  initial_usdt: 100000.0              # 初始保证金
  symbols:                            # 交易对列表
    - BTCUSDT
    - ETHUSDT
```

### 数据路径
```yaml
data_loader:
  aggtrade:
    path_template: "../data_futures/{symbol}/aggTrades/{symbol}-aggTrades-{YYYY}-{MM}-{DD}.parquet"
  signal:
    timestamp_path: "../data_futures/signals/timestamps.npy"
    signal_path: "../data_futures/signals/signals.npy"
  funding_rate:
    path_template: "../data_futures/{symbol}/fundingRate/{symbol}-fundingRate-{YYYY}-{MM}.parquet"
```

### 优化器参数
```yaml
optimizer:
  class_name: "simple_optimizer.SimpleOptimizer"
  params:
    signal_multiplier: 10.0      # 信号到仓位的线性系数
    max_position_value: 50000.0  # 单币种最大持仓价值
    leverage: 3.0                # 杠杆倍数
```

### 执行器参数
```yaml
executor:
  params:
    execution_delay: 10          # 执行延迟(秒)
    execution_window: 20         # 成交窗口(秒)
    fee_rate: 0.0004            # 手续费率
    slippage_rate: 0.0001       # 滑点率
    max_volume_pct: 0.10        # 最大成交量占比
```

## 使用方法

### 基本使用

```bash
python main.py
```

### 自定义优化器

创建自己的优化器类：

```python
from optimizer.base_optimizer import BaseOptimizer

class MyOptimizer(BaseOptimizer):
    def optimize(self, current_time, signals, current_positions,
                 current_prices, usdt_balance, **kwargs):
        target_positions = {}
        
        # 你的优化逻辑
        for symbol, signal in signals.items():
            # 计算目标仓位
            target_positions[symbol] = ...
        
        return target_positions
```

然后在配置文件中指定：

```yaml
optimizer:
  class_name: "my_optimizer.MyOptimizer"
  params:
    # 你的参数
```

### 自定义数据加载器

继承 `BaseLoader` 并实现 `load` 方法：

```python
from data_loader.base_loader import SmallFileLoader

class MyDataLoader(SmallFileLoader):
    def load_all(self):
        # 加载你的数据
        return data
```

## 输出结果

回测完成后会生成两个CSV文件：

### 1. trade_log.csv
记录每个周期的交易明细：
- start_time: 周期开始时间
- end_time: 周期结束时间
- symbol: 交易对
- target_quantity: 目标交易数量
- actual_quantity: 实际成交数量
- vwap: VWAP价格
- execution_price: 执行价格（含滑点）
- trade_value: 交易金额
- fee: 手续费
- slippage: 滑点

### 2. position_log.csv
记录每个周期结束时的状态：
- time: 时间
- usdt_balance: USDT保证金余额
- trade_pnl: 本周期交易PnL
- hold_pnl: 本周期持有PnL
- fee_pnl: 本周期手续费PnL
- funding_pnl: 本周期资金费率PnL
- total_pnl: 本周期总PnL
- {symbol}_position: 各币种仓位
- {symbol}_price: 各币种价格

## PnL计算说明

系统将PnL分为四个部分：

1. **Trade PnL**：新开仓位从执行价到周期结束价的盈亏
2. **Hold PnL**：原有仓位从周期开始价到结束价的盈亏
3. **Fee PnL**：手续费损失（负数）
4. **Funding PnL**：资金费率结算损益

公式：
```
下一周期保证金 = 当前保证金 + total_pnl
total_pnl = trade_pnl + hold_pnl + fee_pnl + funding_pnl
```

## 注意事项

1. **数据准备**：需要准备回测开始时间**前一天**的数据，用于获取第一个时间点的价格。例如回测从2024-01-01开始，需要有2023-12-31的aggtrade数据
2. **时间单位**：所有时间均为UTC时区
3. **未来函数**：优化模块中只能使用当前或过去的数据
4. **爆仓处理**：保证金小于等于0时，所有仓位清零
5. **资金费率**：自动在整点前后1秒内结算
6. **成交限制**：单笔交易不超过市场成交量的指定比例

## 扩展性

系统设计了良好的扩展接口：

- 继承 `BaseLoader` 添加新的数据源
- 继承 `BaseOptimizer` 实现自定义策略
- 所有模块通过配置文件动态加载
- 支持多种时间频率和交易对

## 日志

系统提供详细的日志输出，包括：
- 数据加载过程
- 优化决策
- 交易执行
- PnL计算
- 资金费率结算

日志级别可在配置文件中调整（DEBUG/INFO/WARNING/ERROR）。

## 示例

完整的运行示例请参考 `main.py` 和 `config/config.yaml`。

## 许可证

MIT License