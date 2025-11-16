
"""资金费率数据加载器"""
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import logging
import pandas as pd

from .base_loader import LargeFileLoader

logger = logging.getLogger(__name__)


class FundingRateLoader(LargeFileLoader):
    """资金费率数据加载器，按月加载数据。"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.path_template = config.get("path_template")
        if not self.path_template:
            raise ValueError("FundingRateLoader需要配置 path_template")

    def load_period(self, start: datetime, end: datetime, symbol: str) -> pd.DataFrame:
        cache_key = f"{symbol}_{start.year}-{start.month}_{end.year}-{end.month}"

        if cache_key in self.cache:
            df = self.cache[cache_key]
            logger.debug("从缓存加载 %s 资金费率数据", symbol)
            return self._filter_by_time(df, start, end)

        all_data: List[pd.DataFrame] = []
        current_month = start.replace(day=1)
        end_month = end.replace(day=1)

        while current_month <= end_month:
            file_path = self._get_file_path(symbol, current_month)
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

            if current_month.month == 12:
                current_month = current_month.replace(year=current_month.year + 1, month=1)
            else:
                current_month = current_month.replace(month=current_month.month + 1)

        if not all_data:
            logger.warning("未找到 %s 的资金费率数据", symbol)
            return pd.DataFrame()

        df_all = (
            pd.concat(all_data, ignore_index=True)
            .sort_values("calc_time")
            .reset_index(drop=True)
        )
        self.cache[cache_key] = df_all
        logger.info("加载 %s 资金费率数据: %d 行", symbol, len(df_all))
        return self._filter_by_time(df_all, start, end)

    def _get_file_path(self, symbol: str, date: datetime) -> str:
        return self.path_template.format(
            symbol=symbol,
            YYYY=date.year,
            MM=f"{date.month:02d}",
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

        mask = (df["calc_time"] >= start_ts) & (df["calc_time"] <= end_ts)
        return df.loc[mask].copy()

    def load(self, start: datetime, end: datetime, symbols: list) -> Dict[str, pd.DataFrame]:
        return {symbol: self.load_period(start, end, symbol) for symbol in symbols}
