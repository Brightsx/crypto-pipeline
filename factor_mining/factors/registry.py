"""因子注册器模块"""
import logging
from typing import Dict, Callable, List, Any
from functools import wraps


logger = logging.getLogger(__name__)


class FactorRegistry:
    """因子注册器"""
    
    def __init__(self):
        self._factors: Dict[str, Dict[str, Any]] = {}
    
    def register(self, name: str, kline_window: str, description: str = ""):
        """
        因子注册装饰器
        
        Args:
            name: 因子名称
            kline_window: 使用的K线窗口 (如 "1m", "5m")
            description: 因子描述
        """
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            
            # 注册因子信息
            self._factors[name] = {
                'func': wrapper,
                'kline_window': kline_window,
                'description': description,
                'original_func': func
            }
            
            logger.info(f"Registered factor: {name} (window: {kline_window})")
            return wrapper
        
        return decorator
    
    def get_factor(self, name: str) -> Dict[str, Any]:
        """获取因子信息"""
        if name not in self._factors:
            raise ValueError(f"Factor '{name}' not registered")
        return self._factors[name]
    
    def list_factors(self) -> List[str]:
        """列出所有已注册的因子"""
        return list(self._factors.keys())
    
    def get_factors_by_window(self, window: str) -> Dict[str, Dict[str, Any]]:
        """根据K线窗口获取因子"""
        return {
            name: info for name, info in self._factors.items() 
            if info['kline_window'] == window
        }
    
    def clear(self):
        """清空注册的因子"""
        self._factors.clear()
        logger.info("Factor registry cleared")


# 全局因子注册器实例
factor_registry = FactorRegistry()


def factor(name: str, kline_window: str, description: str = ""):
    """
    因子注册装饰器的便捷函数
    
    使用示例:
    @factor("ma_5", "1m", "5周期移动平均")
    def moving_average_5(df):
        return df['close'].rolling(5).mean()
    """
    return factor_registry.register(name, kline_window, description)