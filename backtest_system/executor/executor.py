
"""交易执行模块"""
from datetime import timedelta
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class Executor:
    """交易执行器，负责从目标仓位到实际成交。"""

    def __init__(self, config: dict):
        self.config = config
        params = config.get("params", {})

        self.execution_delay = params.get("execution_delay", 10)
        self.execution_window = params.get("execution_window", 20)
        self.fee_rate = params.get("fee_rate", 0.0004)
        self.slippage_rate = params.get("slippage_rate", 0.0001)
        self.max_volume_pct = params.get("max_volume_pct", 0.10)

        logger.info(
            "执行器初始化: delay=%ss, window=%ss, fee=%s, slippage=%s, max_vol=%.2f%%",
            self.execution_delay,
            self.execution_window,
            self.fee_rate,
            self.slippage_rate,
            self.max_volume_pct * 100,
        )

    def execute(
        self,
        current_time,
        target_positions: Dict[str, float],
        current_positions: Dict[str, float],
        current_prices: Dict[str, float],
        aggtrade_loader,
        aggtrade_data: Dict[str, "pd.DataFrame"],
        next_time,
    ) -> Tuple[Dict[str, dict], dict]:
        trades: Dict[str, dict] = {}
        execution_info = {
            "total_fee": 0.0,
            "trade_pnl": 0.0,
            "executed_symbols": [],
        }

        logger.info("[%s] 开始执行交易", current_time)

        for symbol, target_pos in target_positions.items():
            cur_pos = current_positions.get(symbol, 0.0)
            cur_price = current_prices.get(symbol)

            trade_qty = target_pos - cur_pos
            if abs(trade_qty) < 1e-8:
                logger.debug("[%s] %s: 无需交易", current_time, symbol)
                continue

            trade_info = self._execute_single_trade(
                current_time=current_time,
                symbol=symbol,
                trade_quantity=trade_qty,
                current_price=cur_price,
                current_position=cur_pos,
                aggtrade_loader=aggtrade_loader,
                aggtrade_df=aggtrade_data.get(symbol),
                next_time=next_time,
            )

            if trade_info is None:
                continue

            trades[symbol] = trade_info
            execution_info["total_fee"] += trade_info["fee"]
            execution_info["trade_pnl"] += trade_info["trade_pnl"]
            execution_info["executed_symbols"].append(symbol)

        logger.info(
            "[%s] 交易执行完成: 总手续费=%.2f USDT, 交易PnL=%.2f USDT",
            current_time,
            execution_info["total_fee"],
            execution_info["trade_pnl"],
        )
        return trades, execution_info

    def _execute_single_trade(
        self,
        current_time,
        symbol: str,
        trade_quantity: float,
        current_price: float,
        current_position: float,
        aggtrade_loader,
        aggtrade_df,
        next_time,
    ):
        import pandas as pd  # type: ignore

        if aggtrade_df is None or isinstance(aggtrade_df, pd.DataFrame) and aggtrade_df.empty:
            if current_price is None:
                logger.warning("[%s] %s: 无成交数据且当前价格无效，跳过交易", current_time, symbol)
                return None
            vwap = current_price
            total_volume = 0.0
            exec_start = current_time
            exec_end = next_time
        else:
            exec_start = current_time + timedelta(seconds=self.execution_delay)
            exec_end = min(exec_start + timedelta(seconds=self.execution_window), next_time)

            logger.debug("[%s] %s: 执行窗口 %s -> %s", current_time, symbol, exec_start, exec_end)
            vwap = aggtrade_loader.get_vwap(aggtrade_df, exec_start, exec_end)
            total_volume = aggtrade_loader.get_total_volume(aggtrade_df, exec_start, exec_end)

            if vwap is None:
                logger.warning("[%s] %s: 窗口无成交数据，使用当前价格", current_time, symbol)
                vwap = current_price or 0.0

        max_tradable = total_volume * self.max_volume_pct
        actual_qty = trade_quantity

        if total_volume > 0 and abs(trade_quantity) > max_tradable:
            actual_qty = max_tradable if trade_quantity > 0 else -max_tradable
            logger.warning(
                "[%s] %s: 交易量受限 %.6f -> %.6f",
                current_time,
                symbol,
                abs(trade_quantity),
                abs(actual_qty),
            )

        if abs(actual_qty) < 1e-12:
            logger.info("[%s] %s: 受成交量限制，实际成交量为 0，跳过", current_time, symbol)
            return None

        if actual_qty > 0:
            execution_price = vwap * (1 + self.slippage_rate)
        else:
            execution_price = vwap * (1 - self.slippage_rate)

        trade_value = abs(actual_qty) * execution_price
        fee = trade_value * self.fee_rate

        if aggtrade_df is not None and not aggtrade_df.empty:
            window_end_price = aggtrade_loader.get_last_price(aggtrade_df, exec_end)
        else:
            window_end_price = None

        if window_end_price is None:
            window_end_price = execution_price

        trade_pnl = actual_qty * (window_end_price - execution_price)

        info = {
            "symbol": symbol,
            "time": current_time,
            "target_quantity": trade_quantity,
            "actual_quantity": actual_qty,
            "vwap": vwap,
            "execution_price": execution_price,
            "trade_value": trade_value,
            "fee": fee,
            "slippage": execution_price - vwap,
            "total_volume": total_volume,
            "max_tradable": max_tradable,
            "trade_pnl": trade_pnl,
            "window_end_price": window_end_price,
        }

        logger.info(
            "[%s] %s: 成交 %.6f @ %.4f, 手续费=%.2f USDT, 交易PnL=%.2f USDT",
            current_time,
            symbol,
            actual_qty,
            execution_price,
            fee,
            trade_pnl,
        )
        return info

    def update_positions(self, current_positions: Dict[str, float], trades: Dict[str, dict]) -> Dict[str, float]:
        new_positions = dict(current_positions)
        for symbol, trade in trades.items():
            new_positions[symbol] = new_positions.get(symbol, 0.0) + trade["actual_quantity"]
        return new_positions
