"""资金费率数据加载器"""
from datetime import datetime
import pandas as pd
import logging
from pathlib import Path
from .base_loader import LargeFileLoader
from utils.time_utils import find_nearest_timestamp

logger = logging.getLogger(__name__)


class FundingRateLoader(LargeFileLoader):
    """资金费率数据加载器，按月加载数据"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.path_template = config.get('path_template')
        if not self.path_template:
            raise ValueError("FundingRateLoader需要配置path_template")
    
    def load_period(self, start: datetime, end: datetime, symbol: str) -> pd.DataFrame:
        """
        加载指定时间段的资金费率数据
        
        Args:
            start: 开始时间(UTC)
            end: 结束时间(UTC)
            symbol: 交易对，如 BTCUSDT
        
        Returns:
            DataFrame包含资金费率数据
        """
        cache_key = f"{symbol}_{start.year}-{start.month}_{end.year}-{end.month}"
        
        # 检查缓存
        if cache_key in self.cache:
            df = self.cache[cache_key]
            logger.debug(f"从缓存加载 {symbol} 资金费率数据")
            return self._filter_by_time(df, start, end)
        
        # 加载数据
        all_data = []
        current_month = start.replace(day=1)
        end_month = end.replace(day=1)
        
        while current_month <= end_month:
            file_path = self._get_file_path(symbol, current_month)
            
            if Path(file_path).exists():
                try:
                    df = pd.read_parquet(file_path)
                    all_data.append(df)
                    logger.debug(f"加载文件: {file_path}, 行数: {len(df)}")
                except Exception as e:
                    logger.warning(f"加载文件失败 {file_path}: {e}")
            else:
                logger.warning(f"文件不存在: {file_path}")
            
            # 移动到下个月
            if current_month.month == 12:
                current_month = current_month.replace(year=current_month.year + 1, month=1)
            else:
                current_month = current_month.replace(month=current_month.month + 1)
        
        if not all_data:
            logger.warning(f"未找到 {symbol} 的资金费率数据")
            return pd.DataFrame()
        
        # 合并数据
        df = pd.concat(all_data, ignore_index=True)
        df = df.sort_values('calc_time').reset_index(drop=True)
        
        # 缓存数据
        self.cache[cache_key] = df
        logger.info(f"加载 {symbol} 资金费率数据: {len(df)} 行")
        
        return self._filter_by_time(df, start, end)
    
    def _get_file_path(self, symbol: str, date: datetime) -> str:
        """构造文件路径"""
        return self.path_template.format(
            symbol=symbol,
            YYYY=date.year,
            MM=f"{date.month:02d}"
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
        
        mask = (df['calc_time'] >= start_ts) & (df['calc_time'] <= end_ts)
        return df[mask].copy()
    
    def get_funding_events(self, df: pd.DataFrame, symbols: list) -> list:
        """
        获取所有资金费率结算事件
        
        Args:
            df: 资金费率数据
            symbols: 交易对列表
        
        Returns:
            列表，每个元素为(calc_time, symbol, funding_rate)
        """
        events = []
        
        for symbol in symbols:
            symbol_df = df[df.index.isin(df.index)]  # 这里需要根据实际数据结构调整
            
            if not symbol_df.empty:
                for _, row in symbol_df.iterrows():
                    events.append((
                        int(row['calc_time']),
                        symbol,
                        float(row['last_funding_rate'])
                    ))
        
        # 按时间排序
        events.sort(key=lambda x: x[0])
        return events
    
    def load(self, start: datetime, end: datetime, symbols: list) -> dict:
        """
        加载多个交易对的资金费率数据
        
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