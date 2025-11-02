"""简单优化器示例"""
import logging
from .base_optimizer import BaseOptimizer

logger = logging.getLogger(__name__)


class SimpleOptimizer(BaseOptimizer):
    """
    简单线性优化器示例
    将信号值线性映射到目标仓位
    """
    
    def __init__(self, config: dict):
        super().__init__(config)
        
        # 从配置中读取参数
        self.signal_multiplier = self.params.get('signal_multiplier', 10.0)
        self.max_position_value = self.params.get('max_position_value', 50000.0)
        self.leverage = self.params.get('leverage', 3.0)
        
        logger.info(f"SimpleOptimizer配置: signal_multiplier={self.signal_multiplier}, "
                   f"max_position_value={self.max_position_value}, leverage={self.leverage}")
    
    def optimize(self, current_time, signals: dict, current_positions: dict,
                 current_prices: dict, usdt_balance: float, **kwargs) -> dict:
        """
        优化目标仓位
        
        策略逻辑:
        1. 信号值 * signal_multiplier * leverage = 目标仓位价值(USDT)
        2. 目标仓位价值 / 当前价格 = 目标仓位数量
        3. 限制单币种最大持仓价值
        
        Args:
            current_time: 当前时间
            signals: 信号字典
            current_positions: 当前仓位
            current_prices: 当前价格
            usdt_balance: USDT余额
            **kwargs: 其他参数
        
        Returns:
            目标仓位字典
        """
        target_positions = {}
        
        logger.info(f"[{current_time}] 开始优化, USDT余额: {usdt_balance:.2f}")
        
        # 如果爆仓，目标仓位全部为0
        if usdt_balance <= 0:
            logger.warning(f"[{current_time}] 保证金不足，已爆仓!")
            for symbol in signals.keys():
                target_positions[symbol] = 0.0
            return target_positions
        
        for symbol, signal in signals.items():
            price = current_prices.get(symbol)
            
            if price is None or price <= 0:
                logger.warning(f"[{current_time}] {symbol} 价格无效: {price}, 目标仓位设为0")
                target_positions[symbol] = 0.0
                continue
            
            # 计算目标仓位价值
            target_value = signal * self.signal_multiplier * self.leverage * usdt_balance
            
            # 限制最大持仓价值
            if abs(target_value) > self.max_position_value:
                target_value = self.max_position_value if target_value > 0 else -self.max_position_value
            
            # 转换为仓位数量
            target_quantity = target_value / price
            
            target_positions[symbol] = target_quantity
            
            logger.debug(f"[{current_time}] {symbol}: 信号={signal:.4f}, "
                        f"目标价值={target_value:.2f} USDT, 目标数量={target_quantity:.6f}")
        
        # 记录优化结果
        self._log_optimization(current_time, signals, current_positions, 
                             target_positions, current_prices)
        
        return target_positions