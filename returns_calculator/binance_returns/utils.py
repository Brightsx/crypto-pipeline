# -*- coding: utf-8 -*-
import os, logging, pandas as pd
from pathlib import Path

def setup_logger(log_dir: Path):
    os.makedirs(log_dir, exist_ok=True)
    log_path = log_dir / "run.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )

def daterange_batches_half_open(start: pd.Timestamp, end: pd.Timestamp, step_days: int):
    """半开区间 [start, end)，生成批次 (start, end_excl)。"""
    cur = start.floor("D")
    last_excl = end + pd.Timedelta(minutes=1)
    while cur < last_excl:
        next_cur = cur + pd.Timedelta(days=step_days)
        yield cur, min(next_cur, last_excl)
        cur = next_cur
