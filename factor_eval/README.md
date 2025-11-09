
# 🧮 `factor_eval_v12` — Binance Futures 因子评估系统

## 🌟 项目简介

`factor_eval_v12` 是一个高性能、结构化、可视化美观的**量化因子评估工具**，用于评估从 Binance 合约（或其他高频市场）中提取的因子与未来收益率之间的关系。  
系统支持从数据对齐、去极值、标准化，到因子相关性、回归、分位回测、稳定性分析、IC-decay 绘图的完整流程。

> ✅ 本版本完全支持多币种（如 BTCUSDT、ETHUSDT）批量评估，  
> ✅ 每个因子单独输出报告与图表，  
> ✅ 日志记录详细，绘图结果美观清晰。

---

## 🧱 目录结构

```
factor_eval_v12/
├── main.py                          # 顶层入口
├── README.md                        # 当前说明文件
├── config/
│   └── config.yaml                  # 全局配置文件
├── src/                             # 源码目录
│   ├── evaluator.py                 # 主逻辑控制模块
│   ├── config_loader.py             # 配置读取
│   ├── io_utils.py                  # 数据读入与对齐
│   ├── preprocess.py                # 去极值与标准化
│   ├── metrics.py                   # IC/RankIC/Newey-West 回归
│   ├── portfolio.py                 # 分位回测模块
│   ├── stability.py                 # 稳定性分析模块
│   ├── plots.py                     # 各类绘图（多delay、多色）
│   └── utils.py                     # 辅助函数与计时器
├── logs/                            # 日志输出目录
└── reports/                         # 运行后自动生成的报告目录
```

---

## ⚙️ 安装与运行

### 1️⃣ 依赖环境

Python ≥ 3.9  
推荐安装：
```bash
pip install pandas numpy matplotlib seaborn pyyaml scipy
```

### 2️⃣ 运行命令
```bash
python factor_eval_v12/main.py --config factor_eval_v12/config/config.yaml
```

### 3️⃣ 运行日志

所有日志同时写入控制台和文件：
```
logs/factor_eval.log
```

日志示例：
```
[2025-11-09 21:33:12,308] INFO: ==== Evaluating BTCUSDT ====
[2025-11-09 21:33:12,491] INFO: read & align BTCUSDT done in 0.19s
[2025-11-09 21:33:12,589] INFO: preprocess factors (BTCUSDT) done in 0.10s
[2025-11-09 21:33:13,912] INFO: [BTCUSDT] factor intrabar_skew_3s — plots saved to reports/per_symbol/BTCUSDT/plots/intrabar_skew_3s (pairs=5)
[2025-11-09 21:33:22,006] INFO: [BTCUSDT] evaluation completed. Reports at reports/per_symbol/BTCUSDT
```

---

## 🧩 核心功能概览

| 模块 | 功能描述 |
|------|-----------|
| **数据加载 (`io_utils`)** | 读取因子与收益率文件（parquet 格式），自动对齐时间戳（UTC），支持正则列筛选。 |
| **预处理 (`preprocess`)** | 对每个因子进行去极值（Quantile 或 MAD）与标准化（可关闭）。 |
| **IC计算 (`metrics`)** | 支持 Pearson IC、Spearman RankIC；可选择 Newey-West 回归调整。 |
| **分位回测 (`portfolio`)** | 将因子分为 n 分位（默认5），计算各分位未来收益率均值、t值、top-bottom 组合、换手率。 |
| **稳定性分析 (`stability`)** | 输出月度、小时、周度 RankIC 稳定性曲线。 |
| **IC Decay (`plots`)** | 对相同因子不同 delay / period 的 RankIC 进行多色折线图展示。 |
| **绘图与报告 (`plots`)** | 每个因子单独输出：月度/小时/周几/Decay/Quantile 图，带标题、轴标签、图例。 |
| **日志系统** | 每个阶段、每个因子绘图均记录详细日志，含时间消耗。 |

---

## 🧾 配置文件说明（`config/config.yaml`）

