"""
evaluators/quantile_evaluator.py
分组回测评估器
"""

import pandas as pd
import numpy as np
from typing import Dict


class QuantileEvaluator:
    """分组回测评估器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.eval_config = config['evaluation']
        self.n_groups = self.eval_config['quantile_groups']
    
    def evaluate(self, factors_df: pd.DataFrame, returns_df: pd.DataFrame) -> Dict:
        """
        对因子进行分组回测分析
        
        Returns:
            包含所有因子分组结果的字典
        """
        results = {}
        
        for factor_name in factors_df.columns:
            factor_results = {}
            
            for return_name in returns_df.columns:
                # 进行分组回测
                quantile_stats = self._quantile_analysis(
                    factors_df[factor_name],
                    returns_df[return_name]
                )
                
                factor_results[return_name] = quantile_stats
            
            results[factor_name] = factor_results
        
        return results
    
    def _quantile_analysis(self, factor: pd.Series, returns: pd.Series) -> Dict:
        """
        分组分析
        
        Returns:
            包含分组统计的字典
        """
        # 对齐数据
        valid_mask = factor.notna() & returns.notna()
        factor_valid = factor[valid_mask]
        returns_valid = returns[valid_mask]
        
        if len(factor_valid) < 100:
            return self._empty_quantile_stats()
        
        # 检查因子唯一值数量
        n_unique = factor_valid.nunique()
        
        # 如果唯一值太少（如只有1和-1），使用实际分组数
        if n_unique <= 2:
            # 二值因子：直接按值分组
            actual_groups = n_unique
            quantiles = factor_valid.rank(method='dense').astype(int) - 1
            
            print(f"      ⚠️  Binary factor detected (unique values: {n_unique}), using {actual_groups} groups instead of {self.n_groups}")
        else:
            # 正常分组
            actual_groups = min(self.n_groups, n_unique)
            if actual_groups < self.n_groups:
                print(f"      ⚠️  Factor has only {n_unique} unique values, using {actual_groups} groups instead of {self.n_groups}")
            
            try:
                quantiles = pd.qcut(factor_valid, q=actual_groups, labels=False, duplicates='drop')
            except ValueError:
                # 如果qcut失败，使用等宽分箱
                quantiles = pd.cut(factor_valid, bins=actual_groups, labels=False, duplicates='drop')
        
        # 计算每组的统计量
        group_stats = []
        for q in range(actual_groups):
            group_mask = quantiles == q
            group_returns = returns_valid[group_mask]
            
            if len(group_returns) > 0:
                stats = {
                    'group': q + 1,
                    'mean_return': group_returns.mean(),
                    'std_return': group_returns.std(),
                    'sharpe': group_returns.mean() / (group_returns.std() + 1e-9) * np.sqrt(252 * 24 * 60),  # 年化
                    'count': len(group_returns),
                    'win_rate': (group_returns > 0).mean(),
                }
            else:
                stats = {
                    'group': q + 1,
                    'mean_return': np.nan,
                    'std_return': np.nan,
                    'sharpe': np.nan,
                    'count': 0,
                    'win_rate': np.nan,
                }
            
            group_stats.append(stats)
        
        group_stats_df = pd.DataFrame(group_stats)
        
        # 计算多空组合
        if len(group_stats_df) >= 2:
            long_short_return = (group_stats_df.iloc[-1]['mean_return'] - 
                                group_stats_df.iloc[0]['mean_return'])
            
            # 计算多空组合的夏普比率
            top_group = quantiles == (actual_groups - 1)
            bottom_group = quantiles == 0
            
            if top_group.sum() > 0 and bottom_group.sum() > 0:
                ls_returns = returns_valid[top_group].mean() - returns_valid[bottom_group].mean()
                ls_std = np.sqrt(returns_valid[top_group].var() + returns_valid[bottom_group].var())
            else:
                ls_returns = np.nan
                ls_std = np.nan
            
            monotonicity = self._calculate_monotonicity(group_stats_df['mean_return'])
        else:
            long_short_return = np.nan
            ls_returns = np.nan
            ls_std = 1e-9
            monotonicity = np.nan
        
        return {
            'group_stats': group_stats_df,
            'long_short_return': long_short_return,
            'long_short_sharpe': ls_returns / (ls_std + 1e-9) * np.sqrt(252 * 24 * 60),
            'monotonicity': monotonicity,
            'spread_ratio': group_stats_df['mean_return'].max() / (group_stats_df['mean_return'].std() + 1e-9),
            'actual_groups': actual_groups,  # 记录实际分组数
        }
    
    def _calculate_monotonicity(self, group_returns: pd.Series) -> float:
        """
        计算单调性指标
        
        单调性越接近1或-1，说明因子分组效果越好
        """
        if len(group_returns) < 2:
            return np.nan
        
        # 计算相邻组收益率差的符号一致性
        diffs = group_returns.diff().dropna()
        if len(diffs) == 0:
            return np.nan
        
        # 单调递增或递减的比例
        monotonic_ratio = max(
            (diffs > 0).sum() / len(diffs),
            (diffs < 0).sum() / len(diffs)
        )
        
        return monotonic_ratio
    
    def _empty_quantile_stats(self) -> Dict:
        """返回空的分组统计结果"""
        return {
            'group_stats': pd.DataFrame(),
            'long_short_return': np.nan,
            'long_short_sharpe': np.nan,
            'monotonicity': np.nan,
            'spread_ratio': np.nan,
        }