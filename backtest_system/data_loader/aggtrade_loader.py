
"""AggTrade 数据加载器"""
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import Dict, List

import pandas as pd

from .base_loader import LargeFileLoader

logger = logging.getLogger(__name__)


class AggTradeLoader(LargeFileLoader):
    """AggTrade 数据加载器，按日分文件加载。"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.path_template = config.get("path_template")
        if not self.path_template:
            raise ValueError("AggTradeLoader需要配置 path_template")

    def load_period(self, start: datetime, end: datetime, symbol: str) -> pd.DataFrame:
        cache_key = f"{symbol}_{start.date()}_{end.date()}"

        if cache_key in self.cache:
            df = self.cache[cache_key]
            logger.debug("从缓存加载 %s aggtrade数据: %s 到 %s", symbol, start.date(), end.date())
            return self._filter_by_time(df, start, end)

        all_data: List[pd.DataFrame] = []
        current_date = start.date()
        end_date = end.date()

        while current_date <= end_date:
            file_path = self._get_file_path(symbol, current_date)
            path = Path(file_path)

            if path.exists():
                try:
                    df = pd.read_parquet(path)
                    all_data.append(df)
                    logger.debug("加载文件: %s, 行数: %d", file_path, len(df))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("加载文件失败 %s: %s", file_path, exc)
            else:
                logger.warning("文件不存在: %s", file_path)

            current_date += timedelta(days=1)

        if not all_data:
            logger.warning("未找到 %s 在 %s 到 %s 的数据", symbol, start.date(), end.date())
            return pd.DataFrame()

        df_all = (
            pd.concat(all_data, ignore_index=True)
            .sort_values("transact_time")
            .reset_index(drop=True)
        )
        self.cache[cache_key] = df_all
        logger.info("加载 %s aggtrade数据: %s 到 %s, 总行数: %d", symbol, start.date(), end.date(), len(df_all))
        return self._filter_by_time(df_all, start, end)

    def _get_file_path(self, symbol: str, date) -> str:
        return self.path_template.format(
            symbol=symbol,
            YYYY=date.year,
            MM=f"{date.month:02d}",
            DD=f"{date.day:02d}",
        )

    def _filter_by_time(self, df: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
        if df.empty:
            return df

        if self.time_unit == "ms":
            start_ts = int(start.timestamp() * 1000)
            end_ts = int(end.timestamp() * 1000)
        else:
            start_ts = int(start.timestamp())
            end_ts = int(end.timestamp())

        mask = (df["transact_time"] >= start_ts) & (df["transact_time"] <= end_ts)
        filtered = df.loc[mask].copy()
        logger.debug("时间过滤: %d -> %d 行", len(df), len(filtered))
        return filtered

    def get_vwap(self, df: pd.DataFrame, start: datetime, end: datetime):
        window_df = self._filter_by_time(df, start, end)
        if window_df.empty:
            return None

        total_value = (window_df["price"] * window_df["quantity"]).sum()
        total_quantity = window_df["quantity"].sum()
        if total_quantity == 0:
            return None
        return float(total_value / total_quantity)

    def get_total_volume(self, df: pd.DataFrame, start: datetime, end: datetime) -> float:
        window_df = self._filter_by_time(df, start, end)
        if window_df.empty:
            return 0.0
        return float(window_df["quantity"].sum())

    def get_last_price(self, df: pd.DataFrame, before_time: datetime):
        if self.time_unit == "ms":
            before_ts = int(before_time.timestamp() * 1000)
        else:
            before_ts = int(before_time.timestamp())

        filtered = df.loc[df["transact_time"] <= before_ts]
        if filtered.empty:
            return None
        return float(filtered.iloc[-1]["price"])

    def load(self, start: datetime, end: datetime, symbols: list) -> Dict[str, pd.DataFrame]:
        return {symbol: self.load_period(start, end, symbol) for symbol in symbols}
