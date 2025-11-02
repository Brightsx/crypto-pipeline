# 挖因子程序 (Factor Mining System)

一个模块化、高性能的量化因子挖掘框架，专门用于处理多币种合约的K线数据并计算各种技术因子。

## 🚀 特性

- **模块化设计**：清晰的代码结构，易于维护和扩展
- **多频率支持**：支持不同时间窗口的K线数据（3s, 1m, 5m, 15m, 1h等）
- **批处理优化**：内存友好的批量处理，避免大数据集的内存溢出
- **因子注册系统**：简单的装饰器模式，用户只需关注因子计算逻辑
- **高性能**：并行处理和智能缓存机制
- **时间对齐**：自动处理不同频率数据的时间对齐问题
- **防未来函数**：确保因子计算不使用未来数据

## 📁 项目结构

```
factor_mining/
├── config.yaml                 # 主配置文件
├── main.py                     # 程序入口
├── requirements.txt            # 依赖包
├── logs/                       # 日志目录
├── factor_results/             # 因子结果输出
├── core/                       # 核心模块
│   ├── config.py              # 配置管理
│   ├── data_manager.py        # 数据管理
│   ├── factor_engine.py       # 因子计算引擎
│   └── utils.py               # 工具函数
├── factors/                   # 因子定义
│   ├── registry.py           # 因子注册器
│   ├── basic_factors.py      # 基础因子示例
│   └── custom_factors.py     # 用户自定义因子
└── tests/                    # 测试模块
```

## ⚙️ 安装和配置

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置文件设置

编辑 `config.yaml` 文件：

```yaml
data:
  root_path: "../data_futures"          # 数据根目录
  symbols: ["BTCUSDT", "ETHUSDT"]       # 币种列表
  kline_windows: ["3s", "1m", "5m", "15m", "1h"]  # K线窗口

factor:
  calc_frequency: "1m"                  # 因子计算频率
  batch_days: 7                         # 批处理天数
  max_lookback_days: 30                 # 最大回看天数
  start_time: "2025-01-01 00:00:00"     # 开始时间 (UTC)
  end_time: "2025-01-31 23:59:59"       # 结束时间 (UTC)
```

### 3. 数据格式要求

K线数据文件结构：
```
../data_futures/
├── BTCUSDT/
│   ├── aggTrades_kline_1m/
│   │   ├── BTCUSDT-kline-1m-2025-01-01.parquet
│   │   └── ...
│   ├── aggTrades_kline_5m/
│   └── ...
└── ETHUSDT/
    └── ...
```

数据列要求：包含 `start_time`, `end_time`, `open`, `high`, `low`, `close`, `volume` 等基础列。

## 🔧 使用方法

### 运行程序

```bash
# 运行所有币种
python main.py

# 运行单个币种（调试用）
python main.py single BTCUSDT
```

### 开发自定义因子

在 `factors/custom_factors.py` 中添加你的因子：

```python
from .registry import factor
import pandas as pd

@factor("my_factor", "1m", "我的自定义因子")
def my_custom_factor(df: pd.DataFrame) -> pd.Series:
    """
    自定义因子计算函数
    
    Args:
        df: K线数据DataFrame，包含所有列
        
    Returns:
        pd.Series: 因子值序列
    """
    # 示例：10周期移动平均
    return df['close'].rolling(window=10, min_periods=1).mean()
```

### 因子开发要点

1. **使用装饰器注册**：`@factor(name, kline_window, description)`
2. **函数签名**：接收 `pd.DataFrame`，返回 `pd.Series`
3. **避免未来函数**：只能使用当前及过去的数据
4. **处理边界**：使用 `min_periods` 参数处理滚动窗口边界
5. **数值稳定性**：在除法操作中加入小常数避免除零错误

## 📊 因子示例

### 基础因子

- **移动平均类**：SMA, EMA
- **波动率类**：标准差，ATR
- **动量类**：价格变化率，RSI
- **成交量类**：成交量比率，量价关系

### 高级因子

- **多时间框架因子**：结合不同K线窗口
- **订单流因子**：基于买卖盘数据
- **复合因子**：多指标综合

## 🏃‍♂️ 性能优化

- **批处理**：按配置的天数分批处理，控制内存使用
- **并行加载**：多线程并行读取数据文件
- **智能缓存**：避免重复加载相同文件
- **增量清理**：定期清理缓存释放内存

## 📝 输出格式

每个币种生成一个parquet文件：`{SYMBOL}_factors.parquet`

文件结构：
```
timestamp (index)  |  factor1  |  factor2  |  ...
2025-01-01 00:00   |   0.123   |   0.456   |  ...
2025-01-01 00:01   |   0.124   |   0.457   |  ...
...
```

## 🧪 测试

运行测试：
```bash
python tests/test_factors.py
```

测试包含：
- 单因子计算验证
- 数据对齐功能测试
- 因子引擎集成测试

## 📋 注意事项

1. **时间统一**：所有时间都使用UTC时间
2. **数据完整性**：确保K线数据文件的完整性和格式正确性
3. **内存管理**：大数据集处理时注意监控内存使用
4. **因子命名**：因子名称必须唯一
5. **时间对齐**：低频K线数据会前向填充，高频数据会按时间点采样

## 🤝 扩展开发

### 添加新数据源
- 在 `DataManager` 中扩展数据加载逻辑
- 支持新的文件格式或数据库连接

### 添加新因子类型
- 继承或扩展因子注册系统
- 支持多输出因子或矩阵因子

### 性能优化
- 实现更高级的缓存策略
- 添加GPU加速支持

## 📄 许可证

本项目使用 MIT 许可证。

## 🐛 问题反馈

如遇到问题，请检查：
1. 配置文件格式是否正确
2. 数据文件路径和格式是否符合要求
3. 因子函数是否正确返回 pandas Series
4. 时间范围设置是否合理

查看日志文件 `logs/factor_mining.log` 获取详细错误信息。