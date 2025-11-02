"""优化器基类"""
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class BaseOptimizer(ABC):
    """优化器基类"""
    
    def __init__(self, config: dict):
        """
        初始化优化器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.params = config.get('params', {})
        logger.info(f"初始化{self.__class__.__name__}, 参数: {self.params}")
    
    @abstractmethod
    def optimize(self, current_time, signals: dict, current_positions: dict, 
                 current_prices: dict, usdt_balance: float, **kwargs) -> dict:
        """
        根据信号和当前状态计算目标仓位
        
        Args:
            current_time: 当前时间(datetime对象)
            signals: 信号字典，键为symbol，值为信号值
            current_positions: 当前仓位字典，键为symbol，值为持仓数量(正数多仓，负数空仓)
            current_prices: 当前价格字典，键为symbol，值为最新价格
            usdt_balance: 当前USDT保证金余额
            **kwargs: 其他可能需要的数据
        
        Returns:
            目标仓位字典，键为symbol，值为目标持仓数量
        """
        pass
    
    def _log_optimization(self, current_time, signals: dict, current_positions: dict, 
                         target_positions: dict, current_prices: dict):
        """记录优化信息"""
        logger.info(f"[{current_time}] 优化完成:")
        for symbol in signals.keys():
            signal = signals.get(symbol, 0)
            current_pos = current_positions.get(symbol, 0)
            target_pos = target_positions.get(symbol, 0)
            price = current_prices.get(symbol, 0)
            
            logger.info(f"  {symbol}: 信号={signal:.4f}, 当前仓位={current_pos:.4f}, "
                       f"目标仓位={target_pos:.4f}, 价格={price:.2f}")