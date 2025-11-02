"""
因子评测主程序（优化版）
提供完整的因子评测流程，支持并行处理加速
"""

import pandas as pd
import numpy as np
import yaml
import os
from pathlib import Path
from typing import Dict, List, Tuple
import warnings
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from tqdm import tqdm
warnings.filterwarnings('ignore')

from evaluators.ic_evaluator import ICEvaluator
from evaluators.quantile_evaluator import QuantileEvaluator
from evaluators.decay_evaluator import DecayEvaluator
from evaluators.statistics_evaluator import StatisticsEvaluator
from utils.data_loader import DataLoader
from utils.preprocessor import Preprocessor
from reports.report_generator import ReportGenerator


class FactorEvaluationPipeline:
    """因子评测管道（优化版）"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """初始化评测管道"""
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.data_loader = DataLoader(self.config)
        self.preprocessor = Preprocessor(self.config)
        
        # 初始化各个评估器
        self.ic_evaluator = ICEvaluator(self.config)
        self.quantile_evaluator = QuantileEvaluator(self.config)
        self.decay_evaluator = DecayEvaluator(self.config)
        self.stats_evaluator = StatisticsEvaluator(self.config)
        
        self.report_generator = ReportGenerator(self.config)
        
        # 创建输出目录
        output_dir = Path(self.config['paths']['output_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 并行配置
        self.n_jobs = self.config.get('performance', {}).get('n_jobs', 4)
        self.use_parallel = self.config.get('performance', {}).get('enable_parallel', True)
        
        print(f"🚀 初始化完成")
        print(f"   - 并行处理: {'启用' if self.use_parallel else '禁用'}")
        if self.use_parallel:
            print(f"   - 进程数: {self.n_jobs}")
    
    def run_evaluation(self) -> Dict:
        """运行完整评测流程"""
        total_start = time.time()
        
        print("\n" + "="*80)
        print("🎯 开始因子评测流程")
        print("="*80)
        
        all_results = {}
        
        # 遍历每个合约
        for idx, symbol in enumerate(self.config['symbols'], 1):
            symbol_start = time.time()
            
            print(f"\n{'='*80}")
            print(f"📊 [{idx}/{len(self.config['symbols'])}] 处理合约: {symbol}")
            print(f"{'='*80}")
            
            # 1. 加载数据
            print("\n⏳ [1/6] 加载数据...")
            load_start = time.time()
            factors_df, returns_df = self.data_loader.load_data(symbol)
            
            if factors_df is None or returns_df is None:
                print(f"   ❌ {symbol} 数据加载失败，跳过")
                continue
            
            print(f"   ✅ 加载完成 (耗时: {time.time()-load_start:.2f}s)")
            print(f"   📦 因子数据: {factors_df.shape}")
            print(f"   📈 收益率数据: {returns_df.shape}")
            
            # 2. 数据预处理
            print("\n⏳ [2/6] 数据预处理...")
            preprocess_start = time.time()
            factors_df, returns_df = self.preprocessor.preprocess(factors_df, returns_df)
            print(f"   ✅ 预处理完成 (耗时: {time.time()-preprocess_start:.2f}s)")
            print(f"   📦 预处理后因子: {factors_df.shape}")
            print(f"   📈 预处理后收益: {returns_df.shape}")
            
            # 3. 并行评估
            if self.use_parallel and len(factors_df.columns) > 10:
                symbol_results = self._parallel_evaluate(factors_df, returns_df, symbol)
            else:
                symbol_results = self._sequential_evaluate(factors_df, returns_df)
            
            # 添加原始数据
            symbol_results['raw_data'] = {
                'factors': factors_df,
                'returns': returns_df
            }
            
            all_results[symbol] = symbol_results
            
            symbol_time = time.time() - symbol_start
            print(f"\n✅ {symbol} 评测完成 (总耗时: {symbol_time:.2f}s)")
        
        # 7. 生成报告
        print("\n" + "="*80)
        print("📝 [7/7] 生成评测报告...")
        print("="*80)
        report_start = time.time()
        self.report_generator.generate_reports(all_results)
        print(f"✅ 报告生成完成 (耗时: {time.time()-report_start:.2f}s)")
        
        total_time = time.time() - total_start
        print("\n" + "="*80)
        print(f"🎉 全部评测完成!")
        print(f"⏱️  总耗时: {total_time:.2f}s ({total_time/60:.2f}min)")
        print(f"📁 结果保存在: {self.config['paths']['output_dir']}")
        print("="*80)
        
        return all_results
    
    def _sequential_evaluate(self, factors_df: pd.DataFrame, returns_df: pd.DataFrame) -> Dict:
        """顺序评估（用于因子数量较少时）"""
        # 3. IC分析
        print("\n⏳ [3/6] IC分析...")
        ic_start = time.time()
        ic_results = {}
        
        with tqdm(total=len(factors_df.columns), desc="   IC分析进度") as pbar:
            for factor_name in factors_df.columns:
                factor_ic = {}
                for return_name in returns_df.columns:
                    ic_stats = self.ic_evaluator._calculate_ic(
                        factors_df[factor_name],
                        returns_df[return_name]
                    )
                    factor_ic[return_name] = ic_stats
                ic_results[factor_name] = factor_ic
                pbar.update(1)
        
        print(f"   ✅ IC分析完成 (耗时: {time.time()-ic_start:.2f}s)")
        
        # 4. 分组回测分析
        print("\n⏳ [4/6] 分组回测分析...")
        quantile_start = time.time()
        quantile_results = {}
        
        with tqdm(total=len(factors_df.columns), desc="   分组分析进度") as pbar:
            for factor_name in factors_df.columns:
                factor_quantile = {}
                for return_name in returns_df.columns:
                    quantile_stats = self.quantile_evaluator._quantile_analysis(
                        factors_df[factor_name],
                        returns_df[return_name]
                    )
                    factor_quantile[return_name] = quantile_stats
                quantile_results[factor_name] = factor_quantile
                pbar.update(1)
        
        print(f"   ✅ 分组分析完成 (耗时: {time.time()-quantile_start:.2f}s)")
        
        # 5. 因子衰减分析
        print("\n⏳ [5/6] 因子衰减分析...")
        decay_start = time.time()
        decay_results = {}
        
        with tqdm(total=len(factors_df.columns), desc="   衰减分析进度") as pbar:
            for factor_name in factors_df.columns:
                decay_stats = self.decay_evaluator._analyze_decay(
                    factors_df[factor_name],
                    returns_df
                )
                decay_results[factor_name] = decay_stats
                pbar.update(1)
        
        print(f"   ✅ 衰减分析完成 (耗时: {time.time()-decay_start:.2f}s)")
        
        # 6. 统计特性分析
        print("\n⏳ [6/6] 统计特性分析...")
        stats_start = time.time()
        stats_results = {}
        
        with tqdm(total=len(factors_df.columns), desc="   统计分析进度") as pbar:
            for factor_name in factors_df.columns:
                stats = self.stats_evaluator._calculate_statistics(factors_df[factor_name])
                stats_results[factor_name] = stats
                pbar.update(1)
        
        print(f"   ✅ 统计分析完成 (耗时: {time.time()-stats_start:.2f}s)")
        
        return {
            'ic': ic_results,
            'quantile': quantile_results,
            'decay': decay_results,
            'statistics': stats_results,
        }
    
    def _parallel_evaluate(self, factors_df: pd.DataFrame, returns_df: pd.DataFrame, symbol: str) -> Dict:
        """并行评估（用于因子数量较多时）"""
        print(f"\n   💡 使用并行处理加速 (因子数: {len(factors_df.columns)})")
        
        factor_names = factors_df.columns.tolist()
        
        # 3. 并行IC分析
        print("\n⏳ [3/6] IC分析 (并行)...")
        ic_start = time.time()
        ic_results = self._parallel_ic_analysis(factors_df, returns_df, factor_names)
        print(f"   ✅ IC分析完成 (耗时: {time.time()-ic_start:.2f}s, 加速比: ~{len(factor_names)/max(1,time.time()-ic_start):.1f}x)")
        
        # 4. 并行分组分析
        print("\n⏳ [4/6] 分组回测分析 (并行)...")
        quantile_start = time.time()
        quantile_results = self._parallel_quantile_analysis(factors_df, returns_df, factor_names)
        print(f"   ✅ 分组分析完成 (耗时: {time.time()-quantile_start:.2f}s)")
        
        # 5. 并行衰减分析
        print("\n⏳ [5/6] 因子衰减分析 (并行)...")
        decay_start = time.time()
        decay_results = self._parallel_decay_analysis(factors_df, returns_df, factor_names)
        print(f"   ✅ 衰减分析完成 (耗时: {time.time()-decay_start:.2f}s)")
        
        # 6. 统计分析（较快，不需要并行）
        print("\n⏳ [6/6] 统计特性分析...")
        stats_start = time.time()
        stats_results = {}
        with tqdm(total=len(factor_names), desc="   统计分析进度") as pbar:
            for factor_name in factor_names:
                stats_results[factor_name] = self.stats_evaluator._calculate_statistics(factors_df[factor_name])
                pbar.update(1)
        print(f"   ✅ 统计分析完成 (耗时: {time.time()-stats_start:.2f}s)")
        
        return {
            'ic': ic_results,
            'quantile': quantile_results,
            'decay': decay_results,
            'statistics': stats_results,
        }
    
    def _parallel_ic_analysis(self, factors_df: pd.DataFrame, returns_df: pd.DataFrame, factor_names: List[str]) -> Dict:
        """并行IC分析"""
        ic_results = {}
        
        with ProcessPoolExecutor(max_workers=self.n_jobs) as executor:
            futures = {}
            
            for factor_name in factor_names:
                future = executor.submit(
                    _evaluate_factor_ic,
                    factors_df[factor_name],
                    returns_df,
                    self.config
                )
                futures[future] = factor_name
            
            with tqdm(total=len(futures), desc="   IC分析进度") as pbar:
                for future in as_completed(futures):
                    factor_name = futures[future]
                    try:
                        ic_results[factor_name] = future.result()
                    except Exception as e:
                        print(f"\n   ⚠️  {factor_name} IC计算失败: {e}")
                        ic_results[factor_name] = {}
                    pbar.update(1)
        
        return ic_results
    
    def _parallel_quantile_analysis(self, factors_df: pd.DataFrame, returns_df: pd.DataFrame, factor_names: List[str]) -> Dict:
        """并行分组分析"""
        quantile_results = {}
        
        with ProcessPoolExecutor(max_workers=self.n_jobs) as executor:
            futures = {}
            
            for factor_name in factor_names:
                future = executor.submit(
                    _evaluate_factor_quantile,
                    factors_df[factor_name],
                    returns_df,
                    self.config
                )
                futures[future] = factor_name
            
            with tqdm(total=len(futures), desc="   分组分析进度") as pbar:
                for future in as_completed(futures):
                    factor_name = futures[future]
                    try:
                        quantile_results[factor_name] = future.result()
                    except Exception as e:
                        print(f"\n   ⚠️  {factor_name} 分组计算失败: {e}")
                        quantile_results[factor_name] = {}
                    pbar.update(1)
        
        return quantile_results
    
    def _parallel_decay_analysis(self, factors_df: pd.DataFrame, returns_df: pd.DataFrame, factor_names: List[str]) -> Dict:
        """并行衰减分析"""
        decay_results = {}
        
        with ProcessPoolExecutor(max_workers=self.n_jobs) as executor:
            futures = {}
            
            for factor_name in factor_names:
                future = executor.submit(
                    _evaluate_factor_decay,
                    factors_df[factor_name],
                    returns_df,
                    self.config
                )
                futures[future] = factor_name
            
            with tqdm(total=len(futures), desc="   衰减分析进度") as pbar:
                for future in as_completed(futures):
                    factor_name = futures[future]
                    try:
                        decay_results[factor_name] = future.result()
                    except Exception as e:
                        print(f"\n   ⚠️  {factor_name} 衰减计算失败: {e}")
                        decay_results[factor_name] = {}
                    pbar.update(1)
        
        return decay_results


# 全局函数用于并行处理
def _evaluate_factor_ic(factor: pd.Series, returns_df: pd.DataFrame, config: dict) -> Dict:
    """评估单个因子的IC（用于并行）"""
    evaluator = ICEvaluator(config)
    results = {}
    for return_name in returns_df.columns:
        results[return_name] = evaluator._calculate_ic(factor, returns_df[return_name])
    return results


def _evaluate_factor_quantile(factor: pd.Series, returns_df: pd.DataFrame, config: dict) -> Dict:
    """评估单个因子的分组（用于并行）"""
    evaluator = QuantileEvaluator(config)
    results = {}
    for return_name in returns_df.columns:
        results[return_name] = evaluator._quantile_analysis(factor, returns_df[return_name])
    return results


def _evaluate_factor_decay(factor: pd.Series, returns_df: pd.DataFrame, config: dict) -> Dict:
    """评估单个因子的衰减（用于并行）"""
    evaluator = DecayEvaluator(config)
    return evaluator._analyze_decay(factor, returns_df)


def main():
    """主函数"""
    # 创建评测管道
    pipeline = FactorEvaluationPipeline("config.yaml")
    
    # 运行评测
    results = pipeline.run_evaluation()
    
    return results


if __name__ == "__main__":
    main()