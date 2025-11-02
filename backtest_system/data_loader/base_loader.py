"""数据加载器基类"""
from abc import ABC, abstractmethod
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BaseLoader(ABC):
    """数据加载器基类"""
    
    def __init__(self, config: dict):
        """
        初始化加载器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.time_unit = config.get('time_unit', 'ms')
        logger.info(f"初始化{self.__class__.__name__}, 时间单位: {self.time_unit}")
    
    @abstractmethod
    def load(self, *args, **kwargs):
        """
        加载数据的抽象方法
        
        Returns:
            加载的数据
        """
        pass
    
    def get_time_unit(self) -> str:
        """获取时间单位"""
        return self.time_unit


class LargeFileLoader(BaseLoader):
    """大文件加载器基类，用于按需加载数据"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.cache = {}  # 缓存已加载的数据
    
    @abstractmethod
    def load_period(self, start: datetime, end: datetime, **kwargs):
        """
        加载指定时间段的数据
        
        Args:
            start: 开始时间
            end: 结束时间
            **kwargs: 其他参数
        
        Returns:
            时间段内的数据
        """
        pass
    
    def clear_cache(self):
        """清空缓存"""
        logger.info(f"{self.__class__.__name__}: 清空缓存")
        self.cache.clear()


class SmallFileLoader(BaseLoader):
    """小文件加载器基类，用于一次性加载全部数据"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.data = None  # 存储加载的全部数据
    
    @abstractmethod
    def load_all(self, **kwargs):
        """
        一次性加载全部数据
        
        Args:
            **kwargs: 其他参数
        
        Returns:
            全部数据
        """
        pass