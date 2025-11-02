"""
测试数据生成脚本

生成模拟的aggtrade、signal和funding rate数据用于测试回测系统
注意：这只是用于测试的模拟数据，不代表真实市场行为
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path


def generate_aggtrade_data(symbol: str, date, base_price: float, output_dir: str):
    """
    生成模拟的aggtrade数据
    
    Args:
        symbol: 交易对，如BTCUSDT
        date: 日期对象
        base_price: 基础价格
        output_dir: 输出目录
    """
    # 生成一天的数据（每秒1-5条交易）
    num_records = np.random.randint(86400, 86400 * 5)
    
    # 时间戳（毫秒）
    start_ts = int(datetime(date.year, date.month, date.day, tzinfo=timezone.utc).timestamp() * 1000)
    end_ts = start_ts + 86400 * 1000
    transact_times = np.sort(np.random.randint(start_ts, end_ts, num_records))
    
    # 价格（随机游走）
    returns = np.random.normal(0, 0.0001, num_records)
    prices = base_price * np.exp(np.cumsum(returns))
    
    # 成交量
    quantities = np.random.exponential(0.1, num_records)
    
    # 构造DataFrame
    df = pd.DataFrame({
        'agg_trade_id': range(1, num_records + 1),
        'price': prices,
        'quantity': quantities,
        'first_trade_id': range(1, num_records + 1),
        'last_trade_id': range(1, num_records + 1),
        'transact_time': transact_times,
        'is_buyer_maker': np.random.choice([True, False], num_records)
    })
    
    # 保存
    output_path = Path(output_dir) / symbol / 'aggTrades'
    output_path.mkdir(parents=True, exist_ok=True)
    
    filename = f"{symbol}-aggTrades-{date.year}-{date.month:02d}-{date.day:02d}.parquet"
    df.to_parquet(output_path / filename, index=False)
    
    print(f"生成 {filename}: {len(df)} 条记录, 价格范围 [{prices.min():.2f}, {prices.max():.2f}]")
    
    return prices[-1]  # 返回最后价格，用于下一天


def generate_funding_rate_data(symbol: str, year: int, month: int, output_dir: str):
    """
    生成模拟的资金费率数据
    
    Args:
        symbol: 交易对
        year: 年份
        month: 月份
        output_dir: 输出目录
    """
    # 每8小时一次资金费率
    start_date = datetime(year, month, 1, tzinfo=timezone.utc)
    
    if month == 12:
        end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    
    # 生成时间点（每8小时）
    calc_times = []
    current = start_date
    while current < end_date:
        if current.hour in [0, 8, 16]:  # 0:00, 8:00, 16:00 UTC
            calc_times.append(int(current.timestamp() * 1000))
        current += timedelta(hours=8)
    
    # 生成资金费率（通常在-0.05%到0.05%之间）
    funding_rates = np.random.normal(0.0001, 0.0002, len(calc_times))
    funding_rates = np.clip(funding_rates, -0.0005, 0.0005)
    
    # 构造DataFrame
    df = pd.DataFrame({
        'calc_time': calc_times,
        'funding_interval_hours': [8] * len(calc_times),
        'last_funding_rate': funding_rates
    })
    
    # 保存
    output_path = Path(output_dir) / symbol / 'fundingRate'
    output_path.mkdir(parents=True, exist_ok=True)
    
    filename = f"{symbol}-fundingRate-{year}-{month:02d}.parquet"
    df.to_parquet(output_path / filename, index=False)
    
    print(f"生成 {filename}: {len(df)} 条记录, 费率范围 [{funding_rates.min():.6f}, {funding_rates.max():.6f}]")


def generate_signal_data(symbols: list, start_date, end_date, frequency_minutes: int, output_dir: str):
    """
    生成模拟的信号数据
    
    Args:
        symbols: 交易对列表
        start_date: 开始日期
        end_date: 结束日期
        frequency_minutes: 信号频率（分钟）
        output_dir: 输出目录
    """
    # 生成时间戳
    timestamps = []
    current = start_date
    while current <= end_date:
        timestamps.append(int(current.timestamp() * 1000))
        current += timedelta(minutes=frequency_minutes)
    
    timestamps = np.array(timestamps)
    
    # 为每个交易对生成信号
    signals = {}
    for symbol in symbols:
        # 生成相关的随机游走信号
        num_points = len(timestamps)
        signal = np.random.normal(0, 0.3, num_points)
        
        # 添加一些趋势和均值回归
        trend = np.linspace(-0.2, 0.2, num_points)
        signal = signal + trend
        
        # 归一化到[-1, 1]
        signal = np.tanh(signal)
        
        signals[symbol] = signal
        
        print(f"生成 {symbol} 信号: {num_points} 个时间点, 范围 [{signal.min():.4f}, {signal.max():.4f}]")
    
    # 保存
    output_path = Path(output_dir) / 'signals'
    output_path.mkdir(parents=True, exist_ok=True)
    
    np.save(output_path / 'timestamps.npy', timestamps)
    np.save(output_path / 'signals.npy', signals)
    
    print(f"信号数据已保存到 {output_path}")


def main():
    """主函数"""
    print("=" * 60)
    print("生成测试数据")
    print("=" * 60)
    
    # 配置
    output_dir = "../data_futures"
    symbols = ['BTCUSDT', 'ETHUSDT']
    base_prices = {'BTCUSDT': 45000.0, 'ETHUSDT': 2500.0}
    
    # 回测时间范围
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2024, 1, 7, 23, 59, 59, tzinfo=timezone.utc)
    
    # 为了获取第一个时间点的价格，需要生成前一天的数据
    data_start_date = start_date - timedelta(days=1)
    
    print(f"\n配置:")
    print(f"  输出目录: {output_dir}")
    print(f"  交易对: {symbols}")
    print(f"  回测时间范围: {start_date} 至 {end_date}")
    print(f"  数据时间范围: {data_start_date} 至 {end_date} (包含前一天)")
    print()
    
    # 1. 生成aggtrade数据
    print("\n" + "-" * 60)
    print("1. 生成AggTrade数据（包含回测开始前一天）")
    print("-" * 60)
    
    current_prices = base_prices.copy()
    current_date = data_start_date.date()  # 从前一天开始
    end = end_date.date()
    
    while current_date <= end:
        for symbol in symbols:
            last_price = generate_aggtrade_data(
                symbol, current_date, current_prices[symbol], output_dir
            )
            current_prices[symbol] = last_price
        
        current_date += timedelta(days=1)
    
    # 2. 生成资金费率数据
    print("\n" + "-" * 60)
    print("2. 生成资金费率数据")
    print("-" * 60)
    
    for symbol in symbols:
        generate_funding_rate_data(symbol, 2024, 1, output_dir)
    
    # 3. 生成信号数据
    print("\n" + "-" * 60)
    print("3. 生成信号数据")
    print("-" * 60)
    
    generate_signal_data(symbols, start_date, end_date, 15, output_dir)
    
    print("\n" + "=" * 60)
    print("测试数据生成完成!")
    print("=" * 60)
    print(f"\n数据已保存到: {output_dir}")
    print("\n目录结构:")
    print("data_futures/")
    for symbol in symbols:
        print(f"├── {symbol}/")
        print(f"│   ├── aggTrades/")
        print(f"│   └── fundingRate/")
    print("└── signals/")
    print("    ├── timestamps.npy")
    print("    └── signals.npy")
    
    print("\n现在可以运行回测系统:")
    print("  python main.py")


if __name__ == "__main__":
    main()