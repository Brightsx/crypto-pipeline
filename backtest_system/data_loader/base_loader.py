
"""数据加载器基类"""
from abc import ABC, abstractmethod
from datetime import datetime
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class BaseLoader(ABC):
    """数据加载器基类。"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.time_unit = config.get("time_unit", "ms")
        logger.info("初始化%s, 时间单位: %s", self.__class__.__name__, self.time_unit)

    @abstractmethod
    def load(self, *args, **kwargs):
        raise NotImplementedError

    def get_time_unit(self) -> str:
        return self.time_unit


class LargeFileLoader(BaseLoader):
    """大文件加载器基类，按需加载并带简单缓存。"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.cache: Dict[str, Any] = {}

    @abstractmethod
    def load_period(self, start: datetime, end: datetime, **kwargs):
        raise NotImplementedError

    def clear_cache(self):
        logger.info("%s: 清空缓存", self.__class__.__name__)
        self.cache.clear()


class SmallFileLoader(BaseLoader):
    """小文件加载器基类，一次性加载全部数据。"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.data = None

    @abstractmethod
    def load_all(self, **kwargs):
        raise NotImplementedError
