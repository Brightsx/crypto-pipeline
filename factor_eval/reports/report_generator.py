"""
reports/report_generator.py
报告生成器
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm

import warnings
warnings.filterwarnings('ignore')


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.output_config = config['output']
        self.output_dir = Path(config['paths']['output_dir'])
        
        # Set plot style with English fonts
        plt.style.use('seaborn-v0_8-darkgrid')
        sns.set_palette("husl")
        
        # Ensure English output, avoid Chinese character issues
        plt.rcParams['font.family'] = 'DejaVu Sans'
        plt.rcParams['axes.unicode_minus'] = False  # Fix minus sign display
    
    def generate_reports(self, all_results: Dict):
        """
        生成所有报告
        
        Args:
            all_results: 所有合约的评测结果
        """
        # 1. 生成综合摘要CSV
        if self.output_config['generate_summary_csv']:
            self._generate_summary_csv(all_results)
        
        # 2. 生成详细HTML报告
        if self.output_config['generate_detailed_html']:
            self._generate_html_reports(all_results)
        
        # 3. 生成可视化图表
        if self.output_config['generate_plots']:
            self._generate_plots(all_results)
        
        # 4. 生成IC时间序列
        if self.output_config['generate_ic_timeseries']:
            self._save_ic_timeseries(all_results)
    
    def _generate_summary_csv(self, all_results: Dict):
        """生成综合摘要CSV"""
        print("   📄 生成综合摘要...")
        
        summary_rows = []
        total_combinations = sum(
            len(results['ic']) * len(list(results['ic'].values())[0]) 
            if results['ic'] else 0
            for results in all_results.values()
        )
        
        with tqdm(total=total_combinations, desc="   处理进度") as pbar:
            for symbol, results in all_results.items():
                ic_results = results['ic']
                quantile_results = results['quantile']
                decay_results = results['decay']
                stats_results = results['statistics']
                
                for factor_name in ic_results.keys():
                    # 对每个因子-收益率对生成一行摘要
                    for return_name in ic_results[factor_name].keys():
                        ic_stats = ic_results[factor_name][return_name]
                        quantile_stats = quantile_results[factor_name][return_name]
                        
                        row = {
                            'symbol': symbol,
                            'factor': factor_name,
                            'return_period': return_name,
                            
                            # IC指标
                            'ic_mean': ic_stats['ic_mean_spearman'],
                            'ic_std': ic_stats['ic_std_spearman'],
                            'ic_ir': ic_stats['ic_ir_spearman'],
                            'ic_positive_ratio': ic_stats['ic_positive_ratio'],
                            
                            # 分组指标
                            'long_short_return': quantile_stats['long_short_return'],
                            'long_short_sharpe': quantile_stats['long_short_sharpe'],
                            'monotonicity': quantile_stats['monotonicity'],
                            
                            # 统计特性
                            'factor_std': stats_results[factor_name]['std'],
                            'autocorr_1': stats_results[factor_name]['autocorr_1'],
                            'turnover_rate': stats_results[factor_name]['turnover_rate'],
                        }
                        
                        summary_rows.append(row)
                        pbar.update(1)
        
        summary_df = pd.DataFrame(summary_rows)
        
        # 保存
        output_path = self.output_dir / 'factor_evaluation_summary.csv'
        summary_df.to_csv(output_path, index=False)
        print(f"   ✅ 摘要文件: {output_path}")
        
        # 生成排名（按IC IR排序）
        print("   📊 生成排名文件...")
        ranking_count = 0
        for symbol in all_results.keys():
            symbol_df = summary_df[summary_df['symbol'] == symbol].copy()
            
            # 对每个收益率周期单独排名
            for return_name in symbol_df['return_period'].unique():
                period_df = symbol_df[symbol_df['return_period'] == return_name].copy()
                period_df = period_df.sort_values('ic_ir', ascending=False)
                
                ranking_path = self.output_dir / f'{symbol}_{return_name}_ranking.csv'
                period_df.to_csv(ranking_path, index=False)
                ranking_count += 1
        
        print(f"   ✅ 生成 {ranking_count} 个排名文件")
    
    def _generate_html_reports(self, all_results: Dict):
        """生成HTML报告"""
        print("   📝 生成HTML报告...")
        
        with tqdm(total=len(all_results), desc="   HTML生成进度") as pbar:
            for symbol, results in all_results.items():
                html_content = self._create_html_report(symbol, results)
                
                output_path = self.output_dir / f'{symbol}_detailed_report.html'
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                pbar.update(1)
        
        print(f"   ✅ 生成 {len(all_results)} 个HTML报告")
    
    def _create_html_report(self, symbol: str, results: Dict) -> str:
        """Create HTML report content (English version)"""
        html = f"""
        <html>
        <head>
            <title>{symbol} Factor Evaluation Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                h2 {{ color: #666; border-bottom: 2px solid #666; padding-bottom: 5px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
                .metric {{ font-weight: bold; color: #4CAF50; }}
            </style>
        </head>
        <body>
            <h1>{symbol} Factor Evaluation Report</h1>
        """
        
        # Add detailed information for each factor
        for factor_name in results['ic'].keys():
            html += f"<h2>Factor: {factor_name}</h2>"
            
            # Statistical properties
            stats = results['statistics'][factor_name]
            html += "<h3>Statistical Properties</h3><table>"
            html += "<tr><th>Metric</th><th>Value</th></tr>"
            for key, value in stats.items():
                if not isinstance(value, (pd.Series, pd.DataFrame)):
                    html += f"<tr><td>{key}</td><td>{value:.6f}</td></tr>"
            html += "</table>"
            
            # Decay analysis
            decay = results['decay'][factor_name]
            html += "<h3>Factor Decay Analysis</h3><table>"
            html += f"<tr><td>Best Holding Period</td><td>{decay['best_holding_period_minutes']} minutes</td></tr>"
            html += f"<tr><td>Best Period IC</td><td>{decay['best_period_ic']:.6f}</td></tr>"
            html += f"<tr><td>Half Life</td><td>{decay['half_life_minutes']} minutes</td></tr>"
            html += "</table>"
        
        html += "</body></html>"
        return html
    
    def _generate_plots(self, all_results: Dict):
        """生成可视化图表（按标的和因子分目录）"""
        print("   📊 生成可视化图表...")
        
        plot_dir = self.output_dir / 'plots'
        plot_dir.mkdir(exist_ok=True)
        
        total_factors = sum(len(results['ic']) for results in all_results.values())
        
        with tqdm(total=total_factors, desc="   图表生成进度") as pbar:
            for symbol, results in all_results.items():
                # 为每个标的创建子目录
                symbol_dir = plot_dir / symbol
                symbol_dir.mkdir(exist_ok=True)
                
                # 为每个因子生成图表
                for factor_name in results['ic'].keys():
                    # 为每个因子创建子目录
                    factor_dir = symbol_dir / factor_name
                    factor_dir.mkdir(exist_ok=True)
                    
                    self._plot_factor_analysis(symbol, factor_name, results, factor_dir)
                    pbar.update(1)
        
        print(f"   ✅ 生成 {total_factors} 个因子的图表文件")
    
    def _plot_factor_analysis(self, symbol: str, factor_name: str, 
                              results: Dict, factor_dir: Path):
        """
        为单个因子生成分析图表
        
        Args:
            symbol: 标的名称
            factor_name: 因子名称
            results: 评测结果
            factor_dir: 因子图表保存目录
        """
        return_names = list(results['ic'][factor_name].keys())
        n_returns = len(return_names)
        
        # 1. IC Time Series - 所有return周期在一张图
        self._plot_ic_timeseries(symbol, factor_name, results, factor_dir)
        
        # 2. IC Comparison - 柱状图对比
        self._plot_ic_comparison(symbol, factor_name, results, factor_dir)
        
        # 3. Quantile Returns - 每个return周期单独一张图
        self._plot_quantile_returns(symbol, factor_name, results, factor_dir, return_names)
        
        # 4. Factor Decay Curve
        self._plot_decay_curve(symbol, factor_name, results, factor_dir)
        
        # 5. Comprehensive Overview - 4合1概览图
        self._plot_comprehensive_overview(symbol, factor_name, results, factor_dir)
    
    def _plot_ic_timeseries(self, symbol: str, factor_name: str, 
                           results: Dict, factor_dir: Path):
        """绘制IC时间序列图"""
        fig, ax = plt.subplots(figsize=(15, 6))
        
        for return_name, ic_stats in results['ic'][factor_name].items():
            ic_series = ic_stats.get('ic_series_spearman', pd.Series())
            if len(ic_series) > 0:
                ax.plot(ic_series.index, ic_series.values, label=return_name, alpha=0.7, linewidth=1.5)
        
        ax.set_title(f'{symbol} - {factor_name} - IC Time Series', fontsize=14, fontweight='bold')
        ax.set_ylabel('Spearman IC', fontsize=12)
        ax.set_xlabel('Date', fontsize=12)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8, alpha=0.5)
        ax.legend(fontsize=10, loc='best')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(factor_dir / '1_ic_timeseries.png', dpi=100, bbox_inches='tight')
        plt.close()
    
    def _plot_ic_comparison(self, symbol: str, factor_name: str, 
                           results: Dict, factor_dir: Path):
        """绘制不同周期IC对比图"""
        fig, ax = plt.subplots(figsize=(12, 6))
        
        ic_means = []
        ic_stds = []
        periods = []
        
        for return_name, ic_stats in results['ic'][factor_name].items():
            ic_means.append(ic_stats['ic_mean_spearman'])
            ic_stds.append(ic_stats['ic_std_spearman'])
            periods.append(return_name.replace('ret_delay_9s_period_', ''))
        
        x = np.arange(len(periods))
        bars = ax.bar(x, ic_means, yerr=ic_stds, capsize=5, alpha=0.7)
        
        # Color bars based on IC value
        for i, bar in enumerate(bars):
            if ic_means[i] > 0:
                bar.set_color('green')
            else:
                bar.set_color('red')
        
        ax.set_title(f'{symbol} - {factor_name} - IC Comparison by Period', fontsize=14, fontweight='bold')
        ax.set_ylabel('Mean Spearman IC', fontsize=12)
        ax.set_xlabel('Return Period', fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(periods, rotation=45, ha='right')
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
        ax.grid(True, alpha=0.3, axis='y')
        
        # Add IC values on top of bars
        for i, (mean, std) in enumerate(zip(ic_means, ic_stds)):
            ax.text(i, mean + std + 0.001, f'{mean:.4f}', ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        plt.savefig(factor_dir / '2_ic_comparison.png', dpi=100, bbox_inches='tight')
        plt.close()
    
    def _plot_quantile_returns(self, symbol: str, factor_name: str, 
                              results: Dict, factor_dir: Path, return_names: List[str]):
        """绘制分组收益图 - 每个return周期一张图"""
        n_returns = len(return_names)
        
        # 计算子图布局
        n_cols = min(3, n_returns)  # 最多3列
        n_rows = (n_returns + n_cols - 1) // n_cols
        
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(6*n_cols, 5*n_rows))
        if n_returns == 1:
            axes = np.array([axes])
        axes = axes.flatten() if n_returns > 1 else axes
        
        for idx, return_name in enumerate(return_names):
            ax = axes[idx] if n_returns > 1 else axes
            
            group_stats = results['quantile'][factor_name][return_name].get('group_stats', pd.DataFrame())
            actual_groups = results['quantile'][factor_name][return_name].get('actual_groups', self.config['evaluation']['quantile_groups'])
            
            if not group_stats.empty:
                # 动态调整柱宽
                bar_width = 0.6 if actual_groups <= 3 else 0.8
                bars = ax.bar(group_stats['group'], group_stats['mean_return'], 
                             width=bar_width, alpha=0.7)
                
                # Color bars: green for positive, red for negative
                for i, bar in enumerate(bars):
                    if group_stats.iloc[i]['mean_return'] > 0:
                        bar.set_color('green')
                    else:
                        bar.set_color('red')
                
                # Add return values on top of bars
                for i, row in group_stats.iterrows():
                    y_pos = row['mean_return']
                    ax.text(row['group'], y_pos, f"{y_pos:.6f}", 
                           ha='center', va='bottom' if y_pos > 0 else 'top', fontsize=9)
                
                period_name = return_name.replace('ret_delay_9s_period_', '')
                
                # 标题中标注实际分组数
                if actual_groups < self.config['evaluation']['quantile_groups']:
                    title = f'Period: {period_name} ({actual_groups} groups)'
                else:
                    title = f'Period: {period_name}'
                
                ax.set_title(title, fontsize=12, fontweight='bold')
                ax.set_xlabel('Group', fontsize=10)
                ax.set_ylabel('Mean Return', fontsize=10)
                ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
                ax.grid(True, alpha=0.3, axis='y')
                
                # 设置x轴刻度
                ax.set_xticks(group_stats['group'])
                
                # Add long-short info
                ls_return = results['quantile'][factor_name][return_name]['long_short_return']
                ax.text(0.02, 0.98, f'L-S: {ls_return:.6f}', 
                       transform=ax.transAxes, fontsize=10,
                       verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
                
                # 如果是二值因子，添加提示
                if actual_groups == 2:
                    ax.text(0.02, 0.90, 'Binary Factor', 
                           transform=ax.transAxes, fontsize=9, style='italic',
                           verticalalignment='top', bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
        
        # Hide unused subplots
        for idx in range(n_returns, len(axes)):
            axes[idx].axis('off')
        
        fig.suptitle(f'{symbol} - {factor_name} - Quantile Returns', fontsize=16, fontweight='bold', y=0.995)
        plt.tight_layout()
        plt.savefig(factor_dir / '3_quantile_returns.png', dpi=100, bbox_inches='tight')
        plt.close()
    
    def _plot_decay_curve(self, symbol: str, factor_name: str, 
                         results: Dict, factor_dir: Path):
        """绘制因子衰减曲线"""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        decay_curve = results['decay'][factor_name].get('period_ic_curve', pd.DataFrame())
        
        if not decay_curve.empty:
            ax.plot(decay_curve['period_minutes'], decay_curve['ic'], 
                   marker='o', linewidth=2, markersize=8, color='blue', alpha=0.7)
            
            ax.set_title(f'{symbol} - {factor_name} - Factor Decay Curve', fontsize=14, fontweight='bold')
            ax.set_xlabel('Holding Period (minutes)', fontsize=12)
            ax.set_ylabel('IC', fontsize=12)
            ax.axhline(y=0, color='red', linestyle='--', linewidth=1.5, alpha=0.5)
            ax.grid(True, alpha=0.3)
            
            # Mark best holding period
            if not pd.isna(results['decay'][factor_name].get('best_holding_period_minutes')):
                best_period = results['decay'][factor_name]['best_holding_period_minutes']
                best_ic = results['decay'][factor_name]['best_period_ic']
                ax.plot(best_period, best_ic, 'r*', markersize=20, 
                       label=f'Best: {best_period}min (IC={best_ic:.4f})', zorder=5)
                ax.legend(fontsize=11, loc='best')
            
            # Add IC values on points
            for _, row in decay_curve.iterrows():
                ax.annotate(f"{row['ic']:.4f}", 
                           (row['period_minutes'], row['ic']),
                           textcoords="offset points", xytext=(0,10), 
                           ha='center', fontsize=8, alpha=0.7)
        
        plt.tight_layout()
        plt.savefig(factor_dir / '4_decay_curve.png', dpi=100, bbox_inches='tight')
        plt.close()
    
    def _plot_comprehensive_overview(self, symbol: str, factor_name: str, 
                                    results: Dict, factor_dir: Path):
        """绘制综合概览图（4合1）"""
        fig = plt.figure(figsize=(16, 12))
        gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)
        
        # 1. IC Time Series (top, span 2 columns)
        ax1 = fig.add_subplot(gs[0, :])
        for return_name, ic_stats in results['ic'][factor_name].items():
            ic_series = ic_stats.get('ic_series_spearman', pd.Series())
            if len(ic_series) > 0:
                ax1.plot(ic_series.index, ic_series.values, label=return_name, alpha=0.7, linewidth=1.5)
        ax1.set_title('IC Time Series', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Spearman IC', fontsize=10)
        ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax1.legend(fontsize=8, loc='best', ncol=2)
        ax1.grid(True, alpha=0.3)
        
        # 2. IC Comparison (middle left)
        ax2 = fig.add_subplot(gs[1, 0])
        ic_means = []
        periods = []
        for return_name, ic_stats in results['ic'][factor_name].items():
            ic_means.append(ic_stats['ic_mean_spearman'])
            periods.append(return_name.replace('ret_delay_9s_period_', ''))
        bars = ax2.bar(periods, ic_means, alpha=0.7)
        for i, bar in enumerate(bars):
            bar.set_color('green' if ic_means[i] > 0 else 'red')
        ax2.set_title('IC Comparison', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Mean IC', fontsize=10)
        ax2.tick_params(axis='x', rotation=45, labelsize=8)
        ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax2.grid(True, alpha=0.3, axis='y')
        
        # 3. Quantile Returns - first return period (middle right)
        ax3 = fig.add_subplot(gs[1, 1])
        first_return = list(results['quantile'][factor_name].keys())[0]
        group_stats = results['quantile'][factor_name][first_return].get('group_stats', pd.DataFrame())
        if not group_stats.empty:
            bars = ax3.bar(group_stats['group'], group_stats['mean_return'], alpha=0.7)
            for i, bar in enumerate(bars):
                bar.set_color('green' if group_stats.iloc[i]['mean_return'] > 0 else 'red')
            period_name = first_return.replace('ret_delay_9s_period_', '')
            ax3.set_title(f'Quantile Returns ({period_name})', fontsize=12, fontweight='bold')
            ax3.set_xlabel('Group', fontsize=10)
            ax3.set_ylabel('Mean Return', fontsize=10)
            ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax3.grid(True, alpha=0.3, axis='y')
        
        # 4. Decay Curve (bottom, span 2 columns)
        ax4 = fig.add_subplot(gs[2, :])
        decay_curve = results['decay'][factor_name].get('period_ic_curve', pd.DataFrame())
        if not decay_curve.empty:
            ax4.plot(decay_curve['period_minutes'], decay_curve['ic'], 
                    marker='o', linewidth=2, markersize=6, color='blue', alpha=0.7)
            ax4.set_title('Factor Decay Curve', fontsize=12, fontweight='bold')
            ax4.set_xlabel('Holding Period (minutes)', fontsize=10)
            ax4.set_ylabel('IC', fontsize=10)
            ax4.axhline(y=0, color='red', linestyle='--', linewidth=1)
            ax4.grid(True, alpha=0.3)
            
            if not pd.isna(results['decay'][factor_name].get('best_holding_period_minutes')):
                best_period = results['decay'][factor_name]['best_holding_period_minutes']
                best_ic = results['decay'][factor_name]['best_period_ic']
                ax4.plot(best_period, best_ic, 'r*', markersize=15, 
                        label=f'Best: {best_period}min', zorder=5)
                ax4.legend(fontsize=10)
        
        fig.suptitle(f'{symbol} - {factor_name} - Comprehensive Overview', 
                    fontsize=16, fontweight='bold')
        plt.savefig(factor_dir / '0_overview.png', dpi=100, bbox_inches='tight')
        plt.close()
    
    def _save_ic_timeseries(self, all_results: Dict):
        """保存IC时间序列数据"""
        print("   💾 保存IC时间序列...")
        
        ic_dir = self.output_dir / 'ic_timeseries'
        ic_dir.mkdir(exist_ok=True)
        
        saved_count = 0
        for symbol, results in all_results.items():
            for factor_name in results['ic'].keys():
                for return_name, ic_stats in results['ic'][factor_name].items():
                    ic_series = ic_stats.get('ic_series_spearman', pd.Series())
                    
                    if len(ic_series) > 0:
                        output_path = ic_dir / f'{symbol}_{factor_name}_{return_name}_ic.csv'
                        ic_series.to_csv(output_path)
                        saved_count += 1
        
        print(f"   ✅ 保存 {saved_count} 个IC时间序列文件")