"""因子测试模块"""
import sys
import pandas as pd
import numpy as np
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from factors.registry import factor


def create_test_data(n_rows=100):
    """创建测试用的K线数据"""
    np.random.seed(42)
    
    # 生成基础价格序列（随机游走）
    base_price = 50000
    price_changes = np.random.normal(0, 0.001, n_rows)
    prices = [base_price]
    
    for change in price_changes[1:]:
        new_price = prices[-1] * (1 + change)
        prices.append(max(new_price, 1))  # 确保价格为正
    
    # 生成OHLC数据
    data = []
    for i, close in enumerate(prices):
        high = close * (1 + abs(np.random.normal(0, 0.003)))
        low = close * (1 - abs(np.random.normal(0, 0.003)))
        if i == 0:
            open_price = close
        else:
            open_price = prices[i-1]
        
        volume = max(np.random.exponential(1000), 100)
        amount = volume * close
        
        # 模拟时间戳（1分钟间隔）
        timestamp = pd.Timestamp('2025-01-01') + pd.Timedelta(minutes=i)
        
        data.append({
            'start_time': timestamp,
            'end_time': timestamp + pd.Timedelta(minutes=1),
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume,
            'amount': amount,
            'trade_count': np.random.randint(50, 200),
            'buy_volume': volume * np.random.uniform(0.4, 0.6),
            'sell_volume': volume * np.random.uniform(0.4, 0.6),
            'vwap': close * (1 + np.random.normal(0, 0.0001)),
            'order_flow_imbalance': np.random.normal(0, 0.1),
            'large_trade_ratio': np.random.uniform(0.1, 0.9)
        })
    
    return pd.DataFrame(data)


# ==================== 测试因子定义 ====================

@factor("test_sma", "1m", "测试用简单移动平均")
def test_simple_moving_average(df: pd.DataFrame) -> pd.Series:
    """测试用的简单移动平均"""
    return df['close'].rolling(window=5, min_periods=1).mean()


@factor("test_volatility", "1m", "测试用波动率")
def test_volatility(df: pd.DataFrame) -> pd.Series:
    """测试用的价格波动率"""
    returns = df['close'].pct_change()
    return returns.rolling(window=10, min_periods=1).std()


@factor("test_volume_ratio", "1m", "测试用成交量比率")
def test_volume_ratio(df: pd.DataFrame) -> pd.Series:
    """测试用的成交量比率"""
    volume_ma = df['volume'].rolling(window=20, min_periods=1).mean()
    return df['volume'] / (volume_ma + 1e-8)


def test_individual_factors():
    """测试单个因子计算"""
    print("Testing individual factors...")
    
    # 创建测试数据
    test_df = create_test_data(50)
    print(f"Created test data with {len(test_df)} rows")
    
    # 测试各个因子
    factors_to_test = ['test_sma', 'test_volatility', 'test_volume_ratio']
    
    for factor_name in factors_to_test:
        try:
            from factors.registry import factor_registry
            factor_info = factor_registry.get_factor(factor_name)
            factor_func = factor_info['func']
            
            result = factor_func(test_df)
            
            print(f"\n{factor_name}:")
            print(f"  Result type: {type(result)}")
            print(f"  Result length: {len(result)}")
            print(f"  Non-null values: {result.notna().sum()}")
            print(f"  Sample values: {result.iloc[-5:].tolist()}")
            
            # 验证结果
            assert isinstance(result, pd.Series), f"{factor_name} should return pd.Series"
            assert len(result) == len(test_df), f"{factor_name} length mismatch"
            
        except Exception as e:
            print(f"Error testing {factor_name}: {e}")


def test_factor_engine():
    """测试因子引擎（简化版）"""
    print("\nTesting Factor Engine...")
    
    try:
        from core.factor_engine import FactorEngine
        from core.utils import generate_time_points, align_data_to_timepoints
        from datetime import datetime
        
        # 创建测试数据
        test_df = create_test_data(100)
        
        # 生成目标时间点
        start_time = datetime(2025, 1, 1, 0, 0, 0)
        end_time = datetime(2025, 1, 1, 1, 30, 0)  # 90分钟
        target_times = generate_time_points(start_time, end_time, "1m")
        
        print(f"Generated {len(target_times)} target timepoints")
        
        # 测试数据对齐
        aligned_data = align_data_to_timepoints(test_df, target_times, 'end_time')
        print(f"Aligned data shape: {aligned_data.shape}")
        
        # 测试因子计算
        from factors.registry import factor_registry
        test_factor_info = factor_registry.get_factor('test_sma')
        factor_func = test_factor_info['func']
        
        factor_result = factor_func(test_df)
        print(f"Factor result shape: {factor_result.shape}")
        
    except Exception as e:
        print(f"Error testing factor engine: {e}")


def test_data_alignment():
    """测试数据对齐功能"""
    print("\nTesting Data Alignment...")
    
    try:
        from core.utils import generate_time_points, align_data_to_timepoints
        from datetime import datetime
        
        # 创建稀疏测试数据（模拟低频K线）
        sparse_data = []
        base_time = datetime(2025, 1, 1, 0, 0, 0)
        
        # 每5分钟一个数据点
        for i in range(0, 60, 5):
            timestamp = base_time + pd.Timedelta(minutes=i)
            sparse_data.append({
                'end_time': timestamp,
                'close': 50000 + i * 10,
                'volume': 1000 + i * 5
            })
        
        sparse_df = pd.DataFrame(sparse_data)
        print(f"Sparse data: {len(sparse_df)} points")
        
        # 生成密集目标时间点（每1分钟）
        target_times = generate_time_points(base_time, base_time + pd.Timedelta(minutes=59), "1m")
        print(f"Target times: {len(target_times)} points")
        
        # 对齐数据
        aligned = align_data_to_timepoints(sparse_df, target_times, 'end_time')
        print(f"Aligned data shape: {aligned.shape}")
        print(f"Non-null close values: {aligned['close'].notna().sum()}")
        
        # 验证前向填充效果
        print("\nSample aligned data:")
        print(aligned[['close', 'volume']].head(10))
        
    except Exception as e:
        print(f"Error testing data alignment: {e}")


def run_all_tests():
    """运行所有测试"""
    print("="*50)
    print("Factor Mining System Tests")
    print("="*50)
    
    test_individual_factors()
    test_data_alignment()
    test_factor_engine()
    
    print("\n" + "="*50)
    print("Tests Completed")
    print("="*50)


if __name__ == "__main__":
    run_all_tests()