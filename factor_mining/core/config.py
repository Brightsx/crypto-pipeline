"""配置管理模块"""
import yaml
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List


class Config:
    """配置管理类"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self._config = self._load_config()
        self._setup_logging()
        
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            raise ValueError(f"Failed to load config from {self.config_path}: {e}")
    
    def _setup_logging(self):
        """设置日志配置"""
        log_config = self._config.get('logging', {})
        log_dir = Path(log_config.get('file', './logs/factor_mining.log')).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=getattr(logging, log_config.get('level', 'INFO')),
            format=log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            handlers=[
                logging.FileHandler(log_config.get('file', './logs/factor_mining.log')),
                logging.StreamHandler()
            ]
        )
    
    @property
    def data_config(self) -> Dict[str, Any]:
        """数据配置"""
        return self._config.get('data', {})
    
    @property
    def factor_config(self) -> Dict[str, Any]:
        """因子配置"""
        return self._config.get('factor', {})
    
    @property
    def performance_config(self) -> Dict[str, Any]:
        """性能配置"""
        return self._config.get('performance', {})
    
    @property
    def symbols(self) -> List[str]:
        """币种列表"""
        return self.data_config.get('symbols', [])
    
    @property
    def kline_windows(self) -> List[str]:
        """K线窗口期列表"""
        return self.data_config.get('kline_windows', [])
    
    @property
    def start_time(self) -> datetime:
        """开始时间"""
        dt = datetime.strptime(self.factor_config['start_time'], '%Y-%m-%d %H:%M:%S')
        return dt.replace(tzinfo=timezone.utc)

    @property
    def end_time(self) -> datetime:
        """结束时间"""
        dt = datetime.strptime(self.factor_config['end_time'], '%Y-%m-%d %H:%M:%S')
        return dt.replace(tzinfo=timezone.utc)
    
    @property
    def calc_frequency(self) -> str:
        """计算频率"""
        return self.factor_config.get('calc_frequency', '1m')
    
    @property
    def batch_days(self) -> int:
        """批处理天数"""
        return self.factor_config.get('batch_days', 7)
    
    @property
    def max_lookback_days(self) -> int:
        """最大回看天数"""
        return self.factor_config.get('max_lookback_days', 30)
    
    @property
    def output_path(self) -> Path:
        """输出路径"""
        path = Path(self.factor_config.get('output_path', './factor_results'))
        path.mkdir(parents=True, exist_ok=True)
        return path


# 全局配置实例
config = Config()