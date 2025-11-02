# 因子评测工具 (Factor Evaluation Tool)

一个功能完整的量化因子评测系统，支持多合约、多周期的因子分析和回测。

## 功能特性

### 🎯 核心评测指标

1. **IC分析** (Information Coefficient)
   - Pearson IC 和 Spearman IC
   - IC均值、标准差、信息比率(IR)
   - IC时间序列分析
   - IC正值比例
   - IC移动平均

2. **分组回测**
   - 多分位数组合分析（默认5组）
   - 多空组合收益和夏普比率
   - 单调性检验
   - 各组胜率统计
   - 收益波动分析

3. **因子衰减**
   - 不同持有期的IC曲线
   - 最优持有期识别
   - 因子半衰期计算
   - 衰减率分析

4. **统计特性**
   - 分布特征（偏度、峰度）
   - 自相关性分析
   - 因子稳定性
   - 换手率分析
   - 极值占比

### 📊 输出内容

- **CSV摘要**: 所有因子的关键指标汇总
- **HTML报告**: 每个合约的详细分析报告
- **可视化图表**: IC时间序列、分组收益、衰减曲线等
- **排名文件**: 按IC IR排序的因子表现
- **IC时间序列**: 完整的IC历史数据

## 快速开始

### 1. 安装

```bash
# 克隆或创建项目目录
mkdir factor_evaluation
cd factor_evaluation

# 创建子目录
mkdir -p utils evaluators reports
touch utils/__init__.py evaluators/__init__.py reports/__init__.py

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置

编辑 `config.yaml`:

```yaml
# 要分析的合约
symbols:
  - BTCUSDT
  - ETHUSDT

# 数据路径
paths:
  factors_dir: "factor_results"
  returns_dir: "../returns_calculator/output"
  output_dir: "evaluation_results"
```

### 3. 运行

```bash
# 完整评测
python main.py

# 快速查看（包含交互式查询）
python quick_start.py
```

## 配置详解

### 合约配置
```yaml
symbols:
  - BTCUSDT
  - ETHUSDT
  - BNBUSDT  # 添加更多合约
```

### 评测参数
```yaml
evaluation:
  quantile_groups: 5          # 分组数量
  significance_level: 0.05    # 显著性水平
  ic_ma_windows: [20, 60]     # IC移动平均窗口
```

### 数据处理
```yaml
data_processing:
  min_valid_ratio: 0.5        # 最小有效数据比例
  winsorize: true             # 是否缩尾
  winsorize_limits: [0.01, 0.99]
  normalize_factors: true     # 是否标准化
  normalize_method: "zscore"  # zscore 或 minmax
```

## 评测指标解读

### IC指标优劣判断

| IC IR | 评价 | 说明 |
|-------|------|------|
| > 2.0 | 优秀 | 非常稳定且显著的预测能力 |
| 1.0-2.0 | 良好 | 较好的预测能力，可以使用 |
| 0.5-1.0 | 一般 | 有一定预测能力，需谨慎 |
| < 0.5 | 较差 | 预测能力不稳定 |

### 多空收益
- 正值表示高因子值对应高收益（正向因子）
- 负值表示低因子值对应高收益（反向因子）
- 绝对值越大越好

### 单调性
- 接近1：完美单调递增
- 接近0：随机分布
- 值越高，分组效果越好

## 使用示例

### 场景1：找出最优因子

```python
from main import FactorEvaluationPipeline
import pandas as pd

# 运行评测
pipeline = FactorEvaluationPipeline()
results = pipeline.run_evaluation()

# 读取摘要
summary = pd.read_csv('evaluation_results/factor_evaluation_summary.csv')

# 找出IC IR > 2 的因子
top_factors = summary[summary['ic_ir'] > 2.0].sort_values('ic_ir', ascending=False)
print(top_factors[['symbol', 'factor', 'return_period', 'ic_ir', 'ic_mean']])
```

### 场景2：分析特定因子

```python
# 查看某个因子在不同周期的表现
factor_name = 'intrabar_skew_3s'
factor_data = summary[summary['factor'] == factor_name]

# 绘制IC随持有期的变化
import matplotlib.pyplot as plt
plt.plot(factor_data['return_period'], factor_data['ic_mean'])
plt.title(f'{factor_name} IC vs Holding Period')
plt.show()
```

### 场景3：合约对比

```python
# 对比同一因子在不同合约的表现
btc_data = summary[(summary['symbol'] == 'BTCUSDT') & 
                   (summary['factor'] == factor_name)]
eth_data = summary[(summary['symbol'] == 'ETHUSDT') & 
                   (summary['factor'] == factor_name)]

print("BTC IC IR:", btc_data['ic_ir'].mean())
print("ETH IC IR:", eth_data['ic_ir'].mean())
```

## 输出文件说明

```
evaluation_results/
├── factor_evaluation_summary.csv          # 【核心】所有因子的汇总指标
├── BTCUSDT_ret_delay_9s_period_1m_ranking.csv  # 各周期的因子排名
├── BTCUSDT_detailed_report.html           # HTML详细报告
├── plots/                                 # 可视化图表
│   ├── BTCUSDT_intrabar_skew_3s.png
│   └── ...
└── ic_timeseries/                         # IC历史数据
    └── ...
```

### 摘要CSV字段说明

| 字段 | 说明 |
|------|------|
| symbol | 合约名称 |
| factor | 因子名称 |
| return_period | 收益率周期 |
| ic_mean | IC均值 |
| ic_std | IC标准差 |
| ic_ir | IC信息比率（核心指标） |
| ic_positive_ratio | IC>0的占比 |
| long_short_return | 多空组合收益 |
| long_short_sharpe | 多空夏普比率 |
| monotonicity | 单调性 |

## 常见问题

### Q1: 数据加载失败？
检查 `config.yaml` 中的路径配置是否正确，确保文件存在。

### Q2: 因子数量为0？
可能是数据有效率不足，调低 `min_valid_ratio` 参数。

### Q3: 内存不足？
- 减少合约数量
- 分批处理
- 关闭部分输出（如图表生成）

### Q4: IC值都很小？
- 检查因子和收益率的对齐是否正确
- 确认延迟设置是否合理
- 考虑因子可能确实预测能力较弱

### Q5: 如何筛选因子？
建议的筛选标准：
1. IC IR > 1.0
2. IC正值比例 > 0.55
3. 单调性 > 0.6
4. 多空收益显著（t检验p<0.05）

## 扩展开发

### 添加新的评估指标

在 `evaluators/` 下创建新的评估器：

```python
# evaluators/my_evaluator.py
class MyEvaluator:
    def __init__(self, config):
        self.config = config
    
    def evaluate(self, factors_df, returns_df):
        # 你的评估逻辑
        return results
```

然后在 `main.py` 中注册：

```python
from evaluators.my_evaluator import MyEvaluator

# 在 __init__ 中
self.my_evaluator = MyEvaluator(self.config)

# 在 run_evaluation 中
my_results = self.my_evaluator.evaluate(factors_df, returns_df)
```

## 技术支持

- 提Issue：描述问题和错误信息
- 提供样例数据格式
- 说明运行环境（Python版本等）

## 更新日志

### v1.0.0 (2024-01-01)
- 初始版本发布
- 支持IC、分组回测、衰减分析
- 多合约配置
- HTML报告和可视化

## 许可证

MIT License