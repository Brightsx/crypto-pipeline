# 项目目录结构
binance-returns-calculator/
├── main.py                 # 主程序入口
├── config.yaml            # 配置文件
├── requirements.txt       # 依赖包
├── src/
│   ├── __init__.py
│   ├── config_manager.py   # 配置管理器
│   ├── time_utils.py       # 时间工具类
│   ├── data_loader.py      # 数据加载器
│   └── returns_calculator.py # 收益率计算器
├── output/                 # 输出目录
└── logs/                   # 日志目录

# 运行方式
1. 安装依赖：
   pip install -r requirements.txt

2. 修改配置文件 config.yaml：
   - 设置数据路径
   - 配置时间范围
   - 设置交易对列表
   - 调整计算参数

3. 运行程序：
   python main.py

# 配置文件说明
config.yaml 中的主要配置项：

- data.base_path: K线数据基础路径
- data.kline_interval: 用于计算的K线窗口（如1m、3s等）
- data.price_column: 价格列名（如vwap、close等）

- time.start_time/end_time: 计算时间范围
- time.interval: 计算间隔（如1m表示每分钟一个时间点）

- returns.delays: 延迟列表（秒为单位）
- returns.periods: 收益率周期列表（如1m、1h、1d）

- performance.batch_days: 每批处理天数
- performance.buffer_days: 缓冲天数

- symbols: 要计算的交易对列表

# 输出格式
生成的parquet文件包含：
- index: UTC时间戳，格式为DatetimeIndex
- columns: ret_delay_{延迟}s_period_{周期} 格式
- 收益率单位为1（即0.01表示1%收益）

# 性能优化特性
1. 分批处理：避免一次性加载所有数据
2. 智能缓存：减少重复文件读取
3. 内存管理：及时清理不需要的数据
4. 异常处理：跳过有问题的数据文件
5. 详细日志：监控计算进度