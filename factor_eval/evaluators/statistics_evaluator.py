"""
evaluators/statistics_evaluator.py
统计特性评估器
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict


class StatisticsEvaluator:
    """统计特性评估器"""
    
    def __init__(self, config: dict):
        self.config = config
    
    def evaluate(self, factors_df: pd.DataFrame, returns_df: pd.DataFrame) -> Dict:
        """
        分析因子的统计特性
        
        Returns:
            包含所有因子统计特性的字典
        """
        results = {}
        
        for factor_name in factors_df.columns:
            stats_dict = self._calculate_statistics(factors_df[factor_name])
            results[factor_name] = stats_dict
        
        return results
    
    def _calculate_statistics(self, factor: pd.Series) -> Dict:
        """
        计算单个因子的统计特性
        """
        factor_valid = factor.dropna()
        
        if len(factor_valid) < 30:
            return self._empty_stats()
        
        # 基础统计量
        stats_dict = {
            'mean': factor_valid.mean(),
            'std': factor_valid.std(),
            'min': factor_valid.min(),
            'max': factor_valid.max(),
            'median': factor_valid.median(),
            
            # 分位数
            'q25': factor_valid.quantile(0.25),
            'q75': factor_valid.quantile(0.75),
            
            # 偏度和峰度
            'skewness': stats.skew(factor_valid),
            'kurtosis': stats.kurtosis(factor_valid),
            
            # 缺失率
            'missing_ratio': factor.isna().mean(),
            
            # 唯一值数量
            'n_unique': factor_valid.nunique(),
            'unique_ratio': factor_valid.nunique() / len(factor_valid),
            
            # 自相关性
            'autocorr_1': factor_valid.autocorr(lag=1),
            'autocorr_5': factor_valid.autocorr(lag=5),
            'autocorr_60': factor_valid.autocorr(lag=60),
            
            # 正态性检验
            'normality_pval': stats.normaltest(factor_valid)[1] if len(factor_valid) >= 20 else np.nan,
            
            # 稳定性 (滚动标准差的标准差)
            'stability': factor_valid.rolling(window=60).std().std(),
        }
        
        # 换手率分析（因子值变化频率）
        factor_change = (factor_valid.diff().abs() > 0).mean()
        stats_dict['turnover_rate'] = factor_change
        
        # 极值占比
        q01 = factor_valid.quantile(0.01)
        q99 = factor_valid.quantile(0.99)
        extreme_ratio = ((factor_valid <= q01) | (factor_valid >= q99)).mean()
        stats_dict['extreme_ratio'] = extreme_ratio
        
        return stats_dict
    
    def _empty_stats(self) -> Dict:
        """返回空的统计结果"""
        return {
            'mean': np.nan,
            'std': np.nan,
            'min': np.nan,
            'max': np.nan,
            'median': np.nan,
            'q25': np.nan,
            'q75': np.nan,
            'skewness': np.nan,
            'kurtosis': np.nan,
            'missing_ratio': np.nan,
            'n_unique': np.nan,
            'unique_ratio': np.nan,
            'autocorr_1': np.nan,
            'autocorr_5': np.nan,
            'autocorr_60': np.nan,
            'normality_pval': np.nan,
            'stability': np.nan,
            'turnover_rate': np.nan,
            'extreme_ratio': np.nan,
        }