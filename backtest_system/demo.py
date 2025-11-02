"""
演示脚本：展示如何创建和使用自定义优化器

本脚本展示：
1. 如何创建自定义优化器
2. 如何在配置中使用自定义优化器
3. 优化器的基本逻辑示例
"""

import numpy as np
from optimizer.base_optimizer import BaseOptimizer
import logging

logger = logging.getLogger(__name__)


class RankBasedOptimizer(BaseOptimizer):
    """
    基于排名的优化器示例
    
    策略逻辑：
    1. 对所有币种的信号进行排名
    2. 只做多信号最强的N个币种，做空信号最弱的M个币种
    3. 其他币种仓位为0
    """
    
    def __init__(self, config: dict):
        super().__init__(config)
        
        self.top_n_long = self.params.get('top_n_long', 2)  # 做多的币种数量
        self.top_n_short = self.params.get('top_n_short', 1)  # 做空的币种数量
        self.position_size = self.params.get('position_size', 0.3)  # 每个仓位占保证金的比例
        self.leverage = self.params.get('leverage', 3.0)  # 杠杆
        
        logger.info(f"RankBasedOptimizer: top_n_long={self.top_n_long}, "
                   f"top_n_short={self.top_n_short}, "
                   f"position_size={self.position_size}, leverage={self.leverage}")
    
    def optimize(self, current_time, signals: dict, current_positions: dict,
                 current_prices: dict, usdt_balance: float, **kwargs) -> dict:
        """
        基于排名的优化
        
        Args:
            current_time: 当前时间
            signals: 信号字典
            current_positions: 当前仓位
            current_prices: 当前价格
            usdt_balance: USDT余额
            
        Returns:
            目标仓位字典
        """
        target_positions = {}
        
        logger.info(f"[{current_time}] RankBasedOptimizer开始优化, USDT={usdt_balance:.2f}")
        
        # 爆仓检查
        if usdt_balance <= 0:
            logger.warning(f"[{current_time}] 保证金不足，已爆仓!")
            return {symbol: 0.0 for symbol in signals.keys()}
        
        # 对信号进行排序
        valid_signals = {}
        for symbol, signal in signals.items():
            if symbol in current_prices and current_prices[symbol] > 0:
                valid_signals[symbol] = signal
        
        if not valid_signals:
            logger.warning(f"[{current_time}] 无有效信号")
            return {symbol: 0.0 for symbol in signals.keys()}
        
        # 按信号值排序
        sorted_symbols = sorted(valid_signals.items(), key=lambda x: x[1], reverse=True)
        
        # 选择做多和做空的币种
        long_symbols = [s[0] for s in sorted_symbols[:self.top_n_long]]
        short_symbols = [s[0] for s in sorted_symbols[-self.top_n_short:]]
        
        logger.info(f"[{current_time}] 做多: {long_symbols}, 做空: {short_symbols}")
        
        # 计算每个仓位的大小
        position_value = usdt_balance * self.position_size * self.leverage
        
        # 分配仓位
        for symbol in signals.keys():
            price = current_prices.get(symbol, 0)
            
            if price <= 0:
                target_positions[symbol] = 0.0
                continue
            
            if symbol in long_symbols:
                # 做多
                target_quantity = position_value / price
                target_positions[symbol] = target_quantity
                logger.debug(f"[{current_time}] {symbol} 做多: {target_quantity:.6f}")
                
            elif symbol in short_symbols:
                # 做空
                target_quantity = -position_value / price
                target_positions[symbol] = target_quantity
                logger.debug(f"[{current_time}] {symbol} 做空: {target_quantity:.6f}")
                
            else:
                # 不持仓
                target_positions[symbol] = 0.0
        
        # 记录优化结果
        self._log_optimization(current_time, signals, current_positions, 
                             target_positions, current_prices)
        
        return target_positions


class MeanReversionOptimizer(BaseOptimizer):
    """
    均值回归优化器示例
    
    策略逻辑：
    当信号偏离均值较大时，进行反向操作（假设会回归）
    """
    
    def __init__(self, config: dict):
        super().__init__(config)
        
        self.threshold = self.params.get('threshold', 0.5)  # 信号阈值
        self.position_size = self.params.get('position_size', 0.3)
        self.leverage = self.params.get('leverage', 2.0)
        
        logger.info(f"MeanReversionOptimizer: threshold={self.threshold}, "
                   f"position_size={self.position_size}, leverage={self.leverage}")
    
    def optimize(self, current_time, signals: dict, current_positions: dict,
                 current_prices: dict, usdt_balance: float, **kwargs) -> dict:
        """
        均值回归优化
        
        Args:
            current_time: 当前时间
            signals: 信号字典
            current_positions: 当前仓位
            current_prices: 当前价格
            usdt_balance: USDT余额
            
        Returns:
            目标仓位字典
        """
        target_positions = {}
        
        logger.info(f"[{current_time}] MeanReversionOptimizer开始优化, USDT={usdt_balance:.2f}")
        
        # 爆仓检查
        if usdt_balance <= 0:
            logger.warning(f"[{current_time}] 保证金不足，已爆仓!")
            return {symbol: 0.0 for symbol in signals.keys()}
        
        # 计算信号均值
        signal_values = list(signals.values())
        if not signal_values:
            return {symbol: 0.0 for symbol in signals.keys()}
        
        mean_signal = np.mean(signal_values)
        
        # 计算每个仓位的大小
        position_value = usdt_balance * self.position_size * self.leverage
        
        for symbol, signal in signals.items():
            price = current_prices.get(symbol, 0)
            
            if price <= 0:
                target_positions[symbol] = 0.0
                continue
            
            # 计算偏离度
            deviation = signal - mean_signal
            
            # 如果偏离超过阈值，反向操作
            if abs(deviation) > self.threshold:
                # 信号高于均值 -> 做空（预期回归）
                # 信号低于均值 -> 做多（预期回归）
                target_quantity = -np.sign(deviation) * position_value / price
                target_positions[symbol] = target_quantity
                logger.debug(f"[{current_time}] {symbol} 偏离={deviation:.4f}, 仓位={target_quantity:.6f}")
            else:
                # 偏离不大，不持仓
                target_positions[symbol] = 0.0
        
        self._log_optimization(current_time, signals, current_positions, 
                             target_positions, current_prices)
        
        return target_positions


