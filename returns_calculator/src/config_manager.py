import yaml
from pathlib import Path
import logging

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._validate_config()
        
    def _load_config(self) -> dict:
        """加载配置文件"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
            
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _validate_config(self):
        """验证配置文件"""
        required_keys = ['data', 'time', 'returns', 'performance', 'output', 'symbols']
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"配置文件缺少必要字段: {key}")
        
        # 验证延迟是否为K线窗口的倍数
        kline_interval_sec = self._parse_interval_to_seconds(self.config['data']['kline_interval'])
        for delay in self.config['returns']['delays']:
            delay_sec = self._parse_interval_to_seconds(delay)
            if delay_sec % kline_interval_sec != 0:
                raise ValueError(f"延迟 {delay} 必须是K线窗口 {kline_interval_sec}s 的倍数")
    
    def _parse_interval_to_seconds(self, interval: str) -> int:
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
    
    def get_config(self) -> dict:
        """获取配置"""
        return self.config