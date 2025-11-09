# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd

def _date_range_days(start, end):
    return pd.date_range(start.normalize(), end.normalize(), freq="D", tz="UTC", inclusive="both")

def list_parquet_files(base_path, symbol, kline_window, date_from, date_to):
    folder = Path(base_path) / symbol / f"aggTrades_kline_{kline_window}"
    return [folder / f"{symbol}-kline-{kline_window}-{d.strftime('%Y-%m-%d')}.parquet"
            for d in _date_range_days(date_from, date_to) if (folder / f"{symbol}-kline-{kline_window}-{d.strftime('%Y-%m-%d')}.parquet").exists()]

def read_price_series(files, price_column):
    import numpy as np
    series_list = []
    for f in files:
        try:
            df = pd.read_parquet(f)
        except Exception:
            continue
        if "start_time" not in df.columns:
            continue
        col = price_column
        if col not in df.columns:
            low = {c.lower(): c for c in df.columns}
            if price_column.lower() in low:
                col = low[price_column.lower()]
            else:
                continue
        ts = pd.to_datetime(df["start_time"].values, unit="ms", utc=True)
        series_list.append(pd.Series(df[col].values, index=ts, name="price"))
    if not series_list:
        return pd.Series(dtype="float64")
    s = pd.concat(series_list).sort_index()
    return s[~s.index.duplicated(keep="last")]
