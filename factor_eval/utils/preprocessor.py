"""
utils/preprocessor.py
数据预处理模块
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Tuple


class Preprocessor:
    """数据预处理器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.process_config = config['data_processing']
    
    def preprocess(self, factors_df: pd.DataFrame, returns_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        预处理因子和收益率数据
        
        Args:
            factors_df: 因子数据
            returns_df: 收益率数据
            
        Returns:
            预处理后的 (factors_df, returns_df)
        """
        print("   🔧 开始预处理...")
        
        # 1. 删除全部为NaN的列
        orig_factor_cols = len(factors_df.columns)
        factors_df = factors_df.dropna(axis=1, how='all')
        returns_df = returns_df.dropna(axis=1, how='all')
        if len(factors_df.columns) < orig_factor_cols:
            print(f"   ↳ 移除全NaN因子: {orig_factor_cols - len(factors_df.columns)} 个")
        
        # 2. 删除有效数据比例过低的因子
        min_valid_ratio = self.process_config['min_valid_ratio']
        valid_mask = factors_df.notna().mean() >= min_valid_ratio
        removed_factors = factors_df.columns[~valid_mask].tolist()
        if removed_factors:
            print(f"   ↳ 移除有效率不足因子: {len(removed_factors)} 个")
            if len(removed_factors) <= 5:
                print(f"      {removed_factors}")
        factors_df = factors_df.loc[:, valid_mask]
        
        # 3. 缩尾处理
        if self.process_config['winsorize']:
            print(f"   ↳ 缩尾处理: {self.process_config['winsorize_limits']}")
            factors_df = self._winsorize(factors_df)
        
        # 4. 标准化
        if self.process_config['normalize_factors']:
            print(f"   ↳ 标准化方法: {self.process_config['normalize_method']}")
            factors_df = self._normalize(factors_df)
        
        # 5. 删除inf和-inf
        inf_count = np.isinf(factors_df.values).sum() + np.isinf(returns_df.values).sum()
        if inf_count > 0:
            print(f"   ↳ 移除inf值: {inf_count} 个")
        factors_df = factors_df.replace([np.inf, -np.inf], np.nan)
        returns_df = returns_df.replace([np.inf, -np.inf], np.nan)
        
        print("   ✅ 预处理完成")
        
        return factors_df, returns_df
    
    def _winsorize(self, df: pd.DataFrame) -> pd.DataFrame:
        """缩尾处理"""
        limits = self.process_config['winsorize_limits']
        
        for col in df.columns:
            if df[col].dtype in [np.float64, np.float32, np.int64, np.int32]:
                lower = df[col].quantile(limits[0])
                upper = df[col].quantile(limits[1])
                df[col] = df[col].clip(lower=lower, upper=upper)
        
        return df
    
    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化因子"""
        method = self.process_config['normalize_method']
        
        if method == 'zscore':
            # Z-score标准化
            return (df - df.mean()) / df.std()
        elif method == 'minmax':
            # Min-Max归一化
            return (df - df.min()) / (df.max() - df.min())
        else:
            return df