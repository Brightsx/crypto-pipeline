#!/usr/bin/env python3
"""挖因子程序主入口"""
import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from core import config, FactorEngine
from factors import factor_registry


def main():
    """主函数"""
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("="*60)
        logger.info("Starting Factor Mining System")
        logger.info("="*60)
        
        # 显示配置信息
        logger.info(f"Symbols: {config.symbols}")
        logger.info(f"K-line windows: {config.kline_windows}")
        logger.info(f"Calculation frequency: {config.calc_frequency}")
        logger.info(f"Time range: {config.start_time} to {config.end_time}")
        logger.info(f"Batch days: {config.batch_days}")
        logger.info(f"Max lookback days: {config.max_lookback_days}")
        
        # 显示注册的因子
        factors = factor_registry.list_factors()
        logger.info(f"Registered factors: {len(factors)}")
        for factor_name in factors:
            factor_info = factor_registry.get_factor(factor_name)
            logger.info(f"  - {factor_name} ({factor_info['kline_window']}): {factor_info['description']}")
        
        if not factors:
            logger.warning("No factors registered! Please check factors module.")
            return
        
        # 创建因子计算引擎
        engine = FactorEngine()
        
        # 显示因子摘要
        summary = engine.get_factor_summary()
        if not summary.empty:
            logger.info("\nFactor Summary:")
            logger.info(summary.to_string(index=False))
        
        # 执行因子计算
        logger.info("\nStarting factor computation...")
        results = engine.compute_all_symbols()
        
        # 显示结果统计
        logger.info("\n" + "="*60)
        logger.info("Factor Computation Results")
        logger.info("="*60)
        
        for symbol, result_df in results.items():
            if not result_df.empty:
                logger.info(f"{symbol}: {len(result_df)} timepoints, {len(result_df.columns)} factors")
                logger.info(f"  Time range: {result_df.index.min()} to {result_df.index.max()}")
                logger.info(f"  Factor columns: {list(result_df.columns)}")
            else:
                logger.warning(f"{symbol}: No results generated")
        
        logger.info("="*60)
        logger.info("Factor Mining Completed Successfully!")
        logger.info("="*60)
        
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.exception("Full traceback:")
        sys.exit(1)


def run_single_symbol(symbol: str):
    """运行单个币种的因子计算（用于调试）"""
    logger = logging.getLogger(__name__)
    
    logger.info(f"Computing factors for single symbol: {symbol}")
    
    if symbol not in config.symbols:
        logger.error(f"Symbol {symbol} not in configured symbols: {config.symbols}")
        return
    
    engine = FactorEngine()
    result = engine.compute_factors(symbol)
    
    if not result.empty:
        logger.info(f"Result shape: {result.shape}")
        logger.info(f"Columns: {list(result.columns)}")
        logger.info(f"Sample data:\n{result.head()}")
        
        # 保存结果
        output_file = config.output_path / f"{symbol}_factors.parquet"
        result.to_parquet(output_file)
        logger.info(f"Saved to {output_file}")
    else:
        logger.warning("No results generated")


if __name__ == "__main__":
    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "single" and len(sys.argv) > 2:
            # 单币种模式：python main.py single BTCUSDT
            run_single_symbol(sys.argv[2])
        else:
            print("Usage:")
            print("  python main.py              # Run all symbols")
            print("  python main.py single SYMBOL # Run single symbol")
    else:
        # 正常模式：运行所有币种
        main()