# src/time_utils.py - 时间工具类
import pandas as pd
import pytz
from datetime import datetime, timedelta
from typing import List
import logging

class TimeUtils:
    """时间工具类"""
    
    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
    def generate_time_points(self) -> pd.DatetimeIndex:
        """生成计算时间点数组"""
        start_time = pd.to_datetime(self.config['time']['start_time'], utc=True)
        end_time = pd.to_datetime(self.config['time']['end_time'], utc=True)
        interval = self.config['time']['interval']
        
        # 将自定义格式转换为pandas频率字符串
        freq_str = self._convert_to_pandas_freq(interval)
        self.logger.info(f"转换频率字符串: {interval} -> {freq_str}")
        
        # 生成时间序列
        time_points = pd.date_range(
            start=start_time,
            end=end_time,
            freq=freq_str,
            tz='UTC'
        )
        
        self.logger.info(f"生成时间点: {start_time} 到 {end_time}, 间隔: {interval}")
        self.logger.info(f"实际生成时间点数量: {len(time_points)}")
        return time_points
    
    def parse_interval_to_seconds(self, interval: str) -> int:
        """解析时间间隔为秒数"""
        if interval.endswith('d'):
            return int(interval[:-1]) * 86400
        elif interval.endswith('h'):
            return int(interval[:-1]) * 3600
        elif interval.endswith('m'):
            return int(interval[:-1]) * 60
        elif interval.endswith('s'):
            return int(interval[:-1])
        else:
            raise ValueError(f"不支持的时间间隔格式: {interval}")
    
    def _convert_to_pandas_freq(self, interval: str) -> str:
        """将自定义时间间隔格式转换为pandas频率字符串"""
        if interval.endswith('s'):
            return f"{interval[:-1]}s"   # 秒 (小写s)
        elif interval.endswith('m'):
            return f"{interval[:-1]}min" # 分钟
        elif interval.endswith('h'):
            return f"{interval[:-1]}h"   # 小时 (小写h)
        elif interval.endswith('d'):
            return f"{interval[:-1]}D"   # 天 (大写D)
        else:
            raise ValueError(f"不支持的时间间隔格式: {interval}")
    
    def get_required_data_range(self, time_points: pd.DatetimeIndex) -> tuple:
        """
        计算所需的数据时间范围
        考虑最大延迟和最大收益率周期
        """
        max_delay = max([
            self.parse_interval_to_seconds(delay) 
            for delay in self.config['returns']['delays']
        ])
        max_period_seconds = max([
            self.parse_interval_to_seconds(period) 
            for period in self.config['returns']['periods']
        ])
        
        # 数据开始时间：最早时间点
        data_start = time_points.min()
        
        # 数据结束时间：最晚时间点 + 最大延迟 + 最大周期
        extra_seconds = max_delay + max_period_seconds
        data_end = time_points.max() + timedelta(seconds=extra_seconds)
        
        self.logger.info(f"所需数据范围: {data_start} 到 {data_end}")
        return data_start, data_end
    
    def get_batch_ranges(self, time_points: pd.DatetimeIndex) -> List[tuple]:
        """
        生成批次处理范围
        返回[(batch_start, batch_end, data_start, data_end), ...]
        """
        batch_days = self.config['performance']['batch_days']
        buffer_days = self.config['performance']['buffer_days']
        
        batches = []
        current_start = time_points.min()
        
        while current_start <= time_points.max():
            # 批次结束时间
            batch_end = min(
                current_start + timedelta(days=batch_days),
                time_points.max()
            )
            
            # 数据范围（包含缓冲）
            data_start = current_start
            data_end = batch_end + timedelta(days=buffer_days)
            
            batches.append((current_start, batch_end, data_start, data_end))
            current_start = batch_end + timedelta(microseconds=1)
        
        self.logger.info(f"生成 {len(batches)} 个批次")
        return batches
    
    def timestamp_to_date_str(self, timestamp: pd.Timestamp) -> str:
        """时间戳转为日期字符串格式(YYYY-MM-DD)"""
        return timestamp.strftime('%Y-%m-%d')