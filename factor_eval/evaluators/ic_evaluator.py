"""
evaluators/ic_evaluator.py
IC (Information Coefficient) 评估器
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List


class ICEvaluator:
    """IC评估器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.eval_config = config['evaluation']
    
    def evaluate(self, factors_df: pd.DataFrame, returns_df: pd.DataFrame) -> Dict:
        """
        计算因子的IC指标
        
        Returns:
            包含所有因子IC结果的字典
        """
        results = {}
        
        for factor_name in factors_df.columns:
            factor_results = {}
            
            for return_name in returns_df.columns:
                # 计算IC
                ic_stats = self._calculate_ic(
                    factors_df[factor_name],
                    returns_df[return_name]
                )
                
                factor_results[return_name] = ic_stats
            
            results[factor_name] = factor_results
        
        return results
    
    def _calculate_ic(self, factor: pd.Series, returns: pd.Series) -> Dict:
        """
        计算单个因子和收益率之间的IC
        
        Returns:
            包含IC统计量的字典
        """
        # 对齐数据并去除NaN
        valid_mask = factor.notna() & returns.notna()
        factor_valid = factor[valid_mask]
        returns_valid = returns[valid_mask]
        
        if len(factor_valid) < 30:  # 数据点太少
            return self._empty_ic_stats()
        
        # Pearson IC
        pearson_ic, pearson_pval = stats.pearsonr(factor_valid, returns_valid)
        
        # Spearman IC (RankIC)
        spearman_ic, spearman_pval = stats.spearmanr(factor_valid, returns_valid)
        
        # 时间序列IC
        ic_series_pearson = self._rolling_ic(factor, returns, method='pearson')
        ic_series_spearman = self._rolling_ic(factor, returns, method='spearman')
        
        # IC统计量
        stats_dict = {
            'ic_mean_pearson': pearson_ic,
            'ic_std_pearson': ic_series_pearson.std(),
            'ic_ir_pearson': pearson_ic / (ic_series_pearson.std() + 1e-9),  # IC信息比率
            'ic_pval_pearson': pearson_pval,
            
            'ic_mean_spearman': spearman_ic,
            'ic_std_spearman': ic_series_spearman.std(),
            'ic_ir_spearman': spearman_ic / (ic_series_spearman.std() + 1e-9),
            'ic_pval_spearman': spearman_pval,
            
            'ic_positive_ratio': (ic_series_pearson > 0).mean(),  # IC>0的比例
            'ic_abs_mean': np.abs(ic_series_pearson).mean(),  # 绝对IC均值
            
            'valid_samples': len(factor_valid),
            'ic_series_pearson': ic_series_pearson,
            'ic_series_spearman': ic_series_spearman,
        }
        
        return stats_dict
    
    def _rolling_ic(self, factor: pd.Series, returns: pd.Series, 
                   method: str = 'pearson', window: int = 240) -> pd.Series:
        """
        计算滚动IC时间序列（优化版，避免逐窗口计算）
        
        Args:
            window: 滚动窗口大小（分钟）
            method: 'pearson' or 'spearman'
        """
        valid_mask = factor.notna() & returns.notna()
        factor_valid = factor[valid_mask]
        returns_valid = returns[valid_mask]
        
        if len(factor_valid) < window:
            return pd.Series(dtype=float)
        
        # 从配置读取步长因子
        stride_factor = self.eval_config.get('ic_rolling_stride', 4)
        stride = max(1, window // stride_factor)
        
        ic_values = []
        ic_indices = []
        
        for i in range(window, len(factor_valid), stride):
            window_factor = factor_valid.iloc[i-window:i]
            window_returns = returns_valid.iloc[i-window:i]
            
            if len(window_factor) >= 30:
                if method == 'pearson':
                    ic, _ = stats.pearsonr(window_factor, window_returns)
                else:  # spearman
                    ic, _ = stats.spearmanr(window_factor, window_returns)
                
                ic_values.append(ic)
                ic_indices.append(factor_valid.index[i-1])
        
        ic_series = pd.Series(ic_values, index=ic_indices)
        
        return ic_series
    
    def _empty_ic_stats(self) -> Dict:
        """返回空的IC统计结果"""
        return {
            'ic_mean_pearson': np.nan,
            'ic_std_pearson': np.nan,
            'ic_ir_pearson': np.nan,
            'ic_pval_pearson': np.nan,
            'ic_mean_spearman': np.nan,
            'ic_std_spearman': np.nan,
            'ic_ir_spearman': np.nan,
            'ic_pval_spearman': np.nan,
            'ic_positive_ratio': np.nan,
            'ic_abs_mean': np.nan,
            'valid_samples': 0,
            'ic_series_pearson': pd.Series(),
            'ic_series_spearman': pd.Series(),
        }