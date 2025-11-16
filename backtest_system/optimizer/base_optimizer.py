
"""优化器基类"""
from abc import ABC, abstractmethod
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class BaseOptimizer(ABC):
    """优化器基类。"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.params = config.get("params", {})
        logger.info("初始化%s, 参数: %s", self.__class__.__name__, self.params)

    @abstractmethod
    def optimize(
        self,
        current_time,
        signals: Dict[str, float],
        current_positions: Dict[str, float],
        current_prices: Dict[str, float],
        usdt_balance: float,
        **kwargs,
    ) -> Dict[str, float]:
        raise NotImplementedError

    def _log_optimization(
        self,
        current_time,
        signals: Dict[str, float],
        current_positions: Dict[str, float],
        target_positions: Dict[str, float],
        current_prices: Dict[str, float],
    ):
        logger.info("[%s] 优化完成:", current_time)
        for symbol, signal in signals.items():
            cur_pos = current_positions.get(symbol, 0.0)
            target_pos = target_positions.get(symbol, 0.0)
            price = current_prices.get(symbol, 0.0)
            logger.info(
                "  %s: 信号=%.4f, 当前仓位=%.4f, 目标仓位=%.4f, 价格=%.2f",
                symbol,
                signal,
                cur_pos,
                target_pos,
                price,
            )
