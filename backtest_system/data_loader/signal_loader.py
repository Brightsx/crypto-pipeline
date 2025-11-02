"""信号数据加载器"""
import numpy as np
import logging
from .base_loader import SmallFileLoader
from utils.time_utils import find_nearest_timestamp

logger = logging.getLogger(__name__)


class SignalLoader(SmallFileLoader):
    """信号数据加载器，一次性加载全部数据"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.timestamp_path = config.get('timestamp_path')
        self.signal_path = config.get('signal_path')
        
        if not self.timestamp_path or not self.signal_path:
            raise ValueError("SignalLoader需要配置timestamp_path和signal_path")
        
        self.timestamps = None
        self.signals = None
    
    def load_all(self) -> tuple:
        """
        加载全部信号数据
        
        Returns:
            (timestamps, signals) 时间戳数组和信号字典
        """
        if self.timestamps is not None and self.signals is not None:
            logger.info("信号数据已加载，使用缓存")
            return self.timestamps, self.signals
        
        logger.info(f"加载信号时间戳: {self.timestamp_path}")
        self.timestamps = np.load(self.timestamp_path)
        
        logger.info(f"加载信号数据: {self.signal_path}")
        self.signals = np.load(self.signal_path, allow_pickle=True).item()
        
        logger.info(f"信号数据加载完成: {len(self.timestamps)} 个时间点, {len(self.signals)} 个交易对")
        
        # 验证数据
        for symbol, values in self.signals.items():
            if len(values) != len(self.timestamps):
                logger.warning(f"{symbol} 信号长度 {len(values)} 与时间戳长度 {len(self.timestamps)} 不匹配")
        
        return self.timestamps, self.signals
    
    def get_signal_at_time(self, target_timestamp: int, symbol: str) -> float:
        """
        获取指定时间点的信号值（取最近的过去时间点）
        
        Args:
            target_timestamp: 目标时间戳
            symbol: 交易对
        
        Returns:
            信号值，如果没有返回None
        """
        if self.timestamps is None or self.signals is None:
            self.load_all()
        
        if symbol not in self.signals:
            logger.warning(f"信号数据中不存在交易对: {symbol}")
            return None
        
        # 找到最近的过去时间戳
        nearest_ts = find_nearest_timestamp(target_timestamp, self.timestamps.tolist(), allow_future=False)
        
        if nearest_ts is None:
            logger.debug(f"未找到 {symbol} 在时间戳 {target_timestamp} 之前的信号")
            return None
        
        # 找到对应的索引
        idx = np.searchsorted(self.timestamps, nearest_ts)
        
        signal_value = float(self.signals[symbol][idx])
        logger.debug(f"获取信号 {symbol} at {target_timestamp} (使用 {nearest_ts}): {signal_value}")
        
        return signal_value
    
    def get_signals_at_time(self, target_timestamp: int, symbols: list) -> dict:
        """
        获取多个交易对在指定时间点的信号值
        
        Args:
            target_timestamp: 目标时间戳
            symbols: 交易对列表
        
        Returns:
            字典，键为symbol，值为信号值
        """
        result = {}
        for symbol in symbols:
            signal = self.get_signal_at_time(target_timestamp, symbol)
            if signal is not None:
                result[symbol] = signal
        
        return result
    
    def load(self):
        """实现基类的load方法"""
        return self.load_all()