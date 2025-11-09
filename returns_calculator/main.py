# -*- coding: utf-8 -*-
import pandas as pd
from pathlib import Path
from binance_returns.config_loader import load_config
from binance_returns.return_calculator import build_time_grid, Combo, compute_returns_for_batch, stitch_batches
from binance_returns.utils import setup_logger, daterange_batches_half_open
import logging

def main():
    root = Path(__file__).resolve().parent
    cfg = load_config(root / "config" / "config.yaml")
    setup_logger(root / "logs")
    logging.info("配置加载完成。")

    start = pd.Timestamp(cfg.time_range.start_time, tz="UTC")
    end   = pd.Timestamp(cfg.time_range.end_time, tz="UTC")
    grid = build_time_grid(cfg.time_range.start_time, cfg.time_range.end_time, cfg.time_range.interval)
    logging.info(f"时间网格：{grid[0]} ~ {grid[-1]} 共 {len(grid)} 点")

    combos = [Combo(pd.to_timedelta(d), pd.to_timedelta(p))
              for d in cfg.returns.delays for p in cfg.returns.periods]
    logging.info(f"组合数量：{len(combos)}")

    out_dir = root / cfg.output.dir
    out_dir.mkdir(parents=True, exist_ok=True)

    for sym in cfg.symbols:
        logging.info(f"==== 开始 {sym} ====")
        batches = []
        for bstart, bend_excl in daterange_batches_half_open(start, end, cfg.batch.batch_days):
            dfb = compute_returns_for_batch(
                symbol=sym,
                base_path=cfg.data.base_path,
                kline_window=cfg.data.kline_window,
                price_column=cfg.data.price_column,
                grid=grid,
                batch_start=bstart, batch_end_excl=bend_excl,
                combos=combos,
                margin_days=cfg.batch.margin_days,
            )
            batches.append(dfb)

        df_all = stitch_batches(batches)
        df_all.index.name = "timestamp"
        out_name = cfg.output.filename_pattern.format(
            symbol=sym,
            kline_window=cfg.data.kline_window,
            interval=cfg.time_range.interval)
        df_all.to_parquet(out_dir / out_name)
        logging.info(f"[{sym}] 输出完成：{out_name}")

    logging.info("全部完成。")

if __name__ == "__main__":
    main()
