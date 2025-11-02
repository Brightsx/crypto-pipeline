"""工具函数模块"""
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Tuple


def parse_frequency(freq_str: str) -> Tuple[int, str]:
    """
    解析频率字符串，返回数值和单位
    
    Args:
        freq_str: 频率字符串，如 "1m", "5m", "1h", "3s"
        
    Returns:
        (数值, 单位) 元组
    """
    import re
    match = re.match(r'(\d+)([smhd])', freq_str.lower())
    if not match:
        raise ValueError(f"Invalid frequency format: {freq_str}")
    return int(match.group(1)), match.group(2)


def frequency_to_seconds(freq_str: str) -> int:
    """将频率字符串转换为秒数"""
    num, unit = parse_frequency(freq_str)
    unit_seconds = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    return num * unit_seconds[unit]


def frequency_to_pandas_freq(freq_str: str) -> str:
    """将自定义频率转换为pandas频率字符串"""
    num, unit = parse_frequency(freq_str)
    unit_map = {'s': 'S', 'm': 'min', 'h': 'H', 'd': 'D'}
    return f"{num}{unit_map[unit]}"


def generate_time_points(start_time: datetime, end_time: datetime, frequency: str) -> pd.DatetimeIndex:
    """生成等距时间点序列"""
    pandas_freq = frequency_to_pandas_freq(frequency)
    time_points = pd.date_range(start=start_time, end=end_time, freq=pandas_freq)
    
    # 确保时区为UTC
    if time_points.tz is None:
        time_points = time_points.tz_localize('UTC')
    
    return time_points


def get_date_range(start_time: datetime, end_time: datetime) -> List[str]:
    """
    获取日期范围内的所有日期字符串
    
    Args:
        start_time: 开始时间
        end_time: 结束时间
        
    Returns:
        日期字符串列表，格式为 YYYY-MM-DD
    """
    dates = []
    current = start_time.date()
    end_date = end_time.date()
    
    while current <= end_date:
        dates.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)
    
    return dates


def align_data_to_timepoints(df: pd.DataFrame, target_times: pd.DatetimeIndex, 
                           time_col: str = 'end_time') -> pd.DataFrame:
    """
    将数据对齐到目标时间点
    """
    if df.empty:
        result = pd.DataFrame(index=target_times)
        result.index.name = 'timestamp'
        return result
    
    # 确保时间列是datetime类型
    if time_col in df.columns:
        df = df.copy()
        # 统一时区处理
        if pd.api.types.is_datetime64_any_dtype(df[time_col]):
            if df[time_col].dt.tz is None:
                df[time_col] = df[time_col].dt.tz_localize('UTC')
            else:
                df[time_col] = df[time_col].dt.tz_convert('UTC')
        else:
            df[time_col] = pd.to_datetime(df[time_col], unit='ms', utc=True)
        
        df.set_index(time_col, inplace=True)
    
    # 确保target_times也有时区
    if target_times.tz is None:
        target_times = target_times.tz_localize('UTC')
    
    # 对齐到目标时间点
    result = df.reindex(target_times, method='ffill')
    result.index.name = 'timestamp'
    
    return result


def merge_batch_results(batch_results: List[pd.DataFrame]) -> pd.DataFrame:
    """
    合并批次结果
    
    Args:
        batch_results: 批次结果列表
        
    Returns:
        合并后的DataFrame
    """
    if not batch_results:
        return pd.DataFrame()
    
    # 过滤空结果
    valid_results = [df for df in batch_results if not df.empty]
    
    if not valid_results:
        return pd.DataFrame()
    
    # 按时间戳合并，去重
    merged = pd.concat(valid_results, axis=0).sort_index()
    
    # 去除重复的时间戳（保留最后一个）
    return merged[~merged.index.duplicated(keep='last')]


def ms_to_datetime(ms_timestamp):
    """毫秒时间戳转datetime"""
    if pd.isna(ms_timestamp):
        return pd.NaT
    return pd.to_datetime(ms_timestamp, unit='ms', utc=True)