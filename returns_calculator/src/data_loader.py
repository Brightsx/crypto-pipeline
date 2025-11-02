# src/data_loader.py - 数据加载器
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import logging
from typing import Optional

class KlineDataLoader:
    """K线数据加载器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.base_path = Path(config['data']['base_path'])
        self.kline_interval = config['data']['kline_interval']
        
        # 缓存最近加载的数据
        self._cached_data = None
        self._cached_symbol = None
        self._cached_date_range = None
    
    def load_kline_data(self, symbol: str, start_date: pd.Timestamp, 
                       end_date: pd.Timestamp) -> pd.DataFrame:
        """
        加载指定时间范围的K线数据
        
        Args:
            symbol: 交易对符号
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            K线数据DataFrame
        """
        # 检查缓存
        if (self._cached_data is not None and 
            self._cached_symbol == symbol and
            self._cached_date_range and
            start_date >= self._cached_date_range[0] and 
            end_date <= self._cached_date_range[1]):
            
            self.logger.debug(f"使用缓存数据 {symbol}")
            return self._filter_data_by_time(self._cached_data, start_date, end_date)
        
        self.logger.info(f"加载K线数据 {symbol}: {start_date.date()} 到 {end_date.date()}")
        
        # 构建数据路径
        data_path = self.base_path / symbol / f"aggTrades_kline_{self.kline_interval}"
        
        if not data_path.exists():
            raise FileNotFoundError(f"数据路径不存在: {data_path}")
        
        # 生成需要的日期列表
        date_range = pd.date_range(start_date.date(), end_date.date(), freq='D')
        
        # 加载数据文件
        dataframes = []
        for date in date_range:
            date_str = date.strftime('%Y-%m-%d')
            filename = f"{symbol}-kline-{self.kline_interval}-{date_str}.parquet"
            filepath = data_path / filename
            
            if filepath.exists():
                try:
                    df = pd.read_parquet(filepath)
                    if not df.empty:
                        dataframes.append(df)
                        self.logger.debug(f"加载文件: {filename}, 数据量: {len(df)}")
                except Exception as e:
                    self.logger.warning(f"加载文件失败 {filename}: {str(e)}")
            else:
                self.logger.warning(f"文件不存在: {filename}")
        
        if not dataframes:
            self.logger.warning(f"未找到有效数据文件 {symbol}")
            return pd.DataFrame()
        
        # 合并数据
        combined_df = pd.concat(dataframes, ignore_index=True)
        
        # 转换时间戳
        combined_df = self._process_timestamps(combined_df)
        
        # 排序并去重
        combined_df = combined_df.sort_values('timestamp').drop_duplicates(subset=['timestamp'])
        combined_df = combined_df.set_index('timestamp')
        
        # 缓存数据
        self._cached_data = combined_df
        self._cached_symbol = symbol
        self._cached_date_range = (start_date, end_date)
        
        self.logger.info(f"成功加载 {len(combined_df)} 条K线数据")
        
        # 筛选时间范围
        return self._filter_data_by_time(combined_df, start_date, end_date)
    
    def _process_timestamps(self, df: pd.DataFrame) -> pd.DataFrame:
        """处理时间戳列"""
        # 使用start_time作为时间戳
        df['timestamp'] = pd.to_datetime(df['start_time'], unit='ms', utc=True)
        return df
    
    def _filter_data_by_time(self, df: pd.DataFrame, start_date: pd.Timestamp, 
                            end_date: pd.Timestamp) -> pd.DataFrame:
        """按时间范围筛选数据"""
        if df.empty:
            return df
            
        mask = (df.index >= start_date) & (df.index <= end_date)
        filtered_df = df[mask].copy()
        
        self.logger.debug(f"筛选后数据量: {len(filtered_df)}")
        return filtered_df
    
    def clear_cache(self):
        """清空缓存"""
        self._cached_data = None
        self._cached_symbol = None
        self._cached_date_range = None
        self.logger.debug("清空数据缓存")