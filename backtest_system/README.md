# Backtest System
多币种永续合约回测系统（含资金费率、滑点、成交量限制、VWAP 执行、信号驱动、优化器、实时日志输出）

## 📌 项目简介
本项目是一个**高性能多币种永续合约回测系统**，支持：

- 多交易对回测
- 按任意频率（秒/min/小时/天）执行周期循环
- AggTrade（逐笔成交）数据生成 VWAP、成交量限制
- 资金费率（Funding Rate）加载 + 独立结算模块
- 支持信号驱动 / 可插拔式优化器
- 实时写入交易日志 & 状态日志
- 自动爆仓检查
- 易扩展的模块化架构

适用于量化团队和个人进行交易策略研究。

## 📁 项目结构
```
backtest_system/
│── main.py
│── requirements.txt
│
├── config/
│   └── config.yaml
│
├── utils/
│   ├── time_utils.py
│   └── __init__.py
│
├── data_loader/
│   ├── base_loader.py
│   ├── aggtrade_loader.py
│   ├── funding_rate_loader.py
│   ├── signal_loader.py
│   └── __init__.py
│
├── funding/
│   ├── settlement.py
│   └── __init__.py
│
├── executor/
│   ├── executor.py
│   └── __init__.py
│
├── optimizer/
│   ├── base_optimizer.py
│   ├── simple_optimizer.py
│   └── __init__.py
│
└── metrics/
    ├── recorder.py
    └── __init__.py
```

## 🛠 安装与运行
### 安装依赖
```
pip install -r requirements.txt
```

### 运行回测
```
python main.py -c config/config.yaml
```

## 📊 输出结果

### ✔ 1. trade_log.csv（实时写入）
包含每笔交易相关信息。

### ✔ 2. state_log.csv（实时写入）
每周期状态：余额、仓位、价格、PnL 等。

### ✔ 3. summary 输出
初始保证金、最终保证金、总收益率。

## 💡 功能亮点
- VWAP 成交、滑点、成交量限制
- 独立资金费率结算模块
- 插拔式优化器
- 实时日志输出
- 可扩展的模块化设计

## 📮 联系 & 支持
如需扩展策略、执行模型、风险管理或可视化模块，可继续联系我。