```yaml
symbols: [BTCUSDT, ETHUSDT]     # 要评估的交易对
utc: true

paths:                          # 数据路径模板
  factors_pattern: "../factor_mining/factor_results/{symbol}_factors.parquet"
  returns_pattern: "../returns_calculator/output/{symbol}_returns.parquet"

columns:                        # 指定需要加载的列（可用正则）
  include_factors: []           # 空列表=加载所有因子列
  include_returns: []           # 空列表=加载所有收益率列

preprocess:
  join_how: "inner"             # inner|outer|left|right
  time_filter:                  # 时间过滤区间（UTC）
    start_time: "2023-01-01 00:00:00"
    end_time: "2025-01-01 00:00:00"
  winsor:                       # 去极值参数
    enabled: true
    method: "quantile"          # quantile 或 mad
    q_low: 0.01
    q_high: 0.99
  standardize:                  # 标准化参数
    enabled: false
  min_samples: 10000            # IC 计算最小样本量

evaluation:
  ic:
    method: "both"              # pearson|spearman|both
  regression:
    newey_west:
      enabled: true
      default_lags: 10
  quantile:                     # 分位回测设置
    enabled: true
    q: 5
    compute_turnover: true

stability:
  ic_by_month: true
  ic_by_hour: true
  ic_by_wday: true
  ic_decay: true

annualization:
  freq_by_period:
    "1m": 525600
    "5m": 105120
    "15m": 35040
    "1h": 8760
    "1d": 365

output:
  save_csv: true
  plots: true

logging:
  level_console: "INFO"
  level_file: "DEBUG"
  log_file: "logs/factor_eval.log"
```

---

## 📊 输出结构与内容

执行完毕后自动生成：
```
reports/
└── per_symbol/
    ├── BTCUSDT/
    │   ├── summary_factor_metrics.csv       # 所有因子×收益率汇总表
    │   ├── stability/
    │   │   ├── ic_by_month.csv
    │   │   ├── ic_by_hour.csv
    │   │   ├── ic_by_wday.csv
    │   │   └── ic_decay.csv
    │   ├── quantiles/
    │   │   ├── <factor>__<return>.csv
    │   └── plots/
    │       ├── <factor1>/
    │       │   ├── ic_by_month__*.png
    │       │   ├── ic_by_hour__*.png
    │       │   ├── ic_by_wday__*.png
    │       │   ├── ic_decay.png
    │       │   └── quantiles__*.png
    │       └── <factor2>/
    │           └── ...
    └── ETHUSDT/
        └── ...
```

---

## 🎨 绘图风格说明

| 图类型 | 文件名示例 | 特点 |
|--------|-------------|------|
| **月度IC曲线** | `ic_by_month__ret_delay_9s_period_1m.png` | 横轴为年月，纵轴 RankIC；线型光滑带点。 |
| **小时IC柱状** | `ic_by_hour__ret_delay_9s_period_1m.png` | 横轴为小时（0–23），纵轴 RankIC。 |
| **周几IC柱状** | `ic_by_wday__ret_delay_9s_period_1m.png` | 横轴为 0–6（周一–周日），纵轴 RankIC。 |
| **IC Decay** | `ic_decay.png` | 同一因子下多 delay 折线图；颜色区分。 |
| **Quantile Bar** | `quantiles__ret_delay_9s_period_1m.png` | 因子分位收益条形图。 |

所有图片：
- 白底灰网格 (`seaborn-whitegrid`)
- 字体自适应、标题包含因子与收益率名
- 统一 DPI=150
- 图例清晰（IC-decay 多 delay）

---

## 🧠 结果解释

| 指标 | 含义 |
|------|------|
| `ic` | Pearson 相关系数，度量因子与未来收益的线性关系 |
| `rank_ic` | Spearman 秩相关系数，度量单调关系（稳健） |
| `reg_alpha` / `reg_beta` | Newey-West 回归截距/斜率 |
| `reg_t` / `reg_p` | 斜率的 t 值与显著性 |
| `ls_mean` / `ls_t` | 分位回测中 top-bottom 组合的收益及显著性 |
| `turnover` | 因子换手率估计 |
| `ic_decay` | 不同收益期与 delay 下 RankIC 变化趋势 |

---

## 🧩 扩展建议

下一步可扩展的功能：
1. **IC Heatmap**（月份 × 因子）
2. **IC 分布直方图**
3. **Top-Bottom 累计收益曲线**
4. **Markdown/HTML 汇总报告**（自动嵌入图片和统计表）
5. **GPU 加速计算**（Numba/Polars 版本）

---

## 🧾 开发者备注

- 所有时间均为 **UTC 时间戳**。
- 支持任意时间频率的 returns（1m、5m、15m、1h、1d...）。
- 若数据量较大，请优先使用 SSD 并关闭 `plots` 以加速。
- 所有模块函数均可独立调用，便于在 Jupyter Notebook 调试。
