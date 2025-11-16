
"""简单线性优化器示例"""
import logging
from typing import Dict

from .base_optimizer import BaseOptimizer

logger = logging.getLogger(__name__)


class SimpleOptimizer(BaseOptimizer):
    """简单线性优化器。"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.signal_multiplier = float(self.params.get("signal_multiplier", 10.0))
        self.max_position_value = float(self.params.get("max_position_value", 50_000.0))
        self.leverage = float(self.params.get("leverage", 3.0))

        logger.info(
            "SimpleOptimizer配置: signal_multiplier=%s, max_position_value=%s, leverage=%s",
            self.signal_multiplier,
            self.max_position_value,
            self.leverage,
        )

    def optimize(
        self,
        current_time,
        signals: Dict[str, float],
        current_positions: Dict[str, float],
        current_prices: Dict[str, float],
        usdt_balance: float,
        **kwargs,
    ) -> Dict[str, float]:
        target_positions: Dict[str, float] = {}

        logger.info("[%s] 开始优化, USDT余额: %.2f", current_time, usdt_balance)

        if usdt_balance <= 0:
            logger.warning("[%s] 保证金不足，已爆仓, 所有目标仓位归零", current_time)
            for symbol in signals.keys():
                target_positions[symbol] = 0.0
            return target_positions

        for symbol, signal in signals.items():
            price = current_prices.get(symbol)
            if not price or price <= 0:
                logger.warning("[%s] %s 价格无效: %s, 目标仓位设为0", current_time, symbol, price)
                target_positions[symbol] = 0.0
                continue

            target_value = signal * self.signal_multiplier * self.leverage * usdt_balance

            if abs(target_value) > self.max_position_value:
                target_value = self.max_position_value if target_value > 0 else -self.max_position_value

            target_quantity = target_value / price
            target_positions[symbol] = target_quantity

            logger.debug(
                "[%s] %s: 信号=%.4f, 目标价值=%.2f USDT, 目标数量=%.6f",
                current_time,
                symbol,
                signal,
                target_value,
                target_quantity,
            )

        self._log_optimization(current_time, signals, current_positions, target_positions, current_prices)
        return target_positions
