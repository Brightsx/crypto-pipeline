
"""时间处理工具模块"""
from datetime import datetime, timezone, timedelta
from typing import Iterator, Iterable, Union


def parse_frequency(freq_str: str) -> timedelta:
    """将频率字符串解析为 :class:`datetime.timedelta`.

    支持:
    - "30s" 秒
    - "1min", "15min" 分钟
    - "1h" 小时
    - "1d" 天
    """
    freq_str = freq_str.lower().strip()
    if not freq_str:
        raise ValueError("频率字符串不能为空")

    if freq_str.endswith("min"):
        return timedelta(minutes=int(freq_str[:-3]))
    if freq_str.endswith("h"):
        return timedelta(hours=int(freq_str[:-1]))
    if freq_str.endswith("d"):
        return timedelta(days=int(freq_str[:-1]))
    if freq_str.endswith("s"):
        return timedelta(seconds=int(freq_str[:-1]))

    raise ValueError(f"无法解析频率字符串: {freq_str}")


def timestamp_to_datetime(timestamp: Union[int, float], unit: str = "ms") -> datetime:
    """将时间戳转换为 UTC :class:`datetime`."""
    if unit == "ms":
        timestamp = timestamp / 1000.0
    elif unit != "s":
        raise ValueError(f"不支持的时间单位: {unit}")
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def datetime_to_timestamp(dt: datetime, unit: str = "ms") -> int:
    """将 :class:`datetime` 转为整数时间戳。"""
    ts = dt.timestamp()
    if unit == "ms":
        return int(ts * 1000)
    if unit == "s":
        return int(ts)
    raise ValueError(f"不支持的时间单位: {unit}")


def parse_datetime_str(dt_str: str) -> datetime:
    """解析 'YYYY-MM-DD HH:MM:SS' 为 UTC datetime."""
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=timezone.utc)


def generate_time_range(start: datetime, end: datetime, freq: timedelta) -> Iterator[datetime]:
    """生成 [start, end] 间隔为 freq 的时间点(包含两端)。"""
    current = start
    while current <= end:
        yield current
        current += freq


def find_nearest_timestamp(target: int, timestamps: Iterable[int], allow_future: bool = False):
    """在有序时间戳列表中找到最接近目标的时间戳。

    :param target: 目标时间戳
    :param timestamps: 递增有序的时间戳序列
    :param allow_future: False 时只返回 <= target 的时间戳
    :returns: 最接近的时间戳或 None
    """
    ts_list = list(timestamps)
    if not ts_list:
        return None

    left, right = 0, len(ts_list) - 1

    if target < ts_list[0]:
        return ts_list[0] if allow_future else None
    if target > ts_list[-1]:
        return ts_list[-1]

    while left <= right:
        mid = (left + right) // 2
        if ts_list[mid] == target:
            return ts_list[mid]
        if ts_list[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    if allow_future and left < len(ts_list):
        if abs(ts_list[left] - target) < abs(ts_list[right] - target):
            return ts_list[left]
    return ts_list[right]
