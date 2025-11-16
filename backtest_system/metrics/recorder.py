
"""回测过程记录与统计模块"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    start_time: datetime
    end_time: datetime
    symbol: str
    target_quantity: float
    actual_quantity: float
    vwap: float
    execution_price: float
    trade_value: float
    fee: float
    slippage: float
    total_volume: float
    max_tradable: float
    trade_pnl: float
    window_end_price: float


@dataclass
class PositionStateRecord:
    time: datetime
    usdt_balance: float
    prices: Dict[str, float]
    positions: Dict[str, float]
    trade_pnl: float
    hold_pnl: float
    fee_pnl: float
    funding_pnl: float


class Recorder:
    """记录每个周期的成交与状态，支持实时写入 CSV。"""

    def __init__(self, config: dict):
        self.config = config
        path_cfg = config.get("paths", {})
        self.trade_log_path = Path(path_cfg.get("trade_log", "logs/trade_log.csv"))
        self.state_log_path = Path(path_cfg.get("state_log", "logs/state_log.csv"))

        self.trade_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_log_path.parent.mkdir(parents=True, exist_ok=True)

        # 启动时清空文件
        self.trade_log_path.write_text("", encoding="utf-8")
        self.state_log_path.write_text("", encoding="utf-8")

        self._trade_header_written = False
        self._state_header_written = False

        self._state_records: List[PositionStateRecord] = []
        self._initial_balance: float | None = None

        logger.info(
            "Recorder 初始化: trade_log=%s, state_log=%s",
            self.trade_log_path,
            self.state_log_path,
        )

    # ---- 记录函数 ----
    def record_initial_state(self, time: datetime, initial_usdt: float, symbols: List[str]):
        self._initial_balance = float(initial_usdt)
        empty_positions = {s: 0.0 for s in symbols}
        empty_prices = {s: 0.0 for s in symbols}
        self.record_position_state(
            time=time,
            usdt_balance=initial_usdt,
            positions=empty_positions,
            prices=empty_prices,
            trade_pnl=0.0,
            hold_pnl=0.0,
            fee_pnl=0.0,
            funding_pnl=0.0,
        )
        logger.info("记录初始状态: %.2f USDT", initial_usdt)

    def record_trades(self, start_time: datetime, end_time: datetime, trades: Dict[str, dict]):
        if not trades:
            return

        records = []
        for symbol, t in trades.items():
            rec = TradeRecord(
                start_time=start_time,
                end_time=end_time,
                symbol=symbol,
                target_quantity=float(t["target_quantity"]),
                actual_quantity=float(t["actual_quantity"]),
                vwap=float(t["vwap"]),
                execution_price=float(t["execution_price"]),
                trade_value=float(t["trade_value"]),
                fee=float(t["fee"]),
                slippage=float(t["slippage"]),
                total_volume=float(t["total_volume"]),
                max_tradable=float(t["max_tradable"]),
                trade_pnl=float(t["trade_pnl"]),
                window_end_price=float(t["window_end_price"]),
            )
            records.append(rec)

        if not records:
            return

        df = pd.DataFrame([asdict(r) for r in records])
        header = not self._trade_header_written
        df.to_csv(self.trade_log_path, mode="a", index=False, header=header)
        self._trade_header_written = True

    def record_position_state(
        self,
        time: datetime,
        usdt_balance: float,
        positions: Dict[str, float],
        prices: Dict[str, float],
        trade_pnl: float,
        hold_pnl: float,
        fee_pnl: float,
        funding_pnl: float,
    ):
        rec = PositionStateRecord(
            time=time,
            usdt_balance=float(usdt_balance),
            positions=dict(positions),
            prices=dict(prices),
            trade_pnl=float(trade_pnl),
            hold_pnl=float(hold_pnl),
            fee_pnl=float(fee_pnl),
            funding_pnl=float(funding_pnl),
        )
        self._state_records.append(rec)

        df = pd.DataFrame([asdict(rec)])
        header = not self._state_header_written
        df.to_csv(self.state_log_path, mode="a", index=False, header=header)
        self._state_header_written = True

    # ---- 保存与汇总 ----
    def save_records(self):
        """记录已实时写入，此处保留接口不再重复写。"""
        logger.info("Recorder 使用实时写入 CSV, save_records 无需额外操作")

    def get_summary(self) -> Dict[str, Any]:
        if not self._state_records:
            return {
                "initial_balance": self._initial_balance or 0.0,
                "final_balance": self._initial_balance or 0.0,
                "total_return": 0.0,
            }

        initial = self._initial_balance if self._initial_balance is not None else self._state_records[0].usdt_balance
        final = self._state_records[-1].usdt_balance
        total_ret = (final - initial) / initial if initial != 0 else 0.0
        return {
            "initial_balance": float(initial),
            "final_balance": float(final),
            "total_return": float(total_ret),
        }
