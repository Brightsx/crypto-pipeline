
"""资金费率结算逻辑"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Set, Tuple

import pandas as pd

from utils.time_utils import datetime_to_timestamp

logger = logging.getLogger(__name__)


@dataclass
class FundingSettlement:
    """资金费率结算模块。

    - funding_loader 仍由 data_loader 负责加载 DataFrame
    - 本模块只负责在给定时间点、仓位和价格下计算资金费率 PnL
    - 内部维护已结算事件集合，避免重复结算同一个 calc_time
    """

    time_unit: str = "ms"
    tolerance_ms: int = 1000
    settled_events: Set[Tuple[str, int]] = field(default_factory=set)

    def settle(
        self,
        current_time,
        symbols,
        positions: Dict[str, float],
        prices: Dict[str, float],
        funding_data: Dict[str, pd.DataFrame],
    ) -> float:
        """在 current_time 附近结算资金费率。

        使用当前周期结束后的仓位与价格。
        """
        if not symbols:
            return 0.0

        ts = datetime_to_timestamp(current_time, self.time_unit)
        total_pnl = 0.0

        for symbol in symbols:
            df = funding_data.get(symbol)
            if df is None or df.empty:
                continue

            # 找到在 tolerance 范围内的 calc_time
            mask = (df["calc_time"] >= ts - self.tolerance_ms) & (df["calc_time"] <= ts + self.tolerance_ms)
            rows = df.loc[mask]

            for _, row in rows.iterrows():
                calc_ts = int(row["calc_time"])
                key = (symbol, calc_ts)
                if key in self.settled_events:
                    continue

                self.settled_events.add(key)
                rate = float(row["last_funding_rate"])
                pos = positions.get(symbol, 0.0)
                price = prices.get(symbol, 0.0)

                if pos == 0.0 or price == 0.0:
                    continue

                position_value = pos * price
                pnl = -position_value * rate  # 多付空收
                total_pnl += pnl

                logger.info(
                    "[%s] %s 资金费率结算: calc_time=%s, 费率=%.6f, 仓位=%.6f, 价格=%.2f, PnL=%.2f USDT",
                    current_time,
                    symbol,
                    calc_ts,
                    rate,
                    pos,
                    price,
                    pnl,
                )

        if total_pnl != 0.0:
            logger.info("[%s] 资金费率总结算: %.2f USDT", current_time, total_pnl)

        return total_pnl
