# main.py - 主程序入口
import logging
import sys
from pathlib import Path
import yaml
import pandas as pd
from datetime import datetime, timedelta
import pytz

from src.data_loader import KlineDataLoader
from src.returns_calculator import ReturnsCalculator
from src.time_utils import TimeUtils
from src.config_manager import ConfigManager

def setup_logging(config):
    """设置日志配置"""
    logging.basicConfig(
        level=getattr(logging, config['logging']['level']),
        format=config['logging']['format'],
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('returns_calculation.log')
        ]
    )

def main():
    """主程序入口"""
    logger = logging.getLogger(__name__)
    
    try:
        # 加载配置
        config_manager = ConfigManager('config.yaml')
        config = config_manager.get_config()
        
        # 设置日志
        setup_logging(config)
        logger.info("开始币安合约收益率计算")
        
        # 初始化组件
        time_utils = TimeUtils(config)
        data_loader = KlineDataLoader(config)
        calculator = ReturnsCalculator(config)
        
        # 生成计算时间点
        time_points = time_utils.generate_time_points()
        logger.info(f"生成 {len(time_points)} 个计算时间点")
        
        # 处理每个交易对
        for symbol in config['symbols']:
            logger.info(f"开始处理交易对: {symbol}")
            
            # 分批计算收益率
            results = calculator.calculate_returns_batch(
                symbol=symbol,
                time_points=time_points,
                data_loader=data_loader
            )
            
            # 保存结果
            output_path = Path(config['output']['base_path'])
            output_path.mkdir(parents=True, exist_ok=True)
            
            filename = f"{symbol}{config['output']['file_suffix']}"
            filepath = output_path / filename
            
            results.to_parquet(filepath)
            logger.info(f"保存结果到: {filepath}")
            
        logger.info("计算完成!")
        
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}")
        raise

if __name__ == "__main__":
    main()

