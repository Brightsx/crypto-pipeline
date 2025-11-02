# src/__init__.py
"""
币安合约收益率计算器

高性能的币安合约数据收益率计算工具，支持：
- 多时间周期收益率计算
- 可配置延迟和周期
- 分批处理大量数据
- 智能缓存机制
- 详细日志记录
"""

__version__ = "1.0.0"
__author__ = "Binance Returns Calculator"

from .config_manager import ConfigManager
from .time_utils import TimeUtils  
from .data_loader import KlineDataLoader
from .returns_calculator import ReturnsCalculator

__all__ = [
    'ConfigManager',
    'TimeUtils', 
    'KlineDataLoader',
    'ReturnsCalculator'
]