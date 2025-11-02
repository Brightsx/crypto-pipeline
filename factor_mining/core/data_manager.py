"""数据管理模块"""
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from concurrent.futures import ThreadPoolExecutor

from core.config import config
from core.utils import get_date_range, ms_to_datetime


logger = logging.getLogger(__name__)


class DataManager:
    """数据管理器，负责K线数据的加载和管理"""
    
    def __init__(self):
        self.data_root = Path(config.data_config['root_path'])
        self.file_pattern = config.data_config['file_pattern']
        self._cache = {}  # 简单的内存缓存
        
    def _build_file_path(self, symbol: str, window: str, date: str) -> Path:
        """构建数据文件路径"""
        filename = self.file_pattern.format(symbol=symbol, window=window, date=date)
        return self.data_root / symbol / f"aggTrades_kline_{window}" / filename
    
    def _load_single_file(self, file_path: Path) -> Optional[pd.DataFrame]:
        """加载单个parquet文件"""
        cache_key = str(file_path)
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return None
            
        try:
            df = pd.read_parquet(file_path)
            
            if not df.empty:
                # 统一时间列处理，确保都是UTC时区
                for time_col in ['start_time', 'end_time']:
                    if time_col in df.columns:
                        if pd.api.types.is_datetime64_any_dtype(df[time_col]):
                            if df[time_col].dt.tz is None:
                                df[time_col] = df[time_col].dt.tz_localize('UTC')
                            else:
                                df[time_col] = df[time_col].dt.tz_convert('UTC')
                        else:
                            df[time_col] = pd.to_datetime(df[time_col], unit='ms', utc=True)
                
                # 按end_time排序
                if 'end_time' in df.columns:
                    df = df.sort_values('end_time')
            
            self._cache[cache_key] = df
            logger.debug(f"Loaded {len(df)} rows from {file_path}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
            return None
    
    def load_kline_data(self, symbol: str, window: str, start_date: str, 
                       end_date: str, include_lookback: bool = True) -> pd.DataFrame:
        """
        加载指定时间范围的K线数据
        
        Args:
            symbol: 币种符号
            window: K线窗口
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            include_lookback: 是否包含回看数据
            
        Returns:
            合并后的K线数据
        """
        # 计算实际需要的日期范围
        actual_start = start_date
        if include_lookback:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            lookback_start = start_dt - timedelta(days=config.max_lookback_days)
            actual_start = lookback_start.strftime('%Y-%m-%d')
        
        date_list = get_date_range(
            datetime.strptime(actual_start, '%Y-%m-%d'),
            datetime.strptime(end_date, '%Y-%m-%d')
        )
        
        logger.info(f"Loading {symbol} {window} data from {actual_start} to {end_date} "
                   f"({len(date_list)} days)")
        
        # 并行加载文件
        data_frames = []
        
        def load_file(date):
            file_path = self._build_file_path(symbol, window, date)
            return self._load_single_file(file_path)
        
        # 使用线程池并行加载
        max_workers = min(len(date_list), config.performance_config.get('n_jobs', 4) or 4)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(load_file, date_list))
        
        # 合并非空结果
        for df in results:
            if df is not None and not df.empty:
                data_frames.append(df)
        
        if not data_frames:
            logger.warning(f"No data found for {symbol} {window}")
            return pd.DataFrame()
        
        # 合并所有数据
        combined_df = pd.concat(data_frames, ignore_index=True)
        
        # 最终排序和去重
        if 'end_time' in combined_df.columns:
            combined_df = combined_df.sort_values('end_time').drop_duplicates(
                subset=['end_time'], keep='last'
            )
        
        logger.info(f"Loaded {len(combined_df)} records for {symbol} {window}")
        return combined_df
    
    def get_batch_date_ranges(self, start_time: datetime, end_time: datetime) -> List[tuple]:
        """
        获取批处理的日期范围列表
        
        Args:
            start_time: 整体开始时间
            end_time: 整体结束时间
            
        Returns:
            (batch_start, batch_end) 元组列表
        """
        batch_ranges = []
        current_start = start_time
        batch_days = config.batch_days
        
        while current_start < end_time:
            batch_end = min(
                current_start + timedelta(days=batch_days - 1, hours=23, minutes=59, seconds=59),
                end_time
            )
            batch_ranges.append((current_start, batch_end))
            current_start = batch_end + timedelta(seconds=1)
            current_start = current_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        return batch_ranges
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        logger.info("Data cache cleared")
    
    def get_cache_info(self) -> Dict:
        """获取缓存信息"""
        return {
            'cached_files': len(self._cache),
            'cache_keys': list(self._cache.keys())
        }