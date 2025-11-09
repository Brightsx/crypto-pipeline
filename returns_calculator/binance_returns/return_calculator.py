# -*- coding: utf-8 -*-
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import List
import pandas as pd
import numpy as np
import re

from .data_loader import list_parquet_files, read_price_series

logger = logging.getLogger(__name__)


# ==============================================================
# 工具函数
# ==============================================================
def _norm_freq(s: str) -> str:
    """Normalize user freq like '1m','3s','1h','1d' to pandas date_range freq."""
    s = s.strip().lower()
    m = re.fullmatch(r'(\d+)\s*([smhd])', s)
    if not m:
        return s  # fallback
    n, u = m.groups()
    if u == 's':
        return f"{n}s"
    if u == 'm':
        return f"{n}min"
    if u == 'h':
        return f"{n}H"
    if u == 'd':
        return f"{n}D"
    return s


def build_time_grid(start_utc: str, end_utc: str, interval: str) -> pd.DatetimeIndex:
    freq = _norm_freq(interval)
    idx = pd.date_range(
        pd.Timestamp(start_utc, tz="UTC"),
        pd.Timestamp(end_utc, tz="UTC"),
        freq=freq,
        inclusive="both",
    )
    return idx.tz_convert("UTC")


def _fmt_td(td: pd.Timedelta) -> str:
    """格式化 timedelta 为可读字符串，如 9s, 1m, 1h, 1d"""
    c = td.components
    parts = []
    if c.days:
        parts.append(f"{c.days}d")
    if c.hours:
        parts.append(f"{c.hours}h")
    if c.minutes:
        parts.append(f"{c.minutes}m")
    secs = int(round(c.seconds))
    if secs:
        parts.append(f"{secs}s")
    if not parts:
        parts.append("0s")
    return "".join(parts)


# ==============================================================
# 数据结构定义
# ==============================================================
@dataclass(frozen=True)
class Combo:
    delay: pd.Timedelta
    period: pd.Timedelta

    @property
    def colname(self) -> str:
        return f"ret_delay_{_fmt_td(self.delay)}_period_{_fmt_td(self.period)}"


# ==============================================================
# 主计算函数
# ==============================================================
def compute_returns_for_batch(
    symbol: str,
    base_path: str,
    kline_window: str,
    price_column: str,
    grid: pd.DatetimeIndex,
    batch_start: pd.Timestamp,         # inclusive
    batch_end_excl: pd.Timestamp,      # exclusive
    combos: List[Combo],
    margin_days: int,
) -> pd.DataFrame:
    """对 [batch_start, batch_end_excl) 的网格时刻 T 计算所有收益列，返回一个 DataFrame（索引为 T）。"""
    min_delay = min([c.delay for c in combos]) if combos else pd.Timedelta(0)
    max_horizon = max([c.delay + c.period for c in combos]) if combos else pd.Timedelta(0)

    # 读取价格文件范围
    k_start = (batch_start + min_delay).normalize()
    k_end = (batch_end_excl + max_horizon + pd.Timedelta(days=margin_days)).normalize()

    files = list_parquet_files(base_path, symbol, kline_window, k_start, k_end)
    logger.info(f"[{symbol}] 读取文件数: {len(files)} 覆盖 {k_start.date()} 至 {k_end.date()}")
    price = read_price_series(files, price_column=price_column)

    sub_grid = grid[(grid >= batch_start) & (grid < batch_end_excl)]
    if price.empty or len(sub_grid) == 0:
        if price.empty:
            logger.warning(f"[{symbol}] 批次 {batch_start}~{batch_end_excl} 无价格数据，填充空结果。")
        out = pd.DataFrame(index=sub_grid)
        for c in combos:
            out[c.colname] = np.nan
        return out

    # ==========================================================
    # Step 1: 保证索引升序唯一
    # ==========================================================
    price = price.sort_index()
    price = price[~price.index.duplicated(keep="last")]

    # ==========================================================
    # Step 2: 用未来最近的非 NaN 值替代所有 NaN
    # ==========================================================
    n_before = int(price.isna().sum())
    price = price.bfill()       # 值层面向未来填充
    price = price.ffill()       # 若尾部仍 NaN，用最后价顶上
    n_after = int(price.isna().sum())
    if n_before > 0:
        logger.info(f"[{symbol}] NaN价格修复: {n_before} -> {n_after} (bfill+ffill)")
    # ==========================================================

    result = pd.DataFrame(index=sub_grid)

    # ==========================================================
    # Step 3: 计算所有组合收益率
    # ==========================================================
    for c in combos:
        s_times = (sub_grid + c.delay)
        e_times = (sub_grid + c.delay + c.period)

        start_price = price.reindex(s_times, method="bfill").reindex(s_times)
        end_price   = price.reindex(e_times, method="bfill").reindex(e_times)

        n_start_nan = int(start_price.isna().sum())
        n_end_nan = int(end_price.isna().sum())
        if n_start_nan or n_end_nan:
            logger.debug(f"[{symbol}] {c.colname}: start NaN={n_start_nan}, end NaN={n_end_nan}")

        ret = (end_price.values / start_price.values) - 1.0
        result[c.colname] = ret

    logger.info(f"[{symbol}] 批次完成: {sub_grid[0]} ~ {sub_grid[-1]} 行={len(result)} 列={len(result.columns)}")
    return result


# ==============================================================
# 拼接批次结果
# ==============================================================
def stitch_batches(batches: List[pd.DataFrame]) -> pd.DataFrame:
    if not batches:
        return pd.DataFrame()
    df = pd.concat(batches).sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df
