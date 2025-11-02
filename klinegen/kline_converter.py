import pandas as pd
import numpy as np
from pathlib import Path
import logging
from datetime import datetime, timezone, timedelta
import argparse
from typing import Optional, Dict, Any, List, Tuple
import warnings
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import multiprocessing as mp
import psutil
import gc
from functools import partial
import time
warnings.filterwarnings('ignore')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class AggtradesToKlineConverter:
    """
    将Binance aggtrades数据转换为K线数据 - 高性能版本
    支持多种时间周期，包含丰富的特征用于因子挖掘
    包含无成交时间段的完整K线序列
    修正了真实交易数量的计算逻辑，去除不必要的上下限限制
    """
    
    def __init__(self, data_root: str = "./data", n_jobs: int = None):
        """
        初始化转换器
        
        Args:
            data_root: 数据根目录路径
            n_jobs: 并行进程数，None为自动检测
        """
        self.data_root = Path(data_root)
        
        # 获取系统信息
        cpu_count = mp.cpu_count()
        memory_gb = psutil.virtual_memory().total / (1024**3)
        
        # 自动检测最优进程数
        if n_jobs is None:
            # 根据CPU核心数和内存大小自动调整
            if memory_gb < 8:
                self.n_jobs = max(1, cpu_count // 2)
            elif memory_gb < 16:
                self.n_jobs = max(2, cpu_count - 1)
            else:
                self.n_jobs = cpu_count
        else:
            self.n_jobs = n_jobs
        
        # 只在主进程中打印系统信息（避免子进程重复打印）
        if n_jobs != 1:  # n_jobs=1 通常表示这是子进程
            logger.info(f"检测到 {cpu_count} 个CPU核心，{memory_gb:.1f}GB 内存")
            logger.info(f"使用 {self.n_jobs} 个并行进程")
    
    def parse_time_interval(self, interval: str) -> tuple:
        """解析时间间隔字符串"""
        import re
        match = re.match(r'(\d+)(ms|s|m|h|d)', interval.lower())
        if not match:
            raise ValueError(f"无效的时间间隔格式: {interval}. 支持格式: 1s, 5m, 100ms等")
        
        value = int(match.group(1))
        unit = match.group(2)
        
        return value, unit
    
    def get_interval_milliseconds(self, interval: str) -> int:
        """将时间间隔转换为毫秒"""
        value, unit = self.parse_time_interval(interval)
        
        unit_multipliers = {
            'ms': 1,
            's': 1000,
            'm': 60000,
            'h': 3600000,
            'd': 86400000
        }
        
        return value * unit_multipliers[unit]
    
    def load_aggtrades_data_optimized(self, file_path: Path) -> pd.DataFrame:
        """
        优化的aggtrades数据加载
        
        Args:
            file_path: aggtrades文件路径
            
        Returns:
            DataFrame with processed aggtrades data
        """
        try:
            logger.info(f"正在加载文件: {file_path}")
            
            # 使用更高效的parquet读取参数
            df = pd.read_parquet(
                file_path,
                engine='pyarrow',
                columns=['agg_trade_id', 'price', 'quantity', 'first_trade_id', 
                        'last_trade_id', 'transact_time', 'is_buyer_maker']
            )
            
            if len(df) == 0:
                logger.warning(f"文件 {file_path} 为空")
                return df
            
            logger.info(f"加载了 {len(df):,} 条aggTrades记录")
            
            # 批量类型转换 - 保持64位精度
            df = df.astype({
                'price': 'float64',
                'quantity': 'float64',
                'transact_time': 'int64',
                'is_buyer_maker': 'bool',
                'agg_trade_id': 'int64',
                'first_trade_id': 'int64',
                'last_trade_id': 'int64'
            })
            
            # 按时间排序 - 使用更高效的排序
            df.sort_values('transact_time', inplace=True)
            df.reset_index(drop=True, inplace=True)
            
            # 预计算成交金额和真实交易数量
            df['amount'] = df['price'] * df['quantity']
            # 计算每个aggtrade包含的真实交易数量
            df['real_trade_count'] = df['last_trade_id'] - df['first_trade_id'] + 1
            
            logger.info(f"时间范围: {df['transact_time'].min()} - {df['transact_time'].max()}")
            logger.info(f"价格范围: {df['price'].min():.8f} - {df['price'].max():.8f}")
            logger.info(f"平均每aggtrade包含真实交易数: {df['real_trade_count'].mean():.2f}")
            
            return df
            
        except Exception as e:
            logger.error(f"加载aggtrades数据失败 {file_path}: {e}")
            return pd.DataFrame()
    
    def generate_complete_kline_timeline(self, start_time: int, end_time: int, interval_ms: int, 
                                       ensure_daily_boundary: bool = True) -> pd.DataFrame:
        """
        生成完整的K线时间序列，包括无成交的时间段
        
        Args:
            start_time: 开始时间戳(毫秒)
            end_time: 结束时间戳(毫秒)
            interval_ms: K线间隔(毫秒)
            ensure_daily_boundary: 是否确保与UTC日期边界对齐
            
        Returns:
            包含所有时间段的DataFrame
        """
        if ensure_daily_boundary:
            # 转换为UTC日期来确保边界对齐
            start_dt = datetime.fromtimestamp(start_time / 1000, tz=timezone.utc)
            end_dt = datetime.fromtimestamp(end_time / 1000, tz=timezone.utc)
            
            # 获取当天UTC 00:00:00的时间戳
            start_date = start_dt.date()
            end_date = end_dt.date()
            
            day_start_dt = datetime.combine(start_date, datetime.min.time().replace(tzinfo=timezone.utc))
            day_end_dt = datetime.combine(end_date, datetime.max.time().replace(tzinfo=timezone.utc))
            
            # 转换回毫秒时间戳
            day_start_ms = int(day_start_dt.timestamp() * 1000)
            day_end_ms = int(day_end_dt.timestamp() * 1000)
            
            # 使用日期边界作为生成范围
            timeline_start = day_start_ms
            timeline_end = day_end_ms
            
            logger.info(f"UTC日期对齐: {start_date} 00:00:00 到 {end_date} 23:59:59")
            logger.info(f"时间戳范围: {timeline_start} - {timeline_end}")
        else:
            timeline_start = start_time
            timeline_end = end_time
        
        # 计算对齐到间隔的开始和结束时间戳
        first_kline_start = (timeline_start // interval_ms) * interval_ms
        last_kline_start = (timeline_end // interval_ms) * interval_ms
        
        # 生成完整时间序列
        kline_starts = np.arange(first_kline_start, last_kline_start + interval_ms, interval_ms)
        
        # 创建基础时间DataFrame
        timeline_df = pd.DataFrame({
            'start_time': kline_starts,
            'end_time': kline_starts + interval_ms - 1
        })
        
        logger.info(f"生成 {len(timeline_df)} 个K线时间段")
        logger.info(f"K线时间范围: {first_kline_start} - {last_kline_start}")
        
        # 验证时间对齐
        if ensure_daily_boundary:
            self.verify_utc_alignment(timeline_df, interval_ms)
        
        return timeline_df
    
    def verify_utc_alignment(self, timeline_df: pd.DataFrame, interval_ms: int):
        """验证K线时间是否与UTC时间正确对齐"""
        if len(timeline_df) == 0:
            return
        
        first_start = timeline_df['start_time'].iloc[0]
        last_start = timeline_df['start_time'].iloc[-1]
        
        first_dt = datetime.fromtimestamp(first_start / 1000, tz=timezone.utc)
        last_dt = datetime.fromtimestamp(last_start / 1000, tz=timezone.utc)
        
        logger.info(f"首个K线开始时间: {first_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        logger.info(f"最后K线开始时间: {last_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        # 验证是否整秒对齐（对于秒级及以上的间隔）
        if interval_ms >= 1000:
            if first_start % 1000 != 0:
                logger.warning(f"时间未对齐到秒: {first_start}")
        
        # 验证间隔是否正确
        if len(timeline_df) > 1:
            actual_interval = timeline_df['start_time'].iloc[1] - timeline_df['start_time'].iloc[0]
            if actual_interval != interval_ms:
                logger.warning(f"时间间隔不匹配: 期望{interval_ms}ms, 实际{actual_interval}ms")
    
    def fill_missing_klines_with_nan(self, kline_df: pd.DataFrame, timeline_df: pd.DataFrame) -> pd.DataFrame:
        """
        用NaN填充缺失的K线时间段
        
        Args:
            kline_df: 有成交数据的K线DataFrame
            timeline_df: 完整时间序列DataFrame
            
        Returns:
            填充后的完整K线DataFrame
        """
        # 合并数据，保留所有时间点
        complete_df = timeline_df.merge(kline_df, on='start_time', how='left', suffixes=('', '_y'))
        
        # 更新end_time（优先使用timeline的值）
        if 'end_time_y' in complete_df.columns:
            complete_df['end_time'] = complete_df['end_time'].fillna(complete_df['end_time_y'])
            complete_df.drop('end_time_y', axis=1, inplace=True)
        
        # 定义需要填充NaN的数值列
        numeric_columns = [
            'first_trade_time', 'last_trade_time', 'trade_duration_ms',
            'open', 'high', 'low', 'close', 'volume', 'amount', 'trade_count',
            'aggtrade_count', 'real_trade_count',
            'buy_volume', 'sell_volume', 'buy_amount', 'sell_amount', 
            'buy_count', 'sell_count', 'buy_aggtrade_count', 'sell_aggtrade_count',
            'vwap', 'price_volatility', 'order_flow_imbalance', 'price_range', 'price_range_pct',
            'avg_trade_size', 'avg_trade_amount', 'max_trade_size', 'min_trade_size',
            'large_trade_volume', 'small_trade_volume', 'large_trade_count', 'small_trade_count',
            'large_trade_ratio', 'quantity_weighted_price', 'trade_intensity',
            'buy_pressure', 'sell_pressure', 'price_trend', 'liquidity_score',
            'first_agg_trade_id', 'last_agg_trade_id', 'first_trade_id', 'last_trade_id',
            # 新增特征
            'price_momentum', 'trade_size_variance', 'price_acceleration', 'volume_momentum',
            'order_imbalance_strength', 'price_efficiency', 'tick_direction_entropy',
            'avg_aggtrade_real_trades', 'max_aggtrade_real_trades', 'min_aggtrade_real_trades',
            'aggtrade_fragmentation', 'price_impact', 'time_between_trades_avg',
            'time_between_trades_std', 'dominant_side_volume_ratio', 'micro_price_trend',
            'volume_weighted_tick_direction', 'trade_clustering_coefficient',
            'price_reversion_strength', 'order_book_pressure_proxy'
        ]
        
        # 确保所有数值列都存在，不存在的用NaN填充
        for col in numeric_columns:
            if col not in complete_df.columns:
                complete_df[col] = np.nan
        
        # 重新排列列顺序
        column_order = [
            'start_time', 'end_time', 'first_trade_time', 'last_trade_time', 'trade_duration_ms',
            'open', 'high', 'low', 'close', 'volume', 'amount', 
            'trade_count', 'aggtrade_count', 'real_trade_count',
            'buy_volume', 'sell_volume', 'buy_amount', 'sell_amount', 
            'buy_count', 'sell_count', 'buy_aggtrade_count', 'sell_aggtrade_count',
            'vwap', 'price_volatility', 'order_flow_imbalance', 'price_range', 'price_range_pct',
            'avg_trade_size', 'avg_trade_amount', 'max_trade_size', 'min_trade_size',
            'large_trade_volume', 'small_trade_volume', 'large_trade_count', 'small_trade_count', 
            'large_trade_ratio', 'quantity_weighted_price', 'trade_intensity', 'buy_pressure', 
            'sell_pressure', 'price_trend', 'liquidity_score', 'first_agg_trade_id', 
            'last_agg_trade_id', 'first_trade_id', 'last_trade_id',
            # 新增特征
            'price_momentum', 'trade_size_variance', 'price_acceleration', 'volume_momentum',
            'order_imbalance_strength', 'price_efficiency', 'tick_direction_entropy',
            'avg_aggtrade_real_trades', 'max_aggtrade_real_trades', 'min_aggtrade_real_trades',
            'aggtrade_fragmentation', 'price_impact', 'time_between_trades_avg',
            'time_between_trades_std', 'dominant_side_volume_ratio', 'micro_price_trend',
            'volume_weighted_tick_direction', 'trade_clustering_coefficient',
            'price_reversion_strength', 'order_book_pressure_proxy'
        ]
        
        # 只选择存在的列
        existing_columns = [col for col in column_order if col in complete_df.columns]
        complete_df = complete_df[existing_columns]
        
        logger.info(f"填充完成，总K线数: {len(complete_df)}, 有效K线: {kline_df.shape[0] if not kline_df.empty else 0}")
        
        return complete_df
    
    def calculate_advanced_features(self, group_data: Dict[str, Any]) -> Dict[str, float]:
        """
        计算高级特征，基于当前K线内的aggtrades数据
        严格避免未来函数，去除不必要的上下限限制
        
        Args:
            group_data: 包含当前K线所有数据的字典
            
        Returns:
            高级特征字典
        """
        prices = group_data['prices']
        quantities = group_data['quantities']
        amounts = group_data['amounts']
        timestamps = group_data['timestamps']
        is_buy_mask = group_data['is_buy_mask']
        real_trade_counts = group_data['real_trade_counts']
        
        features = {}
        
        # 基础检查
        if len(prices) == 0:
            return {key: np.nan for key in [
                'price_momentum', 'trade_size_variance', 'price_acceleration', 'volume_momentum',
                'order_imbalance_strength', 'price_efficiency', 'tick_direction_entropy',
                'avg_aggtrade_real_trades', 'max_aggtrade_real_trades', 'min_aggtrade_real_trades',
                'aggtrade_fragmentation', 'price_impact', 'time_between_trades_avg',
                'time_between_trades_std', 'dominant_side_volume_ratio', 'micro_price_trend',
                'volume_weighted_tick_direction', 'trade_clustering_coefficient',
                'price_reversion_strength', 'order_book_pressure_proxy'
            ]}
        
        n_trades = len(prices)
        total_volume = np.sum(quantities)
        
        # 1. 价格动量 (基于K线内价格变化)
        if n_trades > 1:
            price_changes = np.diff(prices)
            volume_weights = quantities[1:] / np.sum(quantities[1:]) if np.sum(quantities[1:]) > 0 else np.ones(len(quantities[1:])) / len(quantities[1:])
            features['price_momentum'] = np.sum(price_changes * volume_weights)
        else:
            features['price_momentum'] = 0.0
        
        # 2. 交易规模方差
        features['trade_size_variance'] = np.var(quantities) if n_trades > 1 else 0.0
        
        # 3. 价格加速度 (二阶差分)
        if n_trades > 2:
            price_acceleration = np.diff(prices, n=2)
            features['price_acceleration'] = np.mean(price_acceleration)
        else:
            features['price_acceleration'] = 0.0
        
        # 4. 成交量动量
        if n_trades > 1:
            # 计算累计成交量的变化率
            cum_volume = np.cumsum(quantities)
            volume_changes = np.diff(cum_volume) / (cum_volume[:-1] + 1e-10)  # 避免除零
            features['volume_momentum'] = np.mean(volume_changes)
        else:
            features['volume_momentum'] = 0.0
        
        # 5. 订单不平衡强度 (改进版本)
        buy_volume = np.sum(quantities[is_buy_mask])
        sell_volume = np.sum(quantities[~is_buy_mask])
        if total_volume > 0:
            basic_imbalance = (buy_volume - sell_volume) / total_volume
            # 考虑交易频次的影响
            buy_count = np.sum(is_buy_mask)
            sell_count = n_trades - buy_count
            count_imbalance = (buy_count - sell_count) / n_trades if n_trades > 0 else 0
            features['order_imbalance_strength'] = abs(basic_imbalance) * (1 + abs(count_imbalance))
        else:
            features['order_imbalance_strength'] = 0.0
        
        # 6. 价格效率 (价格发现效率)
        if n_trades > 2 and total_volume > 0:
            # 计算价格变化与成交量的相关性
            price_returns = np.diff(prices) / (prices[:-1] + 1e-10)
            volume_weights = quantities[1:] / total_volume
            if len(price_returns) > 1 and np.std(price_returns) > 1e-10:
                try:
                    corr_matrix = np.corrcoef(price_returns, volume_weights)
                    if not np.isnan(corr_matrix[0, 1]):
                        features['price_efficiency'] = abs(corr_matrix[0, 1])
                    else:
                        features['price_efficiency'] = 0.0
                except:
                    features['price_efficiency'] = 0.0
            else:
                features['price_efficiency'] = 0.0
        else:
            features['price_efficiency'] = 0.0
        
        # 7. 成交方向熵 (Tick Direction Entropy)
        if n_trades > 1:
            tick_directions = np.sign(np.diff(prices))
            tick_directions = tick_directions[tick_directions != 0]  # 去除无变化的tick
            if len(tick_directions) > 0:
                unique, counts = np.unique(tick_directions, return_counts=True)
                probabilities = counts / len(tick_directions)
                # 去除上限限制，让熵值自然分布
                features['tick_direction_entropy'] = -np.sum(probabilities * np.log2(probabilities + 1e-10))
            else:
                features['tick_direction_entropy'] = 0.0
        else:
            features['tick_direction_entropy'] = 0.0
        
        # 8. Aggtrade真实交易统计
        features['avg_aggtrade_real_trades'] = np.mean(real_trade_counts)
        features['max_aggtrade_real_trades'] = np.max(real_trade_counts)
        features['min_aggtrade_real_trades'] = np.min(real_trade_counts)
        
        # 9. Aggtrade碎片化程度 (去除上限)
        total_real_trades = np.sum(real_trade_counts)
        aggtrade_count = len(real_trade_counts)
        if aggtrade_count > 0:
            features['aggtrade_fragmentation'] = total_real_trades / aggtrade_count
        else:
            features['aggtrade_fragmentation'] = np.nan
        
        # 10. 价格冲击 (Price Impact) - 去除上限
        if n_trades > 1:
            price_changes = np.diff(prices) / (prices[:-1] + 1e-10)
            # 标准化交易规模
            mean_size = np.mean(quantities) if np.mean(quantities) > 0 else 1.0
            trade_sizes_norm = quantities[1:] / mean_size
            if len(price_changes) > 0 and len(trade_sizes_norm) > 0:
                impact_values = abs(price_changes) * trade_sizes_norm
                features['price_impact'] = np.mean(impact_values)
            else:
                features['price_impact'] = 0.0
        else:
            features['price_impact'] = 0.0
        
        # 11. 交易间隔时间统计
        if n_trades > 1:
            time_diffs = np.diff(timestamps)  # 毫秒
            features['time_between_trades_avg'] = np.mean(time_diffs)
            features['time_between_trades_std'] = np.std(time_diffs) if len(time_diffs) > 1 else 0.0
        else:
            features['time_between_trades_avg'] = 0.0
            features['time_between_trades_std'] = 0.0
        
        # 12. 主导方成交量比例
        if total_volume > 0:
            features['dominant_side_volume_ratio'] = max(buy_volume, sell_volume) / total_volume
        else:
            features['dominant_side_volume_ratio'] = 0.5
        
        # 13. 微观价格趋势
        if n_trades > 2:
            # 使用线性回归斜率来衡量微观趋势
            time_indices = np.arange(n_trades)
            mean_price = np.mean(prices)
            if np.var(time_indices) > 0 and mean_price > 0:
                slope = np.cov(time_indices, prices)[0, 1] / np.var(time_indices)
                features['micro_price_trend'] = slope / mean_price
            else:
                features['micro_price_trend'] = 0.0
        else:
            features['micro_price_trend'] = 0.0
        
        # 14. 成交量加权tick方向
        if n_trades > 1 and total_volume > 0:
            tick_directions = np.sign(np.diff(prices))
            volume_weights = quantities[1:] / total_volume
            features['volume_weighted_tick_direction'] = np.sum(tick_directions * volume_weights)
        else:
            features['volume_weighted_tick_direction'] = 0.0
        
        # 15. 交易聚集系数 - 去除上限
        if n_trades > 2:
            time_diffs = np.diff(timestamps)
            mean_diff = np.mean(time_diffs)
            if mean_diff > 0:
                features['trade_clustering_coefficient'] = np.std(time_diffs) / mean_diff
            else:
                features['trade_clustering_coefficient'] = 0.0
        else:
            features['trade_clustering_coefficient'] = 0.0
        
        # 16. 价格回归强度
        if n_trades > 3 and total_volume > 0:
            # 计算价格相对于VWAP的回归倾向
            vwap = np.sum(prices * quantities) / total_volume
            price_deviations = prices - vwap
            if len(price_deviations) > 1:
                lag_deviations = price_deviations[:-1]
                current_deviations = price_deviations[1:]
                if np.var(lag_deviations) > 1e-10:
                    try:
                        reversion_coeff = np.cov(lag_deviations, current_deviations)[0, 1] / np.var(lag_deviations)
                        features['price_reversion_strength'] = -reversion_coeff  # 负相关表示回归
                    except:
                        features['price_reversion_strength'] = 0.0
                else:
                    features['price_reversion_strength'] = 0.0
            else:
                features['price_reversion_strength'] = 0.0
        else:
            features['price_reversion_strength'] = 0.0
        
        # 17. 订单簿压力代理指标
        if n_trades > 5:
            buy_timestamps = timestamps[is_buy_mask]
            sell_timestamps = timestamps[~is_buy_mask]
            
            if len(buy_timestamps) > 0 and len(sell_timestamps) > 0:
                total_time_span = timestamps[-1] - timestamps[0]
                if total_time_span > 0:
                    buy_time_span = buy_timestamps[-1] - buy_timestamps[0] if len(buy_timestamps) > 1 else 1
                    sell_time_span = sell_timestamps[-1] - sell_timestamps[0] if len(sell_timestamps) > 1 else 1
                    
                    buy_concentration = len(buy_timestamps) / max(buy_time_span, 1)
                    sell_concentration = len(sell_timestamps) / max(sell_time_span, 1)
                    
                    # 去除上限，保持原始差异
                    total_concentration = buy_concentration + sell_concentration
                    if total_concentration > 0:
                        features['order_book_pressure_proxy'] = abs(buy_concentration - sell_concentration) / total_concentration
                    else:
                        features['order_book_pressure_proxy'] = 0.0
                else:
                    features['order_book_pressure_proxy'] = 0.0
            else:
                features['order_book_pressure_proxy'] = 0.0
        else:
            features['order_book_pressure_proxy'] = 0.0
        
        return features
    
    def aggregate_to_kline_vectorized(self, df: pd.DataFrame, interval_ms: int) -> pd.DataFrame:
        """
        矢量化的K线聚合 - 高性能版本，包含无成交时间段
        修正了交易数量的计算逻辑，添加了更多特征，去除不必要的限制
        
        Args:
            df: aggtrades数据
            interval_ms: K线间隔(毫秒)
            
        Returns:
            K线数据DataFrame（包含无成交时间段的NaN数据）
        """
        if len(df) == 0:
            logger.warning("输入的aggtrades数据为空")
            return pd.DataFrame()
        
        logger.info(f"开始聚合K线数据，间隔: {interval_ms}ms")
        
        # 生成完整的时间序列 - 确保UTC日期边界对齐
        start_time = df['transact_time'].min()
        end_time = df['transact_time'].max()
        timeline_df = self.generate_complete_kline_timeline(start_time, end_time, interval_ms, 
                                                          ensure_daily_boundary=True)
        
        # 计算K线时间戳 - 矢量化操作
        df['kline_start_time'] = (df['transact_time'] // interval_ms) * interval_ms
        df['kline_end_time'] = df['kline_start_time'] + interval_ms - 1
        
        # 预分离买卖数据
        is_buy = ~df['is_buyer_maker']
        buy_mask = is_buy.values
        sell_mask = ~buy_mask
        
        logger.info(f"买入订单: {buy_mask.sum():,}, 卖出订单: {sell_mask.sum():,}")
        
        # 分组聚合 - 使用更安全的方式
        grouped = df.groupby('kline_start_time', sort=True)
        
        logger.info(f"生成 {len(grouped)} 个有效K线")
        
        try:
            # 使用一个循环来计算所有统计信息，避免复杂的DataFrame合并
            kline_data = []
            
            for kline_start_time, group in grouped:
                kline_end_time = kline_start_time + interval_ms - 1
                
                # 基本数据提取
                prices = group['price'].values
                quantities = group['quantity'].values
                amounts = group['amount'].values
                timestamps = group['transact_time'].values
                real_trade_counts = group['real_trade_count'].values
                
                first_trade_time = group['transact_time'].min()
                last_trade_time = group['transact_time'].max()
                trade_duration_ms = last_trade_time - first_trade_time
                
                # 基本OHLCV
                open_price = prices[0]
                high_price = prices.max()
                low_price = prices.min()
                close_price = prices[-1]
                volume = quantities.sum()
                amount = amounts.sum()
                
                # 修正：区分aggtrade数量和真实交易数量
                aggtrade_count = len(group)  # aggtrade记录数
                real_trade_count = real_trade_counts.sum()  # 真实交易数量
                
                first_agg_trade_id = group['agg_trade_id'].min()
                last_agg_trade_id = group['agg_trade_id'].max()
                first_trade_id = group['first_trade_id'].min()
                last_trade_id = group['last_trade_id'].max()
                
                # 买卖分离统计 - 基于真实交易数量
                group_idx = group.index
                buy_idx = group_idx[buy_mask[group_idx]]
                sell_idx = group_idx[sell_mask[group_idx]]
                
                # 买入统计
                if len(buy_idx) > 0:
                    buy_volume = df.loc[buy_idx, 'quantity'].sum()
                    buy_amount = df.loc[buy_idx, 'amount'].sum()
                    buy_aggtrade_count = len(buy_idx)  # 买入aggtrade数量
                    buy_real_trade_count = df.loc[buy_idx, 'real_trade_count'].sum()  # 买入真实交易数量
                else:
                    buy_volume = buy_amount = buy_aggtrade_count = buy_real_trade_count = 0
                
                # 卖出统计
                if len(sell_idx) > 0:
                    sell_volume = df.loc[sell_idx, 'quantity'].sum()
                    sell_amount = df.loc[sell_idx, 'amount'].sum()
                    sell_aggtrade_count = len(sell_idx)  # 卖出aggtrade数量
                    sell_real_trade_count = df.loc[sell_idx, 'real_trade_count'].sum()  # 卖出真实交易数量
                else:
                    sell_volume = sell_amount = sell_aggtrade_count = sell_real_trade_count = 0
                
                # 高级统计
                # VWAP
                total_amount = (prices * quantities).sum()
                total_quantity = quantities.sum()
                vwap = total_amount / total_quantity if total_quantity > 0 else prices[0]
                
                # 价格波动率
                if len(prices) > 1:
                    price_returns = np.diff(prices) / (prices[:-1] + 1e-10)  # 避免除零
                    price_volatility = np.std(price_returns) if len(price_returns) > 0 else 0.0
                else:
                    price_volatility = 0.0
                
                # 订单流不平衡
                total_vol = buy_volume + sell_volume
                order_flow_imbalance = (buy_volume - sell_volume) / total_vol if total_vol > 0 else 0.0
                
                # 其他统计
                price_range = high_price - low_price
                price_range_pct = (price_range / open_price) * 100 if open_price > 0 else 0
                
                # 修正：基于真实交易数量计算平均值
                avg_trade_size = total_quantity / real_trade_count if real_trade_count > 0 else 0
                avg_trade_amount = total_amount / real_trade_count if real_trade_count > 0 else 0
                
                # 大单小单统计 - 基于aggtrade的量（因为我们只能观察到aggtrade的大小）
                median_size = np.median(quantities) if len(quantities) > 0 else 0
                large_mask = quantities > median_size
                large_trade_volume = quantities[large_mask].sum()
                small_trade_volume = quantities[~large_mask].sum()
                large_trade_count = large_mask.sum()  # aggtrade count
                small_trade_count = (~large_mask).sum()  # aggtrade count
                large_trade_ratio = large_trade_volume / total_quantity if total_quantity > 0 else 0
                
                # 时间和市场统计
                trade_intensity = real_trade_count / max(trade_duration_ms, 1)  # 修正：使用真实交易数量
                buy_pressure = buy_volume / total_quantity if total_quantity > 0 else 0
                sell_pressure = sell_volume / total_quantity if total_quantity > 0 else 0
                price_trend = (close_price - open_price) / open_price if open_price > 0 else 0
                
                # 流动性得分 - 去除上限限制
                liquidity_score = total_quantity / max(price_volatility, 1e-10)  # 避免除零但不设上限
                
                # 数量加权价格
                quantity_weighted_price = (prices * quantities).sum() / total_quantity if total_quantity > 0 else close_price
                
                # 计算高级特征
                group_data = {
                    'prices': prices,
                    'quantities': quantities,
                    'amounts': amounts,
                    'timestamps': timestamps,
                    'is_buy_mask': buy_mask[group_idx],
                    'real_trade_counts': real_trade_counts
                }
                
                advanced_features = self.calculate_advanced_features(group_data)
                
                # 组装数据
                kline_row = {
                    'start_time': kline_start_time,
                    'end_time': kline_end_time,
                    'first_trade_time': first_trade_time,
                    'last_trade_time': last_trade_time,
                    'trade_duration_ms': trade_duration_ms,
                    'open': open_price,
                    'high': high_price,
                    'low': low_price,
                    'close': close_price,
                    'volume': volume,
                    'amount': amount,
                    'trade_count': real_trade_count,  # 修正：使用真实交易数量
                    'aggtrade_count': aggtrade_count,  # 新增：aggtrade记录数
                    'real_trade_count': real_trade_count,  # 明确标注
                    'buy_volume': buy_volume,
                    'sell_volume': sell_volume,
                    'buy_amount': buy_amount,
                    'sell_amount': sell_amount,
                    'buy_count': buy_real_trade_count,  # 修正：买入真实交易数量
                    'sell_count': sell_real_trade_count,  # 修正：卖出真实交易数量
                    'buy_aggtrade_count': buy_aggtrade_count,  # 新增：买入aggtrade数量
                    'sell_aggtrade_count': sell_aggtrade_count,  # 新增：卖出aggtrade数量
                    'vwap': vwap,
                    'price_volatility': price_volatility,
                    'order_flow_imbalance': order_flow_imbalance,
                    'price_range': price_range,
                    'price_range_pct': price_range_pct,
                    'avg_trade_size': avg_trade_size,
                    'avg_trade_amount': avg_trade_amount,
                    'max_trade_size': quantities.max() if len(quantities) > 0 else 0,
                    'min_trade_size': quantities.min() if len(quantities) > 0 else 0,
                    'large_trade_volume': large_trade_volume,
                    'small_trade_volume': small_trade_volume,
                    'large_trade_count': large_trade_count,
                    'small_trade_count': small_trade_count,
                    'large_trade_ratio': large_trade_ratio,
                    'quantity_weighted_price': quantity_weighted_price,
                    'trade_intensity': trade_intensity,
                    'buy_pressure': buy_pressure,
                    'sell_pressure': sell_pressure,
                    'price_trend': price_trend,
                    'liquidity_score': liquidity_score,
                    'first_agg_trade_id': first_agg_trade_id,
                    'last_agg_trade_id': last_agg_trade_id,
                    'first_trade_id': first_trade_id,
                    'last_trade_id': last_trade_id
                }
                
                # 添加高级特征
                kline_row.update(advanced_features)
                
                kline_data.append(kline_row)
            
            # 创建结果DataFrame
            result = pd.DataFrame(kline_data)
            
            logger.info(f"基础K线聚合完成，生成 {len(result)} 个K线")
            
            # 填充缺失的K线时间段（用NaN填充）
            complete_result = self.fill_missing_klines_with_nan(result, timeline_df)
            
            # 强制垃圾回收
            del grouped, result
            gc.collect()
            
            return complete_result
            
        except Exception as e:
            logger.error(f"K线聚合过程中出错: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            raise e
    
    def process_single_file_optimized(self, symbol: str, date_str: str, interval: str, 
                                    output_suffix: str = "kline") -> Tuple[bool, str, int, int]:
        """
        优化的单文件处理 - 确保UTC时间对齐
        
        Returns:
            (是否成功, 文件路径, 输入记录数, 输出K线数)
        """
        try:
            logger.info(f"开始处理 {symbol} {date_str} {interval}")
            
            # 输入文件路径
            input_file = self.data_root / symbol / "aggTrades" / f"{symbol}-aggTrades-{date_str}.parquet"
            
            if not input_file.exists():
                logger.error(f"文件不存在: {input_file}")
                return False, str(input_file), 0, 0
            
            # 输出目录和文件路径
            output_dir = self.data_root / symbol / f"aggTrades_{output_suffix}_{interval}"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{symbol}-{output_suffix}-{interval}-{date_str}.parquet"
            
            # 验证日期格式和UTC对齐
            self.validate_date_and_utc(date_str)
            
            # 加载数据
            df = self.load_aggtrades_data_optimized(input_file)
            if len(df) == 0:
                logger.warning(f"空数据文件: {input_file}")
                return False, str(input_file), 0, 0
            
            input_count = len(df)
            
            # 验证数据是否在正确的日期范围内
            self.validate_data_date_range(df, date_str)
            
            # 转换为K线
            interval_ms = self.get_interval_milliseconds(interval)
            logger.info(f"K线间隔: {interval_ms}ms")
            
            kline_df = self.aggregate_to_kline_vectorized(df, interval_ms)
            
            if len(kline_df) == 0:
                logger.warning(f"未生成K线数据: {input_file}")
                return False, str(input_file), input_count, 0
            
            output_count = len(kline_df)
            
            # 打印统计信息
            self.print_statistics(df, kline_df, interval)
            
            # 保存结果 - 使用压缩提高I/O效率
            logger.info(f"保存K线数据到: {output_file}")
            kline_df.to_parquet(
                output_file, 
                index=False, 
                engine='pyarrow',
                compression='snappy'
            )
            
            logger.info(f"成功处理完成: {symbol} {date_str}")
            
            # 清理内存
            del df, kline_df
            gc.collect()
            
            return True, str(output_file), input_count, output_count
            
        except Exception as e:
            logger.error(f"处理文件失败 {symbol} {date_str}: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return False, f"{symbol}-{date_str}", 0, 0
    
    def validate_date_and_utc(self, date_str: str):
        """验证日期格式并确保UTC处理"""
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            logger.info(f"处理日期: {date_str} (UTC)")
        except ValueError as e:
            raise ValueError(f"日期格式错误: {date_str}, 应为 YYYY-MM-DD")
    
    def validate_data_date_range(self, df: pd.DataFrame, date_str: str):
        """验证数据是否在指定的UTC日期范围内"""
        if len(df) == 0:
            return
        
        # 目标日期的UTC时间范围
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
        day_start_utc = target_date.replace(tzinfo=timezone.utc)
        day_end_utc = day_start_utc.replace(hour=23, minute=59, second=59, microsecond=999000)
        
        day_start_ms = int(day_start_utc.timestamp() * 1000)
        day_end_ms = int(day_end_utc.timestamp() * 1000)
        
        # 检查数据的实际时间范围
        min_time = df['transact_time'].min()
        max_time = df['transact_time'].max()
        
        min_dt = datetime.fromtimestamp(min_time / 1000, tz=timezone.utc)
        max_dt = datetime.fromtimestamp(max_time / 1000, tz=timezone.utc)
        
        logger.info(f"目标日期范围: {date_str} 00:00:00 到 {date_str} 23:59:59 UTC")
        logger.info(f"实际数据范围: {min_dt.strftime('%Y-%m-%d %H:%M:%S')} 到 {max_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        # 检查是否有数据超出目标日期范围
        out_of_range = (df['transact_time'] < day_start_ms) | (df['transact_time'] > day_end_ms)
        out_of_range_count = out_of_range.sum()
        
        if out_of_range_count > 0:
            logger.warning(f"发现 {out_of_range_count} 条数据超出目标日期范围")
            
            # 显示一些超出范围的样本
            out_of_range_data = df[out_of_range]['transact_time'].head(5)
            for ts in out_of_range_data:
                dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                logger.warning(f"  超出范围时间: {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        else:
            logger.info("✓ 所有数据都在目标UTC日期范围内")
    
    def print_statistics(self, aggtrades_df: pd.DataFrame, kline_df: pd.DataFrame, interval: str):
        """打印统计信息，包括时间验证和修正后的交易数量统计"""
        logger.info("=" * 50)
        logger.info("数据转换统计:")
        logger.info(f"原始aggtrades记录数: {len(aggtrades_df):,}")
        
        if len(aggtrades_df) > 0:
            # 显示原始数据的时间范围
            min_time = aggtrades_df['transact_time'].min()
            max_time = aggtrades_df['transact_time'].max()
            
            min_dt = datetime.fromtimestamp(min_time / 1000, tz=timezone.utc)
            max_dt = datetime.fromtimestamp(max_time / 1000, tz=timezone.utc)
            
            logger.info(f"原始数据时间范围: {min_dt.strftime('%Y-%m-%d %H:%M:%S')} 到 {max_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            
            # 显示aggtrades vs 真实交易数量的对比
            total_real_trades = aggtrades_df['real_trade_count'].sum()
            avg_real_trades_per_aggtrade = aggtrades_df['real_trade_count'].mean()
            logger.info(f"总真实交易数量: {total_real_trades:,}")
            logger.info(f"平均每aggtrade包含真实交易: {avg_real_trades_per_aggtrade:.2f}")
            logger.info(f"数据压缩比 (aggtrades:真实交易): 1:{avg_real_trades_per_aggtrade:.1f}")
        
        if len(kline_df) > 0:
            # 统计信息 - 区分有效和空K线
            valid_klines = kline_df['volume'].notna() & (kline_df['volume'] > 0)
            valid_count = valid_klines.sum()
            empty_count = len(kline_df) - valid_count
            
            logger.info(f"K线统计 - 总计: {len(kline_df)}, 有成交: {valid_count}, 无成交: {empty_count}")
            logger.info(f"K线间隔: {interval}")
            
            # 显示K线的时间范围
            min_kline_time = kline_df['start_time'].min()
            max_kline_time = kline_df['start_time'].max()
            
            min_kline_dt = datetime.fromtimestamp(min_kline_time / 1000, tz=timezone.utc)
            max_kline_dt = datetime.fromtimestamp(max_kline_time / 1000, tz=timezone.utc)
            
            logger.info(f"K线时间范围: {min_kline_dt.strftime('%Y-%m-%d %H:%M:%S')} 到 {max_kline_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            
            if valid_count > 0:
                valid_data = kline_df[valid_klines]
                
                # 修正后的统计信息
                total_aggtrades = valid_data['aggtrade_count'].sum()
                total_real_trades = valid_data['real_trade_count'].sum()
                
                logger.info(f"平均每根K线包含aggtrades: {total_aggtrades / valid_count:.1f}")
                logger.info(f"平均每根K线包含真实交易: {total_real_trades / valid_count:.1f}")
                logger.info(f"K线级别压缩比 (aggtrades:真实交易): 1:{(total_real_trades / total_aggtrades):.1f}")
                
                logger.info(f"价格范围: {valid_data['low'].min():.8f} - {valid_data['high'].max():.8f}")
                logger.info(f"总成交量: {valid_data['volume'].sum():.2f}")
                logger.info(f"总成交额: {valid_data['amount'].sum():.2f}")
                
                buy_vol_total = valid_data['buy_volume'].sum()
                total_vol = valid_data['volume'].sum()
                if total_vol > 0:
                    logger.info(f"买入占比: {(buy_vol_total / total_vol * 100):.1f}%")
                
                # 新增特征统计
                if 'price_momentum' in valid_data.columns:
                    pm_mean = valid_data['price_momentum'].mean()
                    pm_std = valid_data['price_momentum'].std()
                    logger.info(f"价格动量: 均值={pm_mean:.6f}, 标准差={pm_std:.6f}")
                    
                if 'order_imbalance_strength' in valid_data.columns:
                    ois_mean = valid_data['order_imbalance_strength'].mean()
                    ois_max = valid_data['order_imbalance_strength'].max()
                    logger.info(f"订单不平衡强度: 均值={ois_mean:.4f}, 最大值={ois_max:.4f}")
                    
                if 'aggtrade_fragmentation' in valid_data.columns:
                    af_mean = valid_data['aggtrade_fragmentation'].mean()
                    af_max = valid_data['aggtrade_fragmentation'].max()
                    logger.info(f"aggtrade碎片化程度: 均值={af_mean:.2f}, 最大值={af_max:.2f}")
                
                if 'liquidity_score' in valid_data.columns:
                    ls_mean = valid_data['liquidity_score'].mean()
                    ls_max = valid_data['liquidity_score'].max()
                    logger.info(f"流动性得分: 均值={ls_mean:.2f}, 最大值={ls_max:.2f} (无上限限制)")
                
                # 验证时间连续性
                if len(kline_df) > 1:
                    interval_ms = self.get_interval_milliseconds(interval)
                    time_diffs = kline_df['start_time'].diff().dropna()
                    expected_diff = interval_ms
                    
                    correct_intervals = (time_diffs == expected_diff).sum()
                    total_intervals = len(time_diffs)
                    
                    logger.info(f"时间连续性检查: {correct_intervals}/{total_intervals} 个间隔正确")
                    
                    if correct_intervals != total_intervals:
                        logger.warning("存在时间间隔不正确的K线")
            else:
                logger.info("所有K线时间段都无成交数据")
        
        logger.info("=" * 50)


def process_file_worker(args):
    """工作进程函数"""
    symbol, date_str, interval, output_suffix, data_root = args
    converter = AggtradesToKlineConverter(data_root, n_jobs=1)  # 子进程使用单线程
    return converter.process_single_file_optimized(symbol, date_str, interval, output_suffix)


class HighPerformanceConverter(AggtradesToKlineConverter):
    """高性能转换器 - 支持并行处理"""
    
    def process_multiple_files_parallel(self, tasks: List[Tuple], interval: str, 
                                      output_suffix: str = "kline") -> Dict[str, Any]:
        """
        并行处理多个文件
        
        Args:
            tasks: [(symbol, date_str), ...] 任务列表
            interval: K线间隔
            output_suffix: 输出文件夹后缀
            
        Returns:
            处理结果统计
        """
        if not tasks:
            return {"success": 0, "total": 0, "failed": []}
        
        logger.info(f"开始并行处理 {len(tasks)} 个文件，使用 {self.n_jobs} 个进程")
        start_time = time.time()
        
        # 准备任务参数
        task_args = [(symbol, date_str, interval, output_suffix, str(self.data_root)) 
                     for symbol, date_str in tasks]
        
        results = []
        failed_tasks = []
        total_input_records = 0
        total_output_klines = 0
        
        # 使用进程池并行处理
        with ProcessPoolExecutor(max_workers=self.n_jobs) as executor:
            # 提交所有任务
            future_to_task = {
                executor.submit(process_file_worker, task_arg): task_arg 
                for task_arg in task_args
            }
            
            # 处理完成的任务
            completed = 0
            for future in as_completed(future_to_task):
                task_arg = future_to_task[future]
                symbol, date_str = task_arg[0], task_arg[1]
                completed += 1
                
                try:
                    success, output_path, input_count, output_count = future.result()
                    if success:
                        results.append((symbol, date_str, output_path, input_count, output_count))
                        total_input_records += input_count
                        total_output_klines += output_count
                    else:
                        failed_tasks.append((symbol, date_str, "处理失败"))
                        
                except Exception as e:
                    failed_tasks.append((symbol, date_str, str(e)))
                
                # 进度日志
                if completed % max(1, len(tasks) // 10) == 0:
                    progress = completed / len(tasks) * 100
                    elapsed = time.time() - start_time
                    eta = elapsed * (len(tasks) - completed) / completed if completed > 0 else 0
                    logger.info(f"进度: {completed}/{len(tasks)} ({progress:.1f}%), "
                               f"用时: {elapsed:.1f}s, 预计剩余: {eta:.1f}s")
        
        elapsed_time = time.time() - start_time
        success_count = len(results)
        
        # 统计结果
        stats = {
            "success": success_count,
            "total": len(tasks),
            "failed": failed_tasks,
            "success_rate": (success_count / len(tasks)) * 100 if tasks else 0,
            "total_time": elapsed_time,
            "avg_time_per_file": elapsed_time / len(tasks) if tasks else 0,
            "total_input_records": total_input_records,
            "total_output_klines": total_output_klines,
            "compression_ratio": total_input_records / total_output_klines if total_output_klines > 0 else 0
        }
        
        logger.info(f"\n{'='*60}")
        logger.info("批量处理完成统计:")
        logger.info(f"总文件数: {stats['total']}")
        logger.info(f"成功处理: {stats['success']} ({stats['success_rate']:.1f}%)")
        logger.info(f"失败处理: {len(failed_tasks)}")
        logger.info(f"总耗时: {stats['total_time']:.1f}秒")
        logger.info(f"平均每文件耗时: {stats['avg_time_per_file']:.2f}秒")
        logger.info(f"处理速度: {stats['total']/(stats['total_time']/60):.1f} 文件/分钟")
        logger.info(f"总输入记录: {stats['total_input_records']:,}")
        logger.info(f"总输出K线: {stats['total_output_klines']:,}")
        if stats['compression_ratio'] > 0:
            logger.info(f"压缩比: {stats['compression_ratio']:.1f}:1")
        logger.info(f"{'='*60}")
        
        if failed_tasks:
            logger.warning(f"失败的任务:")
            for symbol, date_str, error in failed_tasks[:10]:
                logger.warning(f"  {symbol} {date_str}: {error}")
            if len(failed_tasks) > 10:
                logger.warning(f"  ... 还有 {len(failed_tasks)-10} 个失败任务")
        
        return stats
    
    def process_date_range_parallel(self, symbols: list, start_date: str, end_date: str, 
                                  interval: str, output_suffix: str = "kline"):
        """并行处理日期范围"""
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        # 生成所有任务
        tasks = []
        current_dt = start_dt
        while current_dt <= end_dt:
            date_str = current_dt.strftime("%Y-%m-%d")
            for symbol in symbols:
                tasks.append((symbol, date_str))
            current_dt += timedelta(days=1)
        
        logger.info(f"准备处理 {len(symbols)} 个交易对, 日期范围: {start_date} 到 {end_date}")
        logger.info(f"总任务数: {len(tasks)}")
        
        return self.process_multiple_files_parallel(tasks, interval, output_suffix)
    
    def process_multiple_symbols_single_date_parallel(self, symbols: list, date: str, 
                                                    interval: str, output_suffix: str = "kline"):
        """并行处理多个交易对的单日数据"""
        tasks = [(symbol, date) for symbol in symbols]
        
        logger.info(f"准备并行处理 {len(symbols)} 个交易对的单日数据: {date}")
        
        return self.process_multiple_files_parallel(tasks, interval, output_suffix)


def main():
    parser = argparse.ArgumentParser(description="将Binance aggtrades数据转换为K线数据 - 高性能版本（修正交易数量计算，去除上下限限制）")
    parser.add_argument("--data_root", default="./data", help="数据根目录")
    parser.add_argument("--symbol", help="单个交易对符号，如 ETHUSDT")
    parser.add_argument("--symbols", nargs='+', help="多个交易对符号，如 ETHUSDT BTCUSDT ADAUSDT")
    parser.add_argument("--symbols_file", help="包含交易对列表的文件路径（每行一个交易对）")
    parser.add_argument("--date", help="单个日期 (YYYY-MM-DD)")
    parser.add_argument("--start_date", help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end_date", help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--interval", default="1s", help="K线间隔，如 1s, 5s, 1m")
    parser.add_argument("--output_suffix", default="kline", help="输出文件夹后缀")
    parser.add_argument("--n_jobs", type=int, help="并行进程数，默认自动检测")
    parser.add_argument("--use_parallel", action='store_true', default=True, help="使用并行处理（默认开启）")
    
    args = parser.parse_args()
    
    # 确定要处理的交易对列表
    symbols = []
    if args.symbol:
        symbols = [args.symbol]
    elif args.symbols:
        symbols = args.symbols
    elif args.symbols_file:
        try:
            with open(args.symbols_file, 'r') as f:
                symbols = [line.strip() for line in f if line.strip()]
            logger.info(f"从文件 {args.symbols_file} 读取到 {len(symbols)} 个交易对")
        except Exception as e:
            logger.error(f"读取交易对文件失败: {e}")
            return
    else:
        logger.error("请指定交易对: --symbol 或 --symbols 或 --symbols_file")
        return
    
    if not symbols:
        logger.error("未找到要处理的交易对")
        return
    
    logger.info(f"将要处理的交易对: {symbols}")
    
    # 选择转换器
    if args.use_parallel and len(symbols) > 1:
        converter = HighPerformanceConverter(args.data_root, args.n_jobs)
    else:
        converter = AggtradesToKlineConverter(args.data_root, args.n_jobs)
    
    if args.date:
        # 处理单个日期
        if len(symbols) == 1:
            success, output_path, input_count, output_count = converter.process_single_file_optimized(
                symbols[0], args.date, args.interval, args.output_suffix)
            if success:
                logger.info(f"成功处理: {output_path}")
                logger.info(f"输入记录: {input_count:,}, 输出K线: {output_count:,}")
            else:
                logger.error(f"处理失败: {symbols[0]} {args.date}")
        else:
            if isinstance(converter, HighPerformanceConverter):
                converter.process_multiple_symbols_single_date_parallel(
                    symbols, args.date, args.interval, args.output_suffix)
            else:
                # 单进程处理
                for symbol in symbols:
                    success, output_path, input_count, output_count = converter.process_single_file_optimized(
                        symbol, args.date, args.interval, args.output_suffix)
                    if success:
                        logger.info(f"成功处理: {symbol} {args.date}")
                    else:
                        logger.error(f"处理失败: {symbol} {args.date}")
    elif args.start_date and args.end_date:
        # 处理日期范围
        if isinstance(converter, HighPerformanceConverter):
            converter.process_date_range_parallel(
                symbols, args.start_date, args.end_date, args.interval, args.output_suffix)
        else:
            # 单进程处理
            logger.warning("建议使用并行处理提高性能")
            start_dt = datetime.strptime(args.start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(args.end_date, "%Y-%m-%d")
            
            for symbol in symbols:
                current_dt = start_dt
                while current_dt <= end_dt:
                    date_str = current_dt.strftime("%Y-%m-%d")
                    success, output_path, input_count, output_count = converter.process_single_file_optimized(
                        symbol, date_str, args.interval, args.output_suffix)
                    if success:
                        logger.info(f"成功处理: {symbol} {date_str}")
                    else:
                        logger.error(f"处理失败: {symbol} {date_str}")
                    current_dt += timedelta(days=1)
    else:
        logger.error("请指定 --date 或者 --start_date 和 --end_date")
        return


if __name__ == "__main__":
    main()


"""
使用示例 - 完整版高性能K线转换器，修正交易数量计算，去除上下限限制:

主要改进:
1. 修正了交易数量计算逻辑 - 区分aggtrade数量和真实交易数量
2. 新增17个高级特征，基于aggtrades数据，严格避免未来函数
3. 去除了不必要的上下限限制，让特征值自然分布
4. 提高代码可读性和可扩展性
5. 保留原有的并行化处理和NaN填充功能

去除的上下限限制:
- liquidity_score: 从 min(liquidity_score, 1e6) 改为无上限
- 各种比率和强度指标: 不再人为限制在[0,1]区间
- 时间和价格相关指标: 保持原始数值范围

修正的交易数量字段:
- trade_count: 现在使用真实交易数量 (last_trade_id - first_trade_id + 1)
- aggtrade_count: 新增，表示aggtrade记录数
- real_trade_count: 明确标注的真实交易数量
- buy_count/sell_count: 现在基于真实交易数量
- buy_aggtrade_count/sell_aggtrade_count: 新增，买卖aggtrade数量

新增的17个特征 (严格避免未来函数):
1. price_momentum: 价格动量
2. trade_size_variance: 交易规模方差
3. price_acceleration: 价格加速度（二阶差分）
4. volume_momentum: 成交量动量
5. order_imbalance_strength: 订单不平衡强度（改进版本）
6. price_efficiency: 价格效率（价格发现效率）
7. tick_direction_entropy: 成交方向熵
8. avg_aggtrade_real_trades: 平均每aggtrade包含的真实交易数
9. max_aggtrade_real_trades: 最大aggtrade包含的真实交易数
10. min_aggtrade_real_trades: 最小aggtrade包含的真实交易数
11. aggtrade_fragmentation: aggtrade碎片化程度
12. price_impact: 价格冲击
13. time_between_trades_avg: 交易间隔平均时间
14. time_between_trades_std: 交易间隔时间标准差
15. dominant_side_volume_ratio: 主导方成交量比例
16. micro_price_trend: 微观价格趋势
17. volume_weighted_tick_direction: 成交量加权tick方向
18. trade_clustering_coefficient: 交易聚集系数
19. price_reversion_strength: 价格回归强度
20. order_book_pressure_proxy: 订单簿压力代理指标

使用示例:

# 单个交易对
python improved_kline_converter.py --symbol ETHUSDT --date 2024-12-31 --interval 1s

# 多个交易对并行处理
python improved_kline_converter.py --symbols ETHUSDT BTCUSDT ADAUSDT --date 2024-12-31 --interval 1s --n_jobs 4

# 日期范围批量处理
python improved_kline_converter.py --symbols ETHUSDT BTCUSDT --start_date 2024-12-01 --end_date 2024-12-31 --interval 5s

# 从文件读取交易对列表
python improved_kline_converter.py --symbols_file symbols.txt --start_date 2024-12-01 --end_date 2024-12-31 --interval 1m

# 不同时间间隔示例
python improved_kline_converter.py --symbol BTCUSDT --date 2024-12-31 --interval 100ms
python improved_kline_converter.py --symbol BTCUSDT --date 2024-12-31 --interval 3s
python improved_kline_converter.py --symbol BTCUSDT --date 2024-12-31 --interval 5m
python improved_kline_converter.py --symbol BTCUSDT --date 2024-12-31 --interval 1h

注意事项:
1. 所有特征都基于当前K线内的历史数据，严格避免未来函数
2. 去除了上下限限制，特征值将保持自然分布范围
3. 修正了交易数量计算，现在能正确区分aggtrade数量和真实交易数量
4. 保持64位精度和UTC时间对齐
5. 无成交时间段用NaN填充，保持时间序列完整性
6. 增强的错误处理和异常情况处理
7. 详细的统计信息输出，便于数据质量监控

代码特点:
- 完整可运行，无需额外修改
- 高性能并行处理
- 内存优化和垃圾回收
- 详细的日志输出
- 鲁棒的错误处理
- 模块化设计，易于扩展新特征
"""