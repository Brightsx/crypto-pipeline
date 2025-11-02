"""因子计算引擎"""
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from tqdm import tqdm

from core.config import config
from core.data_manager import DataManager
from core.utils import generate_time_points, align_data_to_timepoints, merge_batch_results
from factors.registry import factor_registry


logger = logging.getLogger(__name__)


class FactorEngine:
    """因子计算引擎"""
    
    def __init__(self):
        self.data_manager = DataManager()
        self.target_timepoints = None
        
    def _generate_target_timepoints(self) -> pd.DatetimeIndex:
        """生成目标时间点序列"""
        if self.target_timepoints is None:
            self.target_timepoints = generate_time_points(
                config.start_time, 
                config.end_time, 
                config.calc_frequency
            )
            logger.info(f"Generated {len(self.target_timepoints)} target timepoints")
        return self.target_timepoints
    
    def _compute_batch_factors(self, symbol: str, batch_start: datetime, 
                              batch_end: datetime) -> pd.DataFrame:
        """
        计算单个批次的因子
        
        Args:
            symbol: 币种符号
            batch_start: 批次开始时间
            batch_end: 批次结束时间
            
        Returns:
            因子结果DataFrame
        """
        logger.info(f"Computing factors for {symbol}: {batch_start} to {batch_end}")
        
        # 获取批次对应的目标时间点
        target_times = self._generate_target_timepoints()
        batch_times = target_times[
            (target_times >= batch_start) & (target_times <= batch_end)
        ]
        
        if len(batch_times) == 0:
            logger.warning(f"No target timepoints in batch range")
            return pd.DataFrame()
        
        # 按K线窗口分组计算因子
        window_results = {}
        
        for window in config.kline_windows:
            window_factors = factor_registry.get_factors_by_window(window)
            if not window_factors:
                continue
                
            # 加载这个窗口的数据（包含回看数据）
            kline_data = self.data_manager.load_kline_data(
                symbol=symbol,
                window=window,
                start_date=batch_start.strftime('%Y-%m-%d'),
                end_date=batch_end.strftime('%Y-%m-%d'),
                include_lookback=True
            )
            
            if kline_data.empty:
                logger.warning(f"No data for {symbol} {window}")
                continue
            
            # 计算这个窗口的所有因子
            window_factor_results = {}
            
            for factor_name, factor_info in window_factors.items():
                try:
                    logger.debug(f"Computing factor: {factor_name}")
                    
                    # 执行用户定义的因子函数
                    factor_func = factor_info['func']
                    factor_result = factor_func(kline_data)
                    
                    # 处理因子计算结果
                    if isinstance(factor_result, pd.Series):
                        # 如果结果是Series，需要与原始数据的时间对齐
                        factor_df = pd.DataFrame({
                            'end_time': kline_data['end_time'],
                            factor_name: factor_result.values
                        }).dropna()
                        
                    elif isinstance(factor_result, pd.DataFrame):
                        # 如果结果是DataFrame，确保有时间列
                        if 'end_time' not in factor_result.columns:
                            factor_result['end_time'] = kline_data['end_time']
                        factor_df = factor_result.dropna()
                        
                    else:
                        logger.error(f"Invalid factor result type for {factor_name}")
                        continue
                    
                    # 将因子数据对齐到目标时间点
                    aligned_factor = align_data_to_timepoints(
                        factor_df, batch_times, 'end_time'
                    )
                    
                    # 只保留因子值列
                    factor_cols = [col for col in aligned_factor.columns if col != 'end_time']
                    if factor_cols:
                        window_factor_results[factor_name] = aligned_factor[factor_cols[0]]
                    
                except Exception as e:
                    logger.error(f"Error computing factor {factor_name}: {e}")
                    continue
            
            window_results[window] = window_factor_results
        
        # 合并所有窗口的因子结果
        all_factor_series = {}
        for window_data in window_results.values():
            all_factor_series.update(window_data)
        
        if not all_factor_series:
            logger.warning(f"No factors computed for {symbol} batch")
            return pd.DataFrame()
        
        # 构建最终结果DataFrame
        result_df = pd.DataFrame(all_factor_series, index=batch_times)
        result_df.index.name = 'timestamp'
        
        logger.info(f"Computed {len(result_df.columns)} factors for {len(result_df)} timepoints")
        return result_df
    
    def compute_factors(self, symbol: str) -> pd.DataFrame:
        """
        计算指定币种的所有因子
        
        Args:
            symbol: 币种符号
            
        Returns:
            完整的因子结果DataFrame
        """
        logger.info(f"Starting factor computation for {symbol}")
        
        # 获取批次日期范围
        batch_ranges = self.data_manager.get_batch_date_ranges(
            config.start_time,
            config.end_time
        )
        
        logger.info(f"Processing {len(batch_ranges)} batches")
        
        # 分批处理
        batch_results = []
        for i, (batch_start, batch_end) in enumerate(tqdm(batch_ranges, desc=f"Processing {symbol}")):
            try:
                batch_result = self._compute_batch_factors(symbol, batch_start, batch_end)
                if not batch_result.empty:
                    batch_results.append(batch_result)
                
                # 清理部分缓存以节省内存
                if i % 3 == 0:
                    self.data_manager.clear_cache()
                    
            except Exception as e:
                logger.error(f"Error in batch {i}: {e}")
                continue
        
        # 合并所有批次结果
        if not batch_results:
            logger.warning(f"No valid results for {symbol}")
            return pd.DataFrame()
        
        final_result = merge_batch_results(batch_results)
        logger.info(f"Final result for {symbol}: {len(final_result)} rows, {len(final_result.columns)} factors")
        
        return final_result
    
    def compute_all_symbols(self) -> Dict[str, pd.DataFrame]:
        """
        计算所有币种的因子
        
        Returns:
            {symbol: factor_dataframe} 字典
        """
        results = {}
        
        for symbol in config.symbols:
            try:
                logger.info(f"Starting computation for {symbol}")
                result = self.compute_factors(symbol)
                
                if not result.empty:
                    results[symbol] = result
                    
                    # 保存结果
                    output_file = config.output_path / f"{symbol}_factors.parquet"
                    result.to_parquet(output_file)
                    logger.info(f"Saved factors for {symbol} to {output_file}")
                
            except Exception as e:
                logger.error(f"Failed to compute factors for {symbol}: {e}")
                continue
            
            finally:
                # 清理缓存
                self.data_manager.clear_cache()
        
        return results
    
    def get_factor_summary(self) -> pd.DataFrame:
        """获取因子摘要信息"""
        factors = factor_registry.list_factors()
        if not factors:
            return pd.DataFrame()
        
        summary_data = []
        for factor_name in factors:
            factor_info = factor_registry.get_factor(factor_name)
            summary_data.append({
                'factor_name': factor_name,
                'kline_window': factor_info['kline_window'],
                'description': factor_info['description']
            })
        
        return pd.DataFrame(summary_data)