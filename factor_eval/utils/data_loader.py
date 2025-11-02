"""
utils/data_loader.py
数据加载模块
"""

import pandas as pd
from pathlib import Path
from typing import Tuple, Optional


class DataLoader:
    """数据加载器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.paths = config['paths']
    
    def load_data(self, symbol: str) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """
        加载因子和收益率数据
        
        Args:
            symbol: 合约名称
            
        Returns:
            (factors_df, returns_df) 元组
        """
        try:
            # 构建文件路径
            factors_path = Path(self.paths['factors_dir']) / \
                          self.paths['factors_template'].format(symbol=symbol)
            returns_path = Path(self.paths['returns_dir']) / \
                          self.paths['returns_template'].format(symbol=symbol)
            
            # 加载数据
            factors_df = pd.read_parquet(factors_path)
            returns_df = pd.read_parquet(returns_path)
            
            # 确保索引为DatetimeIndex
            if not isinstance(factors_df.index, pd.DatetimeIndex):
                factors_df.index = pd.to_datetime(factors_df.index)
            if not isinstance(returns_df.index, pd.DatetimeIndex):
                returns_df.index = pd.to_datetime(returns_df.index)
            
            # 对齐数据
            common_index = factors_df.index.intersection(returns_df.index)
            factors_df = factors_df.loc[common_index]
            returns_df = returns_df.loc[common_index]
            
            print(f"   成功加载 {symbol}: {len(factors_df)} 行数据")
            print(f"   因子数量: {len(factors_df.columns)}, 收益率周期: {len(returns_df.columns)}")
            
            return factors_df, returns_df
            
        except FileNotFoundError as e:
            print(f"   错误: 文件未找到 - {e}")
            return None, None
        except Exception as e:
            print(f"   错误: 加载数据失败 - {e}")
            return None, None