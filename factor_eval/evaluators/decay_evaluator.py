"""
evaluators/decay_evaluator.py
因子衰减分析评估器
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List


class DecayEvaluator:
    """因子衰减评估器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.eval_config = config['evaluation']
    
    def evaluate(self, factors_df: pd.DataFrame, returns_df: pd.DataFrame) -> Dict:
        """
        分析因子的衰减特性
        
        Returns:
            包含所有因子衰减结果的字典
        """
        results = {}
        
        for factor_name in factors_df.columns:
            # 分析该因子在不同收益率周期的表现
            decay_stats = self._analyze_decay(
                factors_df[factor_name],
                returns_df
            )
            
            results[factor_name] = decay_stats
        
        return results
    
    def _analyze_decay(self, factor: pd.Series, returns_df: pd.DataFrame) -> Dict:
        """
        分析单个因子的衰减特性
        
        通过比较因子在不同预测周期的IC来判断衰减速度
        """
        ic_by_period = {}
        
        # 计算各个周期的IC
        for return_col in returns_df.columns:
            valid_mask = factor.notna() & returns_df[return_col].notna()
            
            if valid_mask.sum() < 30:
                ic_by_period[return_col] = np.nan
                continue
            
            # 计算Spearman IC
            ic, _ = stats.spearmanr(
                factor[valid_mask],
                returns_df[return_col][valid_mask]
            )
            
            ic_by_period[return_col] = ic
        
        # 提取周期信息并排序
        period_ics = []
        for col, ic in ic_by_period.items():
            # 从列名提取周期，如 ret_delay_9s_period_1m -> 1
            # ret_delay_9s_period_5m -> 5
            # ret_delay_9s_period_15m -> 15
            # ret_delay_9s_period_1h -> 60
            # ret_delay_9s_period_1d -> 1440
            if 'period_' in col:
                period_str = col.split('period_')[1]
                if period_str.endswith('m'):
                    period = int(period_str[:-1])
                elif period_str.endswith('h'):
                    period = int(period_str[:-1]) * 60
                elif period_str.endswith('d'):
                    period = int(period_str[:-1]) * 1440
                else:
                    period = 0
                
                period_ics.append({
                    'period_minutes': period,
                    'period_name': period_str,
                    'ic': ic
                })
        
        # 按周期排序
        period_ics.sort(key=lambda x: x['period_minutes'])
        period_df = pd.DataFrame(period_ics)
        
        # 计算衰减指标
        if len(period_df) >= 2 and not period_df['ic'].isna().all():
            # IC衰减率 (相邻周期IC的下降速度)
            ic_diffs = period_df['ic'].diff()
            decay_rate = (ic_diffs / period_df['ic'].shift(1)).mean()
            
            # 半衰期 (IC下降到初始值一半所需的周期)
            first_ic = period_df['ic'].iloc[0]
            if not np.isnan(first_ic) and first_ic != 0:
                half_ic = first_ic / 2
                # 找到最接近half_ic的周期
                closest_idx = (period_df['ic'] - half_ic).abs().idxmin()
                half_life = period_df.loc[closest_idx, 'period_minutes']
            else:
                half_life = np.nan
            
            # 最优持有期 (IC绝对值最大的周期)
            best_period_idx = period_df['ic'].abs().idxmax()
            best_period = period_df.loc[best_period_idx, 'period_minutes']
            best_ic = period_df.loc[best_period_idx, 'ic']
        else:
            decay_rate = np.nan
            half_life = np.nan
            best_period = np.nan
            best_ic = np.nan
        
        return {
            'period_ic_curve': period_df,
            'decay_rate': decay_rate,  # IC衰减率
            'half_life_minutes': half_life,  # 半衰期(分钟)
            'best_holding_period_minutes': best_period,  # 最优持有期(分钟)
            'best_period_ic': best_ic,  # 最优持有期的IC
            'ic_range': period_df['ic'].max() - period_df['ic'].min() if len(period_df) > 0 else np.nan,
        }