def create_demo_config():
    """
    创建演示配置文件
    展示如何配置不同的优化器
    """
    
    config_rank_based = """
# 使用排名优化器的配置示例
backtest:
  start_time: "2024-01-01 00:00:00"
  end_time: "2024-01-07 23:59:59"
  frequency: "15min"
  initial_usdt: 100000.0
  symbols:
    - BTCUSDT
    - ETHUSDT
    - BNBUSDT

optimizer:
  class_name: "demo.RankBasedOptimizer"  # 使用自定义优化器
  params:
    top_n_long: 2        # 做多前2名
    top_n_short: 1       # 做空最后1名
    position_size: 0.3   # 每个仓位占保证金30%
    leverage: 3.0        # 3倍杠杆
"""
    
    config_mean_reversion = """
# 使用均值回归优化器的配置示例
backtest:
  start_time: "2024-01-01 00:00:00"
  end_time: "2024-01-07 23:59:59"
  frequency: "15min"
  initial_usdt: 100000.0
  symbols:
    - BTCUSDT
    - ETHUSDT

optimizer:
  class_name: "demo.MeanReversionOptimizer"  # 使用均值回归优化器
  params:
    threshold: 0.5       # 信号偏离阈值
    position_size: 0.3   # 每个仓位占保证金30%
    leverage: 2.0        # 2倍杠杆
"""
    
    print("=" * 60)
    print("排名优化器配置示例：")
    print("=" * 60)
    print(config_rank_based)
    
    print("\n" + "=" * 60)
    print("均值回归优化器配置示例：")
    print("=" * 60)
    print(config_mean_reversion)


def demo_optimizer_usage():
    """
    演示如何在代码中使用优化器
    """
    from datetime import datetime, timezone
    
    print("\n" + "=" * 60)
    print("优化器使用演示")
    print("=" * 60)
    
    # 模拟数据
    current_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    signals = {
        'BTCUSDT': 0.8,
        'ETHUSDT': 0.3,
        'BNBUSDT': -0.5
    }
    current_positions = {
        'BTCUSDT': 0.0,
        'ETHUSDT': 0.0,
        'BNBUSDT': 0.0
    }
    current_prices = {
        'BTCUSDT': 45000.0,
        'ETHUSDT': 2500.0,
        'BNBUSDT': 300.0
    }
    usdt_balance = 100000.0
    
    # 测试排名优化器
    print("\n1. 排名优化器测试：")
    print("-" * 60)
    
    rank_config = {
        'params': {
            'top_n_long': 2,
            'top_n_short': 1,
            'position_size': 0.3,
            'leverage': 3.0
        }
    }
    
    rank_optimizer = RankBasedOptimizer(rank_config)
    target_positions = rank_optimizer.optimize(
        current_time, signals, current_positions, current_prices, usdt_balance
    )
    
    print("\n信号值：")
    for symbol, signal in signals.items():
        print(f"  {symbol}: {signal:.4f}")
    
    print("\n目标仓位：")
    for symbol, position in target_positions.items():
        position_value = position * current_prices[symbol]
        print(f"  {symbol}: {position:.6f} (价值: {position_value:.2f} USDT)")
    
    # 测试均值回归优化器
    print("\n\n2. 均值回归优化器测试：")
    print("-" * 60)
    
    mr_config = {
        'params': {
            'threshold': 0.5,
            'position_size': 0.3,
            'leverage': 2.0
        }
    }
    
    mr_optimizer = MeanReversionOptimizer(mr_config)
    target_positions = mr_optimizer.optimize(
        current_time, signals, current_positions, current_prices, usdt_balance
    )
    
    print("\n信号值：")
    mean_signal = np.mean(list(signals.values()))
    print(f"  均值: {mean_signal:.4f}")
    for symbol, signal in signals.items():
        deviation = signal - mean_signal
        print(f"  {symbol}: {signal:.4f} (偏离: {deviation:+.4f})")
    
    print("\n目标仓位：")
    for symbol, position in target_positions.items():
        position_value = position * current_prices[symbol]
        direction = "多头" if position > 0 else "空头" if position < 0 else "空仓"
        print(f"  {symbol}: {position:.6f} ({direction}, 价值: {abs(position_value):.2f} USDT)")


if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("多币种合约回测系统 - 自定义优化器演示")
    print("=" * 60)
    
    # 展示配置示例
    create_demo_config()
    
    # 演示优化器使用
    demo_optimizer_usage()
    
    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)
    print("\n提示：")
    print("1. 将上述优化器代码保存到独立的Python文件")
    print("2. 在config.yaml中配置optimizer.class_name")
    print("3. 运行 python main.py 开始回测")
    print("=" * 60)