
"""信号数据加载器"""
import logging
from typing import Dict, List, Tuple

import numpy as np

from .base_loader import SmallFileLoader
from utils.time_utils import find_nearest_timestamp

logger = logging.getLogger(__name__)


class SignalLoader(SmallFileLoader):
    """信号数据加载器：一次性加载所有 npy 信号文件。"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.timestamp_path = config.get("timestamp_path")
        self.signal_path = config.get("signal_path")

        if not self.timestamp_path or not self.signal_path:
            raise ValueError("SignalLoader需要配置 timestamp_path 和 signal_path")

        self.timestamps = None
        self.signals: Dict[str, np.ndarray] = {}

    def load_all(self) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        if self.timestamps is not None and self.signals:
            logger.info("信号数据已加载，使用缓存")
            return self.timestamps, self.signals

        logger.info("加载信号时间戳: %s", self.timestamp_path)
        self.timestamps = np.load(self.timestamp_path)

        logger.info("加载信号数据: %s", self.signal_path)
        self.signals = np.load(self.signal_path, allow_pickle=True).item()

        logger.info("信号数据加载完成: %d 个时间点, %d 个交易对", len(self.timestamps), len(self.signals))

        for symbol, values in self.signals.items():
            if len(values) != len(self.timestamps):
                logger.warning("%s 信号长度 %d 与时间戳长度 %d 不匹配", symbol, len(values), len(self.timestamps))

        return self.timestamps, self.signals

    def get_signal_at_time(self, target_timestamp: int, symbol: str):
        if self.timestamps is None or not self.signals:
            self.load_all()

        if symbol not in self.signals:
            logger.warning("信号数据中不存在交易对: %s", symbol)
            return None

        nearest_ts = find_nearest_timestamp(int(target_timestamp), self.timestamps.tolist(), allow_future=False)
        if nearest_ts is None:
            logger.debug("未找到 %s 在时间戳 %s 之前的信号", symbol, target_timestamp)
            return None

        idx = int(np.searchsorted(self.timestamps, nearest_ts))
        if idx >= len(self.timestamps):
            idx = len(self.timestamps) - 1

        value = float(self.signals[symbol][idx])
        logger.debug("获取信号 %s at %s (使用 %s): %s", symbol, target_timestamp, nearest_ts, value)
        return value

    def get_signals_at_time(self, target_timestamp: int, symbols: List[str]) -> Dict[str, float]:
        return {
            symbol: val
            for symbol in symbols
            if (val := self.get_signal_at_time(target_timestamp, symbol)) is not None
        }

    def load(self):
        return self.load_all()
