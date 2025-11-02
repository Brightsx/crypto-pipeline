"""AggTrade数据加载器"""
from datetime import datetime, timedelta
import pandas as pd
import logging
from pathlib import Path
from .base_loader import LargeFileLoader

logger = logging.getLogger(__name__)


class AggTradeLoader(LargeFileLoader):
    """AggTrade数据加载器，按天加载数据"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.path_template = config.get('path_template')
        if not self.path_template:
            raise ValueError("AggTradeLoader需要配置path_template")
    
    def load_period(self, start: datetime, end: datetime, symbol: str) -> pd.DataFrame:
        """
        加载指定时间段的aggtrade数据
        
        Args:
            start: 开始时间(UTC)
            end: 结束时间(UTC)
            symbol: 交易对，如 BTCUSDT
        
        Returns:
            DataFrame包含aggtrade数据
        """
        cache_key = f"{symbol}_{start.date()}_{end.date()}"
        
        # 检查缓存
        if cache_key in self.cache:
            df = self.cache[cache_key]
            logger.debug(f"从缓存加载 {symbol} aggtrade数据: {start.date()} 到 {end.date()}")
            return self._filter_by_time(df, start, end)
        
        # 加载数据
        all_data = []
        current_date = start.date()
        end_date = end.date()
        
        while current_date <= end_date:
            file_path = self._get_file_path(symbol, current_date)
            
            if Path(file_path).exists():
                try:
                    df = pd.read_parquet(file_path)
                    all_data.append(df)
                    logger.debug(f"加载文件: {file_path}, 行数: {len(df)}")
                except Exception as e:
                    logger.warning(f"加载文件失败 {file_path}: {e}")
            else:
                logger.warning(f"文件不存在: {file_path}")
            
            current_date += timedelta(days=1)
        
        if not all_data:
            logger.warning(f"未找到 {symbol} 在 {start.date()} 到 {end.date()} 的数据")
            return pd.DataFrame()
        
        # 合并数据
        df = pd.concat(all_data, ignore_index=True)
        df = df.sort_values('transact_time').reset_index(drop=True)
        
        # 缓存数据
        self.cache[cache_key] = df
        logger.info(f"加载 {symbol} aggtrade数据: {start.date()} 到 {end.date()}, 总行数: {len(df)}")
        
        return self._filter_by_time(df, start, end)
    
    def _get_file_path(self, symbol: str, date) -> str:
        """构造文件路径"""
        return self.path_template.format(
            symbol=symbol,
            YYYY=date.year,
            MM=f"{date.month:02d}",
            DD=f"{date.day:02d}"
        )
    
    def _filter_by_time(self, df: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
        """根据时间过滤数据"""
        if df.empty:
            return df
        
        # 转换时间戳
        if self.time_unit == 'ms':
            start_ts = int(start.timestamp() * 1000)
            end_ts = int(end.timestamp() * 1000)
        else:
            start_ts = int(start.timestamp())
            end_ts = int(end.timestamp())
        
        mask = (df['transact_time'] >= start_ts) & (df['transact_time'] <= end_ts)
        filtered_df = df[mask].copy()
        
        logger.debug(f"时间过滤: {len(df)} -> {len(filtered_df)} 行")
        return filtered_df
    
    def get_vwap(self, df: pd.DataFrame, start: datetime, end: datetime) -> float:
        """
        计算指定时间窗口的VWAP
        
        Args:
            df: aggtrade数据
            start: 开始时间
            end: 结束时间
        
        Returns:
            VWAP价格，如果没有数据返回None
        """
        window_df = self._filter_by_time(df, start, end)
        
        if window_df.empty:
            return None
        
        total_value = (window_df['price'] * window_df['quantity']).sum()
        total_quantity = window_df['quantity'].sum()
        
        if total_quantity == 0:
            return None
        
        vwap = total_value / total_quantity
        return float(vwap)
    
    def get_total_volume(self, df: pd.DataFrame, start: datetime, end: datetime) -> float:
        """
        获取指定时间窗口的总成交量
        
        Args:
            df: aggtrade数据
            start: 开始时间
            end: 结束时间
        
        Returns:
            总成交量
        """
        window_df = self._filter_by_time(df, start, end)
        
        if window_df.empty:
            return 0.0
        
        return float(window_df['quantity'].sum())
    
    def get_last_price(self, df: pd.DataFrame, before_time: datetime) -> float:
        """
        获取指定时间之前的最后一个成交价
        
        Args:
            df: aggtrade数据
            before_time: 截止时间
        
        Returns:
            最后成交价，如果没有数据返回None
        """
        if self.time_unit == 'ms':
            before_ts = int(before_time.timestamp() * 1000)
        else:
            before_ts = int(before_time.timestamp())
        
        mask = df['transact_time'] <= before_ts
        filtered_df = df[mask]
        
        if filtered_df.empty:
            return None
        
        last_price = float(filtered_df.iloc[-1]['price'])
        return last_price
    
    def load(self, start: datetime, end: datetime, symbols: list) -> dict:
        """
        加载多个交易对的数据
        
        Args:
            start: 开始时间
            end: 结束时间
            symbols: 交易对列表
        
        Returns:
            字典，键为symbol，值为DataFrame
        """
        result = {}
        for symbol in symbols:
            result[symbol] = self.load_period(start, end, symbol)
        return result