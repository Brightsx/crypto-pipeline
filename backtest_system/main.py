
"""主回测程序入口"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import timedelta
from pathlib import Path
from typing import Dict, Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.time_utils import (
    parse_frequency,
    parse_datetime_str,
    generate_time_range,
    datetime_to_timestamp,
)
from data_loader.aggtrade_loader import AggTradeLoader
from data_loader.signal_loader import SignalLoader
from data_loader.funding_rate_loader import FundingRateLoader
from optimizer.simple_optimizer import SimpleOptimizer
from executor.executor import Executor
from metrics import Recorder
from funding import FundingSettlement


def setup_logging(config: Dict[str, Any]) -> None:
    log_config = config.get("logging", {})
    level = getattr(logging, log_config.get("level", "INFO"))
    fmt = log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    date_fmt = log_config.get("date_format", "%Y-%m-%d %H:%M:%S")
    logging.basicConfig(level=level, format=fmt, datefmt=date_fmt)


class BacktestEngine:
    """回测引擎"""

    def __init__(self, config_path: str):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        setup_logging(self.config)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("=" * 60)
        self.logger.info("回测系统启动")
        self.logger.info("=" * 60)

        bt_cfg = self.config["backtest"]
        self.start_time = parse_datetime_str(bt_cfg["start_time"])
        self.end_time = parse_datetime_str(bt_cfg["end_time"])
        self.frequency = parse_frequency(bt_cfg["frequency"])
        self.initial_usdt = float(bt_cfg["initial_usdt"])
        self.symbols = list(bt_cfg["symbols"])

        self.logger.info("回测时间: %s 至 %s (UTC)", self.start_time, self.end_time)
        self.logger.info("回测频率: %s", bt_cfg["frequency"])
        self.logger.info("初始保证金: %.2f USDT", self.initial_usdt)
        self.logger.info("交易对: %s", self.symbols)

        self._init_modules()

        self.current_usdt = self.initial_usdt
        self.current_positions: Dict[str, float] = {s: 0.0 for s in self.symbols}
        self.current_prices: Dict[str, float] = {s: 0.0 for s in self.symbols}

    def _init_modules(self) -> None:
        self.logger.info("初始化模块...")

        dl_cfg = self.config["data_loader"]
        self.aggtrade_loader = AggTradeLoader(dl_cfg["aggtrade"])
        self.signal_loader = SignalLoader(dl_cfg["signal"])
        self.funding_rate_loader = FundingRateLoader(dl_cfg["funding_rate"])
        self.signal_loader.load_all()

        self.optimizer = SimpleOptimizer(self.config["optimizer"])
        self.executor = Executor(self.config["executor"])
        self.recorder = Recorder(self.config["metrics"])

        self.funding_settlement = FundingSettlement(
            time_unit=self.funding_rate_loader.get_time_unit(),
            tolerance_ms=1000,
        )

        self.logger.info("模块初始化完成")

    def _load_period_data(self, start, end):
        extended_start = start - timedelta(days=1)
        extended_end = end + timedelta(seconds=120)

        aggtrade_data = {
            symbol: self.aggtrade_loader.load_period(extended_start, extended_end, symbol)
            for symbol in self.symbols
        }
        funding_data = {
            symbol: self.funding_rate_loader.load_period(extended_start, end, symbol)
            for symbol in self.symbols
        }
        return aggtrade_data, funding_data

    def _update_prices(self, current_time, aggtrade_data: dict) -> None:
        for symbol in self.symbols:
            df = aggtrade_data.get(symbol)
            if df is None or df.empty:
                self.logger.warning("[%s] %s 无价格数据", current_time, symbol)
                continue

            price = self.aggtrade_loader.get_last_price(df, current_time)
            if price is not None:
                self.current_prices[symbol] = price
            else:
                self.logger.warning("[%s] %s 无法获取价格", current_time, symbol)

    def _calculate_pnl(
        self,
        prev_prices: Dict[str, float],
        current_prices: Dict[str, float],
        prev_positions: Dict[str, float],
        execution_info: Dict[str, Any],
    ) -> tuple[float, float, float]:
        trade_pnl = float(execution_info.get("trade_pnl", 0.0))

        hold_pnl = 0.0
        for symbol in self.symbols:
            prev_pos = prev_positions.get(symbol, 0.0)
            prev_price = prev_prices.get(symbol, 0.0)
            curr_price = current_prices.get(symbol, 0.0)
            if prev_pos and prev_price and curr_price:
                hold_pnl += prev_pos * (curr_price - prev_price)

        fee_pnl = -float(execution_info.get("total_fee", 0.0))
        return trade_pnl, hold_pnl, fee_pnl

    def run(self) -> Dict[str, Any]:
        self.logger.info("=" * 60)
        self.logger.info("开始回测")
        self.logger.info("=" * 60)

        self.recorder.record_initial_state(self.start_time, self.current_usdt, self.symbols)

        time_points = list(generate_time_range(self.start_time, self.end_time, self.frequency))
        self.logger.info("总共 %d 个时间点", len(time_points))

        current_load_start = None
        load_period = timedelta(days=1)
        aggtrade_data: dict = {}
        funding_data: dict = {}

        for idx, current_time in enumerate(time_points):
            if current_load_start is None or current_time >= current_load_start + load_period:
                current_load_start = current_time
                load_end = min(current_time + load_period, self.end_time + timedelta(seconds=120))
                self.logger.info("加载数据: %s 至 %s", current_load_start.date(), load_end.date())
                aggtrade_data, funding_data = self._load_period_data(current_load_start, load_end)

            next_time = time_points[idx + 1] if idx + 1 < len(time_points) else self.end_time

            self.logger.info("\n%s", "=" * 60)
            self.logger.info("周期 %d/%d: %s", idx + 1, len(time_points), current_time)
            self.logger.info("%s", "=" * 60)

            # 1. 更新当前价格（周期开始价）
            prev_prices = dict(self.current_prices)
            self._update_prices(current_time, aggtrade_data)

            # 2. 获取信号（只用过去的）
            current_ts = datetime_to_timestamp(current_time, self.signal_loader.get_time_unit())
            signals = self.signal_loader.get_signals_at_time(current_ts, self.symbols)
            if not signals:
                self.logger.warning("[%s] 未获取到信号，信号视为0", current_time)
                signals = {s: 0.0 for s in self.symbols}

            # 3. 优化目标仓位
            prev_positions = dict(self.current_positions)
            target_positions = self.optimizer.optimize(
                current_time,
                signals,
                self.current_positions,
                self.current_prices,
                self.current_usdt,
            )

            # 4. 执行交易
            trades, execution_info = self.executor.execute(
                current_time,
                target_positions,
                self.current_positions,
                self.current_prices,
                self.aggtrade_loader,
                aggtrade_data,
                next_time,
            )

            # 5. 更新仓位（保证金稍后更新）
            self.current_positions = self.executor.update_positions(self.current_positions, trades)

            # 6. 记录成交
            self.recorder.record_trades(current_time, next_time, trades)

            # 7. 更新周期结束价格
            self._update_prices(next_time, aggtrade_data)

            # 8. 计算交易/持仓/手续费 PnL
            trade_pnl, hold_pnl, fee_pnl = self._calculate_pnl(
                prev_prices, self.current_prices, prev_positions, execution_info
            )
            total_pnl_before_funding = trade_pnl + hold_pnl + fee_pnl
            self.current_usdt += total_pnl_before_funding

            # 9. 检查爆仓（先考虑价格+手续费的影响）
            if self.current_usdt <= 0:
                self.logger.warning("[%s] 爆仓(价格/手续费导致)! 保证金: %.2f", current_time, self.current_usdt)
                self.current_usdt = 0.0
                self.current_positions = {s: 0.0 for s in self.symbols}

            # 10. 资金费率结算 (使用本周期已成交后的仓位和周期结束价)
            funding_pnl = 0.0
            if self.current_usdt > 0:
                funding_pnl = self.funding_settlement.settle(
                    current_time=next_time,
                    symbols=self.symbols,
                    positions=self.current_positions,
                    prices=self.current_prices,
                    funding_data=funding_data,
                )
                self.current_usdt += funding_pnl

                # 资金费率也可能导致爆仓
                if self.current_usdt <= 0:
                    self.logger.warning("[%s] 爆仓(资金费率导致)! 保证金: %.2f", next_time, self.current_usdt)
                    self.current_usdt = 0.0
                    self.current_positions = {s: 0.0 for s in self.symbols}

            # 11. 记录状态（使用周期结束时间 next_time）
            if next_time != current_time:
                self.recorder.record_position_state(
                    time=next_time,
                    usdt_balance=self.current_usdt,
                    positions=self.current_positions,
                    prices=self.current_prices,
                    trade_pnl=trade_pnl,
                    hold_pnl=hold_pnl,
                    fee_pnl=fee_pnl,
                    funding_pnl=funding_pnl,
                )

            self.logger.info("[%s] 周期结束: USDT=%.2f", next_time, self.current_usdt)

        self.logger.info("\n%s", "=" * 60)
        self.logger.info("回测完成")
        self.logger.info("%s", "=" * 60)

        self.recorder.save_records()
        summary = self.recorder.get_summary()
        return summary


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="多币种合约回测系统")
    parser.add_argument(
        "-c",
        "--config",
        default=str(PROJECT_ROOT / "config" / "config.yaml"),
        help="配置文件路径 (默认: config/config.yaml)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    config_path = args.config
    print("Using config:", config_path)

    try:
        engine = BacktestEngine(config_path)
        summary = engine.run()

        print("\n" + "=" * 60)
        print("回测完成!")
        print("=" * 60)
        print(f"初始保证金: {summary['initial_balance']:.2f} USDT")
        print(f"最终保证金: {summary['final_balance']:.2f} USDT")
        print(f"总收益率: {summary['total_return']:.2%}")
        print("=" * 60)
    except Exception as exc:  # noqa: BLE001
        logging.error("回测失败: %s", exc, exc_info=True)
        raise


if __name__ == "__main__":
    main()
