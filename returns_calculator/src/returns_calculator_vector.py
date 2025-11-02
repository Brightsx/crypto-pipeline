# src/returns_calculator.py - 收益率计算器（向量化版本）
import pandas as pd
import numpy as np
from datetime import timedelta
import logging
from typing import List, Tuple
from .time_utils import TimeUtils

class ReturnsCalculator:
    """收益率计算器 - 向量化版本"""
    
    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.time_utils = TimeUtils(config)
        self.price_column = config['data']['price_column']
        
    def calculate_returns_batch(self, symbol: str, time_points: pd.DatetimeIndex, 
                               data_loader) -> pd.DataFrame:
        """
        分批计算收益率 - 向量化版本
        
        Args:
            symbol: 交易对符号
            time_points: 计算时间点
            data_loader: 数据加载器
            
        Returns:
            收益率DataFrame
        """
        self.logger.info(f"开始向量化计算 {symbol} 的收益率")
        
        # 获取批次范围
        batches = self.time_utils.get_batch_ranges(time_points)
        
        # 初始化结果DataFrame
        result_columns = self._generate_column_names()
        results = []
        
        for i, (batch_start, batch_end, data_start, data_end) in enumerate(batches):
            self.logger.info(f"处理批次 {i+1}/{len(batches)}: {batch_start.date()} 到 {batch_end.date()}")
            
            try:
                # 加载数据
                kline_data = data_loader.load_kline_data(symbol, data_start, data_end)
                
                if kline_data.empty:
                    self.logger.warning(f"批次 {i+1} 无数据，跳过")
                    continue
                
                # 筛选当前批次的时间点
                batch_time_points = time_points[
                    (time_points >= batch_start) & (time_points <= batch_end)
                ]
                
                self.logger.info(f"批次数据: {len(kline_data)} 条K线, {len(batch_time_points)} 个时间点")
                
                # 向量化计算收益率
                batch_results = self._calculate_returns_vectorized(
                    kline_data, batch_time_points
                )
                
                if not batch_results.empty:
                    results.append(batch_results)
                    # 统计有效收益率数量
                    valid_count = batch_results.count().sum()
                    total_count = len(batch_results) * len(batch_results.columns)
                    self.logger.info(f"批次 {i+1} 完成: {valid_count}/{total_count} 个有效收益率")
                else:
                    self.logger.warning(f"批次 {i+1} 未生成有效结果")
                
            except Exception as e:
                self.logger.error(f"批次 {i+1} 计算失败: {str(e)}")
                continue
        
        # 合并结果
        if results:
            final_result = pd.concat(results, axis=0)
            final_result = final_result.sort_index()
            
            # 确保所有列都存在
            for col in result_columns:
                if col not in final_result.columns:
                    final_result[col] = np.nan
                    
            final_result = final_result[result_columns]
            
            # 统计最终结果
            total_valid = final_result.count().sum()
            total_possible = len(final_result) * len(final_result.columns)
            self.logger.info(f"{symbol} 收益率计算完成: {len(final_result)} 个时间点, "
                           f"{total_valid}/{total_possible} 个有效收益率 "
                           f"({total_valid/total_possible*100:.1f}%)")
            
            return final_result
        else:
            # 返回空结果
            empty_result = pd.DataFrame(
                index=pd.DatetimeIndex([], name='timestamp', tz='UTC'),
                columns=result_columns
            )
            self.logger.warning(f"{symbol} 未能计算出任何收益率")
            return empty_result
    
    def _calculate_returns_vectorized(self, kline_data: pd.DataFrame, 
                                    time_points: pd.DatetimeIndex) -> pd.DataFrame:
        """
        向量化计算收益率
        
        Args:
            kline_data: K线数据
            time_points: 时间点列表
            
        Returns:
            收益率DataFrame
        """
        if kline_data.empty or self.price_column not in kline_data.columns:
            self.logger.error(f"数据为空或缺少价格列 {self.price_column}")
            return pd.DataFrame()
        
        self.logger.info(f"开始向量化计算 {len(time_points)} 个时间点的收益率")
        self.logger.info(f"K线数据时间范围: {kline_data.index.min()} 到 {kline_data.index.max()}")
        self.logger.info(f"计算时间点范围: {time_points.min()} 到 {time_points.max()}")
        
        # 初始化结果DataFrame
        result_df = pd.DataFrame(index=time_points)
        result_df.index.name = 'timestamp'
        
        # 对每个延迟和周期组合进行向量化计算
        for delay in self.config['returns']['delays']:
            delay_sec = self.time_utils.parse_interval_to_seconds(delay)
            
            for period in self.config['returns']['periods']:
                period_sec = self.time_utils.parse_interval_to_seconds(period)
                
                try:
                    self.logger.debug(f"计算 delay={delay}, period={period}")
                    
                    # 向量化计算时间偏移
                    start_times = time_points + pd.Timedelta(seconds=delay_sec)
                    end_times = start_times + pd.Timedelta(seconds=period_sec)
                    
                    # 向量化获取价格
                    start_prices = self._vectorized_price_lookup(kline_data, start_times)
                    end_prices = self._vectorized_price_lookup(kline_data, end_times)
                    
                    # 向量化计算收益率
                    returns = (end_prices - start_prices) / start_prices
                    
                    # 存储结果
                    col_name = f"ret_delay_{delay}_period_{period}"
                    result_df[col_name] = returns
                    
                    # 统计有效数据
                    valid_count = returns.count()
                    self.logger.debug(f"{col_name}: {valid_count}/{len(returns)} 个有效值")
                    
                except Exception as e:
                    self.logger.error(f"计算失败 delay={delay}, period={period}: {str(e)}")
                    col_name = f"ret_delay_{delay}_period_{period}"
                    result_df[col_name] = np.nan
        
        return result_df
    
    def _vectorized_price_lookup(self, kline_data: pd.DataFrame, 
                               target_times: pd.DatetimeIndex) -> pd.Series:
        """
        向量化价格查找
        使用pandas merge_asof进行高效的时间对齐
        
        Args:
            kline_data: K线数据
            target_times: 目标时间数组
            
        Returns:
            对应的价格Series
        """
        if kline_data.empty or len(target_times) == 0:
            return pd.Series(np.nan, index=target_times)
        
        try:
            # 创建查找表
            lookup_df = pd.DataFrame({
                'target_time': target_times,
                'original_order': range(len(target_times))
            }).reset_index(drop=True)
            
            # 准备K线数据用于合并
            kline_for_merge = kline_data[[self.price_column]].reset_index()
            kline_for_merge = kline_for_merge.sort_values('timestamp')
            
            # 使用merge_asof进行向前查找最近时间点
            merged = pd.merge_asof(
                lookup_df.sort_values('target_time'),
                kline_for_merge,
                left_on='target_time',
                right_on='timestamp',
                direction='backward'  # 向前查找
            )
            
            # 检查时间差是否在合理范围内
            kline_interval_sec = self.time_utils.parse_interval_to_seconds(
                self.config['data']['kline_interval']
            )
            
            # 计算时间差
            time_diff = (merged['target_time'] - merged['timestamp']).dt.total_seconds()
            
            # 创建有效性掩码
            valid_mask = (
                (~merged['timestamp'].isna()) &  # K线时间存在
                (time_diff <= kline_interval_sec * 2) &  # 时间差在合理范围内
                (time_diff >= 0)  # 不能是未来时间
            )
            
            # 应用掩码
            prices = merged[self.price_column].where(valid_mask, np.nan)
            
            # 恢复原始顺序
            merged['price'] = prices
            merged = merged.sort_values('original_order')
            
            result = pd.Series(
                merged['price'].values,
                index=target_times,
                name='price'
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"向量化价格查找失败: {str(e)}")
            return pd.Series(np.nan, index=target_times)
    
    def _generate_column_names(self) -> List[str]:
        """生成结果列名"""
        columns = []
        for delay in self.config['returns']['delays']:
            for period in self.config['returns']['periods']:
                col_name = f"ret_delay_{delay}_period_{period}"
                columns.append(col_name)
        return columns
    
    def _validate_data_coverage(self, kline_data: pd.DataFrame, 
                              time_points: pd.DatetimeIndex) -> Tuple[pd.Timestamp, pd.Timestamp]:
        """
        验证数据覆盖范围
        
        Returns:
            (数据开始时间, 数据结束时间)
        """
        if kline_data.empty:
            return None, None
            
        data_start = kline_data.index.min()
        data_end = kline_data.index.max()
        
        # 计算所需的最大时间范围
        max_delay = max([
            self.time_utils.parse_interval_to_seconds(delay) 
            for delay in self.config['returns']['delays']
        ])
        max_period = max([
            self.time_utils.parse_interval_to_seconds(period)
            for period in self.config['returns']['periods']
        ])
        
        required_start = time_points.min()
        required_end = time_points.max() + pd.Timedelta(seconds=max_delay + max_period)
        
        if data_start > required_start:
            self.logger.warning(f"数据开始时间 {data_start} 晚于需求 {required_start}")
        
        if data_end < required_end:
            self.logger.warning(f"数据结束时间 {data_end} 早于需求 {required_end}")
        
        return data_start, data_end