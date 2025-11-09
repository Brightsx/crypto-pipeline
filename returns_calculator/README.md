# Binance Futures Return Calculator (UTC)

高性能、结构清晰的币安合约收益率计算框架。  
**所有时间均为 UTC**，支持任意时间分辨率（秒、分钟、小时等），通过延迟 × 周期组合计算收益率。  

---

## 📂 项目结构

```
binance_returns_refactored/
├── main.py                      # 主入口（直接运行）
├── binance_returns/             # 主包目录
│   ├── __init__.py
│   ├── config_loader.py         # 加载 YAML 配置
│   ├── data_loader.py           # 高效读取每日 parquet 数据
│   ├── return_calculator.py     # 收益率计算核心逻辑
│   ├── utils.py                 # 日志与批次工具函数
├── config/
│   └── config.yaml              # 主配置文件
├── logs/
│   └── run.log                  # 运行日志
├── output/
│   └── (保存各交易对的计算结果)
├── requirements.txt
└── README.md
```

---

## ⚙️ 功能概述

- **延迟 × 周期 组合收益率**  
  例如配置中 `delays: ["9s","15s"]` 与 `periods: ["1m","5m"]`，则生成：
  ```
  ret_delay_9s_period_1m
  ret_delay_9s_period_5m
  ret_delay_15s_period_1m
  ret_delay_15s_period_5m
  ```

- **向后找价格机制**  
  若起始或结束价格为 `NaN`，算法会沿时间轴**向后（未来）**寻找最近可用价格；  
  若两个价格最终落在同一时刻，则收益率自动为 0。

- **批处理机制**  
  数据按配置的 `batch_days` 分批读取，每批再延长 `margin_days`，确保覆盖延迟与最长周期，避免重复 I/O。

- **精确时间网格**  
  按配置的 `interval`（如 `"1m"`）生成全局时间序列，每一分钟（或更细分）都计算收益率。  
  全过程统一使用 `pandas.Timestamp(..., tz="UTC")`。

- **最小 I/O 策略**  
  只读取必要列（`start_time` 与价格列），跳过冗余字段，自动跳过缺失文件。

---

## 🧩 配置说明（`config/config.yaml`）

```yaml
symbols: ["BTCUSDT"]            # 要计算的合约/币种

data:
  base_path: "../data_futures"  # 数据目录
  kline_window: "3s"            # K线窗口类型，如 3s, 1m, 5m, 15m, 1h
  price_column: "vwap"          # 收益率使用的价格列

time_range:
  start_time: "2023-01-01 00:00:00"
  end_time:   "2025-01-01 00:00:00"
  interval:   "1m"              # 计算间隔（每分钟一个点）

returns:
  delays: ["9s", "15s"]         # 延迟
  periods: ["1m", "5m", "15m", "1h"]  # 收益率周期

batch:
  batch_days: 30                # 每批处理天数
  margin_days: 7                # 右侧冗余天数，确保覆盖延迟+最长周期

output:
  dir: "output"                 # 输出目录
  filename_pattern: "{symbol}_returns_{kline_window}_{interval}.parquet"
```

---

## 🚀 使用方法

### 1️⃣ 安装依赖
```bash
pip install -r requirements.txt
```

### 2️⃣ 运行主程序
```bash
python main.py
```

### 3️⃣ 查看日志
实时查看运行进度与警告：
```bash
tail -f logs/run.log
```

---

## 📊 输出结果格式

输出文件路径（示例）：
```
output/BTCUSDT_returns_3s_1m.parquet
```

示例：
```
                           ret_delay_9s_period_1m  ret_delay_9s_period_5m  ret_delay_15s_period_1h
timestamp
2023-01-01 00:00:00+00:00                0.000119               -0.000406                -0.000719
2023-01-01 00:01:00+00:00               -0.000185               -0.000385                -0.000838
...
2025-01-01 00:00:00+00:00                0.000616                0.001231                 0.008781
```

索引为 `DatetimeIndex`（UTC），列为所有延迟与周期组合，值为收益率（单位 1）。

---

## 💡 技术要点

| 特性 | 说明 |
|------|------|
| 时间精度 | 秒、分钟、小时均可 |
| 时区 | 全部为 UTC |
| 缺失处理 | 向后补价，不向前填充 |
| 性能优化 | 分批读取 + 向量化计算 |
| 输出格式 | Parquet（Arrow，高压缩、高速读写） |

---

## 🧠 延伸功能建议
- 支持 **多进程并行计算多个币种**
- 增加 **断点续算**（检测已完成区间）
- 输出 **统计报告（NaN 占比、收益率分布）**
- 支持 **成本调整后的净收益**

---

**Made with ❤️ for quantitative research and data-driven trading pipelines.**
