# src/returns_calculator.py - 收益率计算器
import pandas as pd
import numpy as np
from datetime import timedelta
import logging
from typing import List
from .time_utils import TimeUtils

class ReturnsCalculator:
    """收益率计算器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.time_utils = TimeUtils(config)
        self.price_column = config['data']['price_column']
        
    def calculate_returns_batch(self, symbol: str, time_points: pd.DatetimeIndex, 
                               data_loader) -> pd.DataFrame:
        """
        分批计算收益率
        
        Args:
            symbol: 交易对符号
            time_points: 计算时间点
            data_loader: 数据加载器
            
        Returns:
            收益率DataFrame
        """
        self.logger.info(f"开始计算 {symbol} 的收益率")
        
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
                
                # 计算收益率
                batch_results = self._calculate_returns_for_timepoints(
                    kline_data, batch_time_points
                )
                
                if not batch_results.empty:
                    results.append(batch_results)
                
                self.logger.info(f"批次 {i+1} 完成，计算了 {len(batch_results)} 个时间点")
                
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
            
            self.logger.info(f"{symbol} 收益率计算完成，共 {len(final_result)} 个时间点")
            return final_result
        else:
            # 返回空结果
            empty_result = pd.DataFrame(
                index=pd.DatetimeIndex([], name='timestamp', tz='UTC'),
                columns=result_columns
            )
            self.logger.warning(f"{symbol} 未能计算出任何收益率")
            return empty_result
    
    def _calculate_returns_for_timepoints(self, kline_data: pd.DataFrame, 
                                        time_points: pd.DatetimeIndex) -> pd.DataFrame:
        """为指定时间点计算收益率"""
        if kline_data.empty or self.price_column not in kline_data.columns:
            self.logger.error(f"数据为空或缺少价格列 {self.price_column}")
            return pd.DataFrame()
        
        self.logger.info(f"开始计算 {len(time_points)} 个时间点的收益率")
        self.logger.info(f"K线数据时间范围: {kline_data.index.min()} 到 {kline_data.index.max()}")
        self.logger.info(f"计算时间点范围: {time_points.min()} 到 {time_points.max()}")
        self.logger.info(f"可用价格列: {list(kline_data.columns)}")
        
        results = []
        success_count = 0
        
        for i, timestamp in enumerate(time_points):
            try:
                row_results = {'timestamp': timestamp}
                row_has_data = False
                
                # 对每个延迟和周期组合计算收益率
                for delay in self.config['returns']['delays']:
                    for period in self.config['returns']['periods']:
                        
                        delay_sec = self.time_utils.parse_interval_to_seconds(delay)
                        return_value = self._calculate_single_return(
                            kline_data, timestamp, delay_sec, period
                        )
                        
                        col_name = f"ret_delay_{delay}_period_{period}"
                        row_results[col_name] = return_value
                        
                        if not pd.isna(return_value):
                            row_has_data = True
                
                if row_has_data:
                    success_count += 1
                    
                results.append(row_results)
                
                # 每100个时间点打印一次进度
                if (i + 1) % 100 == 0:
                    self.logger.info(f"已处理 {i + 1}/{len(time_points)} 个时间点，成功计算 {success_count} 个")
                    
            except Exception as e:
                self.logger.debug(f"计算时间点 {timestamp} 失败: {str(e)}")
                continue
        
        self.logger.info(f"总共成功计算 {success_count}/{len(time_points)} 个时间点")
        
        if results:
            df = pd.DataFrame(results)
            df = df.set_index('timestamp')
            df.index.name = 'timestamp'
            return df
        else:
            return pd.DataFrame()
    
    def _calculate_single_return(self, kline_data: pd.DataFrame, timestamp: pd.Timestamp,
                            delay: int, period: str) -> float:
        """计算单个收益率"""
        # 计算延迟后的起始时间
        start_time = timestamp + timedelta(seconds=delay)
        
        # 计算结束时间
        period_seconds = self.time_utils.parse_interval_to_seconds(period)
        end_time = start_time + timedelta(seconds=period_seconds)
        
        try:
            # 获取起始价格
            start_price = self._get_price_at_time(kline_data, start_time)
            if pd.isna(start_price):
                # 添加调试信息
                if timestamp == kline_data.index.min() or timestamp.hour == 0 and timestamp.minute < 5:
                    self.logger.debug(f"起始价格为nan: {timestamp} + {delay}s = {start_time}")
                return np.nan
            
            # 获取结束价格
            end_price = self._get_price_at_time(kline_data, end_time)
            if pd.isna(end_price):
                # 添加调试信息
                if timestamp == kline_data.index.min() or timestamp.hour == 0 and timestamp.minute < 5:
                    self.logger.debug(f"结束价格为nan: {start_time} + {period_seconds}s = {end_time}")
                return np.nan
            
            # 计算收益率
            return_rate = (end_price - start_price) / start_price
            return return_rate
            
        except Exception as e:
            self.logger.debug(f"计算收益率失败 {timestamp}, delay={delay}, period={period}: {str(e)}")
            return np.nan
    
    def _get_price_at_time(self, kline_data: pd.DataFrame, target_time: pd.Timestamp) -> float:
        """
        获取指定时间的价格
        使用最近的K线数据
        
        Args:
            kline_data: K线数据
            target_time: 目标时间
            
        Returns:
            价格值
        """
        if kline_data.empty:
            return np.nan
        
        # 找到最接近的时间点（向前找）
        valid_times = kline_data.index[kline_data.index <= target_time]
        
        if len(valid_times) == 0:
            return np.nan
        
        closest_time = valid_times[-1]  # 最近的时间点
        
        # 检查时间差是否在合理范围内（比如不超过K线窗口的2倍）
        kline_interval_sec = self.time_utils.parse_interval_to_seconds(
            self.config['data']['kline_interval']
        )
        time_diff = (target_time - closest_time).total_seconds()
        
        if time_diff > kline_interval_sec * 2:
            return np.nan
        
        return kline_data.loc[closest_time, self.price_column]
    
    def _generate_column_names(self) -> List[str]:
        """生成结果列名"""
        columns = []
        for delay in self.config['returns']['delays']:
            for period in self.config['returns']['periods']:
                col_name = f"ret_delay_{delay}_period_{period}"
                columns.append(col_name)
        return columns