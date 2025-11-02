"""时间处理工具模块"""
from datetime import datetime, timezone, timedelta
import pandas as pd
from typing import Union


def parse_frequency(freq_str: str) -> timedelta:
    """
    解析频率字符串为timedelta对象
    
    Args:
        freq_str: 频率字符串，如 "30s", "1min", "15min", "1h"
    
    Returns:
        timedelta对象
    """
    freq_str = freq_str.lower().strip()
    
    if freq_str.endswith('s'):
        return timedelta(seconds=int(freq_str[:-1]))
    elif freq_str.endswith('min'):
        return timedelta(minutes=int(freq_str[:-3]))
    elif freq_str.endswith('h'):
        return timedelta(hours=int(freq_str[:-1]))
    elif freq_str.endswith('d'):
        return timedelta(days=int(freq_str[:-1]))
    else:
        raise ValueError(f"无法解析频率字符串: {freq_str}")


def timestamp_to_datetime(timestamp: Union[int, float], unit: str = 'ms') -> datetime:
    """
    将时间戳转换为UTC datetime对象
    
    Args:
        timestamp: 时间戳
        unit: 时间单位 's'(秒) 或 'ms'(毫秒)
    
    Returns:
        UTC datetime对象
    """
    if unit == 'ms':
        timestamp = timestamp / 1000.0
    elif unit != 's':
        raise ValueError(f"不支持的时间单位: {unit}")
    
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def datetime_to_timestamp(dt: datetime, unit: str = 'ms') -> int:
    """
    将datetime对象转换为时间戳
    
    Args:
        dt: datetime对象
        unit: 时间单位 's'(秒) 或 'ms'(毫秒)
    
    Returns:
        时间戳
    """
    timestamp = dt.timestamp()
    
    if unit == 'ms':
        return int(timestamp * 1000)
    elif unit == 's':
        return int(timestamp)
    else:
        raise ValueError(f"不支持的时间单位: {unit}")


def parse_datetime_str(dt_str: str) -> datetime:
    """
    解析日期时间字符串为UTC datetime对象
    
    Args:
        dt_str: 日期时间字符串，格式 "YYYY-MM-DD HH:MM:SS"
    
    Returns:
        UTC datetime对象
    """
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=timezone.utc)


def generate_time_range(start: datetime, end: datetime, freq: timedelta):
    """
    生成时间范围
    
    Args:
        start: 开始时间
        end: 结束时间
        freq: 频率
    
    Yields:
        datetime对象
    """
    current = start
    while current <= end:
        yield current
        current += freq


def find_nearest_timestamp(target: int, timestamps: list, allow_future: bool = False) -> int:
    """
    在时间戳列表中找到最接近目标时间的时间戳
    
    Args:
        target: 目标时间戳
        timestamps: 时间戳列表(已排序)
        allow_future: 是否允许返回未来时间戳
    
    Returns:
        最接近的时间戳，如果没有合适的返回None
    """
    if not timestamps:
        return None
    
    # 二分查找
    left, right = 0, len(timestamps) - 1
    
    # 如果目标时间早于所有时间戳
    if target < timestamps[0]:
        return timestamps[0] if allow_future else None
    
    # 如果目标时间晚于所有时间戳
    if target > timestamps[-1]:
        return timestamps[-1]
    
    while left <= right:
        mid = (left + right) // 2
        
        if timestamps[mid] == target:
            return timestamps[mid]
        elif timestamps[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    
    # 此时 right < left，timestamps[right] < target < timestamps[left]
    if allow_future:
        # 返回更接近的那个
        if left < len(timestamps):
            if abs(timestamps[left] - target) < abs(timestamps[right] - target):
                return timestamps[left]
        return timestamps[right]
    else:
        # 只返回过去的时间戳
        return timestamps[right]