# -*- coding: utf-8 -*-
import yaml
from dataclasses import dataclass
from typing import List

@dataclass
class DataConfig:
    base_path: str
    kline_window: str
    price_column: str

@dataclass
class TimeRange:
    start_time: str
    end_time: str
    interval: str

@dataclass
class ReturnsConfig:
    delays: List[str]
    periods: List[str]

@dataclass
class BatchConfig:
    batch_days: int
    margin_days: int

@dataclass
class OutputConfig:
    dir: str
    filename_pattern: str

@dataclass
class AppConfig:
    symbols: List[str]
    data: DataConfig
    time_range: TimeRange
    returns: ReturnsConfig
    batch: BatchConfig
    output: OutputConfig

def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return AppConfig(
        symbols=cfg["symbols"],
        data=DataConfig(**cfg["data"]),
        time_range=TimeRange(**cfg["time_range"]),
        returns=ReturnsConfig(**cfg["returns"]),
        batch=BatchConfig(**cfg["batch"]),
        output=OutputConfig(**cfg["output"]),
    )
