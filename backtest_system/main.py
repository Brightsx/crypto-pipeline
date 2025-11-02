"""主回测程序"""
import yaml
import logging
import sys
from datetime import timedelta
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from utils.time_utils import (
    parse_frequency, parse_datetime_str, generate_time_range,
    datetime_to_timestamp, timestamp_to_datetime, find_nearest_timestamp
)
from data_loader.aggtrade_loader import AggTradeLoader
from data_loader.signal_loader import SignalLoader
from data_loader.funding_rate_loader import FundingRateLoader
from optimizer.simple_optimizer import SimpleOptimizer
from executor.executor import Executor
from metrics.recorder import Recorder


def setup_logging(config: dict):
    """设置日志"""
    log_config = config.get('logging', {})
    level = getattr(logging, log_config.get('level', 'INFO'))
    fmt = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    date_fmt = log_config.get('date_format', '%Y-%m-%d %H:%M:%S')
    
    logging.basicConfig(level=level, format=fmt, datefmt=date_fmt)


def load_module(module_path: str, class_name: str):
    """动态加载模块"""
    parts = module_path.split('.')
    module = __import__(module_path)
    
    for part in parts[1:]:
        module = getattr(module, part)
    
    return getattr(module, class_name)


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, config_path: str):
        """
        初始化回测引擎
        
        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # 设置日志
        setup_logging(self.config)
        self.logger = logging.getLogger(__name__)
        self.logger.info("=" * 60)
        self.logger.info("回测系统启动")
        self.logger.info("=" * 60)
        
        # 解析回测参数
        self.start_time = parse_datetime_str(self.config['backtest']['start_time'])
        self.end_time = parse_datetime_str(self.config['backtest']['end_time'])
        self.frequency = parse_frequency(self.config['backtest']['frequency'])
        self.initial_usdt = self.config['backtest']['initial_usdt']
        self.symbols = self.config['backtest']['symbols']
        
        self.logger.info(f"回测时间: {self.start_time} 至 {self.end_time} (UTC)")
        self.logger.info(f"回测频率: {self.config['backtest']['frequency']}")
        self.logger.info(f"初始保证金: {self.initial_usdt} USDT")
        self.logger.info(f"交易对: {self.symbols}")
        
        # 初始化各模块
        self._init_modules()
        
        # 状态变量
        self.current_usdt = self.initial_usdt
        self.current_positions = {symbol: 0.0 for symbol in self.symbols}
        self.current_prices = {symbol: 0.0 for symbol in self.symbols}
    
    def _init_modules(self):
        """初始化各个模块"""
        self.logger.info("初始化模块...")
        
        # 数据加载器
        self.aggtrade_loader = AggTradeLoader(self.config['data_loader']['aggtrade'])
        self.signal_loader = SignalLoader(self.config['data_loader']['signal'])
        self.funding_rate_loader = FundingRateLoader(self.config['data_loader']['funding_rate'])
        
        # 预加载信号数据
        self.signal_loader.load_all()
        
        # 优化器
        self.optimizer = SimpleOptimizer(self.config['optimizer'])
        
        # 执行器
        self.executor = Executor(self.config['executor'])
        
        # 记录器
        self.recorder = Recorder(self.config['metrics'])
        
        self.logger.info("模块初始化完成")
    
    def _load_period_data(self, start, end):
        """加载周期数据"""
        # 加载aggtrade数据
        # 为了获取第一个时间点的价格，需要加载开始时间之前的数据
        extended_start = start - timedelta(days=1)  # 向前扩展1天
        extended_end = end + timedelta(seconds=120)  # 向后扩展120秒用于执行窗口
        
        aggtrade_data = {}
        
        for symbol in self.symbols:
            aggtrade_data[symbol] = self.aggtrade_loader.load_period(extended_start, extended_end, symbol)
        
        # 加载资金费率数据
        funding_data = {}
        for symbol in self.symbols:
            funding_data[symbol] = self.funding_rate_loader.load_period(extended_start, end, symbol)
        
        return aggtrade_data, funding_data
    
    def _settle_funding_rate(self, current_time, funding_data: dict):
        """
        结算资金费率
        
        Args:
            current_time: 当前时间
            funding_data: 资金费率数据
        
        Returns:
            资金费率PnL
        """
        funding_pnl = 0.0
        current_ts = datetime_to_timestamp(current_time, 'ms')
        
        for symbol in self.symbols:
            symbol_funding_df = funding_data.get(symbol)
            
            if symbol_funding_df is None or symbol_funding_df.empty:
                continue
            
            # 找到最接近当前时间的资金费率时间
            funding_times = symbol_funding_df['calc_time'].tolist()
            nearest_funding_time = find_nearest_timestamp(current_ts, funding_times, allow_future=True)
            
            if nearest_funding_time is None:
                continue
            
            # 检查是否非常接近（允许毫秒级偏差，比如在1秒内）
            time_diff = abs(current_ts - nearest_funding_time)
            if time_diff > 1000:  # 超过1秒就不结算
                continue
            
            # 获取资金费率
            funding_row = symbol_funding_df[symbol_funding_df['calc_time'] == nearest_funding_time]
            if funding_row.empty:
                continue
            
            funding_rate = float(funding_row.iloc[0]['last_funding_rate'])
            position = self.current_positions.get(symbol, 0.0)
            price = self.current_prices.get(symbol, 0.0)
            
            if position == 0 or price == 0:
                continue
            
            # 计算资金费率损益
            # 多仓支付资金费率（为负），空仓收取资金费率（为正）
            position_value = position * price
            symbol_funding_pnl = -position_value * funding_rate
            funding_pnl += symbol_funding_pnl
            
            self.logger.info(f"[{current_time}] {symbol} 资金费率结算: "
                           f"费率={funding_rate:.6f}, 仓位={position:.6f}, "
                           f"价格={price:.2f}, PnL={symbol_funding_pnl:.2f} USDT")
        
        if funding_pnl != 0:
            self.logger.info(f"[{current_time}] 资金费率总结算: {funding_pnl:.2f} USDT")
        
        return funding_pnl
    
    def _update_prices(self, current_time, aggtrade_data: dict):
        """更新当前价格"""
        for symbol in self.symbols:
            symbol_df = aggtrade_data.get(symbol)
            if symbol_df is None or symbol_df.empty:
                self.logger.warning(f"[{current_time}] {symbol} 无价格数据")
                continue
            
            price = self.aggtrade_loader.get_last_price(symbol_df, current_time)
            if price is not None:
                self.current_prices[symbol] = price
            else:
                self.logger.warning(f"[{current_time}] {symbol} 无法获取价格")
    
    def _calculate_pnl(self, trades: dict, prev_prices: dict, current_prices: dict, 
                      prev_positions: dict, execution_info: dict) -> tuple:
        """
        计算本周期的PnL
        
        Args:
            trades: 交易记录
            prev_prices: 上一周期价格
            current_prices: 当前周期价格
            prev_positions: 上一周期仓位
            execution_info: 执行信息
        
        Returns:
            (trade_pnl, hold_pnl, fee_pnl)
        """
        # trade_pnl: 已在executor中计算
        trade_pnl = execution_info['trade_pnl']
        
        # hold_pnl: 持有仓位的价格变动
        hold_pnl = 0.0
        for symbol in self.symbols:
            prev_pos = prev_positions.get(symbol, 0.0)
            prev_price = prev_prices.get(symbol, 0.0)
            curr_price = current_prices.get(symbol, 0.0)
            
            if prev_pos != 0 and prev_price != 0 and curr_price != 0:
                price_change = curr_price - prev_price
                symbol_hold_pnl = prev_pos * price_change
                hold_pnl += symbol_hold_pnl
        
        # fee_pnl: 手续费（负数）
        fee_pnl = -execution_info['total_fee']
        
        return trade_pnl, hold_pnl, fee_pnl
    
    def run(self):
        """运行回测"""
        self.logger.info("=" * 60)
        self.logger.info("开始回测")
        self.logger.info("=" * 60)
        
        # 记录初始状态
        self.recorder.record_initial_state(self.start_time, self.current_usdt, self.symbols)
        
        # 生成时间序列
        time_points = list(generate_time_range(self.start_time, self.end_time, self.frequency))
        self.logger.info(f"总共 {len(time_points)} 个时间点")
        
        # 按天或周加载数据
        current_load_start = None
        load_period = timedelta(days=1)
        aggtrade_data = {}
        funding_data = {}
        
        for i, current_time in enumerate(time_points):
            # 检查是否需要加载新的数据周期
            if current_load_start is None or current_time >= current_load_start + load_period:
                current_load_start = current_time
                load_end = min(current_time + load_period, self.end_time + timedelta(seconds=120))
                
                self.logger.info(f"加载数据: {current_load_start.date()} 至 {load_end.date()}")
                aggtrade_data, funding_data = self._load_period_data(current_load_start, load_end)
            
            # 确定下一个时间点
            next_time = time_points[i + 1] if i + 1 < len(time_points) else self.end_time
            
            self.logger.info(f"\n{'=' * 60}")
            self.logger.info(f"周期 {i + 1}/{len(time_points)}: {current_time}")
            self.logger.info(f"{'=' * 60}")
            
            # 1. 结算资金费率并更新保证金
            funding_pnl = self._settle_funding_rate(current_time, funding_data)
            self.current_usdt += funding_pnl
            
            # 2. 检查是否爆仓
            if self.current_usdt <= 0:
                self.logger.warning(f"[{current_time}] 爆仓! 保证金: {self.current_usdt:.2f}")
                self.current_usdt = 0.0
                self.current_positions = {symbol: 0.0 for symbol in self.symbols}
            
            # 3. 更新当前价格
            prev_prices = self.current_prices.copy()
            self._update_prices(current_time, aggtrade_data)
            
            # 4. 获取信号
            current_ts = datetime_to_timestamp(current_time, 
                                             self.signal_loader.get_time_unit())
            signals = self.signal_loader.get_signals_at_time(current_ts, self.symbols)
            
            if not signals:
                self.logger.warning(f"[{current_time}] 未获取到信号")
                signals = {symbol: 0.0 for symbol in self.symbols}
            
            # 5. 优化：计算目标仓位
            prev_positions = self.current_positions.copy()
            target_positions = self.optimizer.optimize(
                current_time, signals, self.current_positions,
                self.current_prices, self.current_usdt
            )
            
            # 6. 执行交易
            trades, execution_info = self.executor.execute(
                current_time, target_positions, self.current_positions,
                self.current_prices, self.aggtrade_loader, aggtrade_data, next_time
            )
            
            # 7. 更新仓位（不更新保证金）
            self.current_positions = self.executor.update_positions(
                self.current_positions, trades
            )
            
            # 8. 记录交易（传入开始和结束时间）
            self.recorder.record_trades(current_time, next_time, trades)
            
            # 9. 更新最终价格（周期结束时的价格）
            self._update_prices(next_time, aggtrade_data)
            
            # 10. 计算PnL
            trade_pnl, hold_pnl, fee_pnl = self._calculate_pnl(
                trades, prev_prices, self.current_prices, prev_positions, execution_info
            )
            
            # 11. 更新保证金（统一在这里处理）
            total_pnl = trade_pnl + hold_pnl + fee_pnl
            self.current_usdt += total_pnl

            # 12. 再次检查是否爆仓
            if self.current_usdt <= 0:
                self.logger.warning(f"[{current_time}] 爆仓! 保证金: {self.current_usdt:.2f}")
                self.current_usdt = 0.0
                self.current_positions = {symbol: 0.0 for symbol in self.symbols}
            
            # 13. 记录周期状态
            self.recorder.record_position_state(
                next_time, self.current_usdt, self.current_positions, 
                self.current_prices, trade_pnl, hold_pnl, fee_pnl, funding_pnl
            )
            
            self.logger.info(f"[{current_time}] 周期结束: USDT={self.current_usdt:.2f}")
        
        # 保存结果
        self.logger.info("\n" + "=" * 60)
        self.logger.info("回测完成，保存结果...")
        self.logger.info("=" * 60)
        self.recorder.save_records()
        
        # 输出摘要
        summary = self.recorder.get_summary()
        
        return summary


def main():
    """主函数"""
    config_path = "config/config.yaml"
    
    try:
        engine = BacktestEngine(config_path)
        summary = engine.run()
        
        print("\n" + "=" * 60)
        print("回测完成!")
        print("=" * 60)
        print(f"初始保证金: {summary['initial_balance']:.2f} USDT")
        print(f"最终保证金: {summary['final_balance']:.2f} USDT")
        print(f"总收益率: {summary['total_return']:.2%}")
        print("=" * 60)
        
    except Exception as e:
        logging.error(f"回测失败: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()