"""统计记录器"""
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class Recorder:
    """
    统计记录器
    记录交易信息和仓位状态
    """
    
    def __init__(self, config: dict):
        """
        初始化记录器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.output_dir = Path(config.get('output_dir', './results'))
        self.trade_log_file = self.output_dir / config.get('trade_log_file', 'trade_log.csv')
        self.position_log_file = self.output_dir / config.get('position_log_file', 'position_log.csv')
        
        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化CSV文件（清空并写入表头）
        self._init_csv_files()
        
        logger.info(f"记录器初始化: 输出目录={self.output_dir}")

    def _init_csv_files(self):
        """初始化CSV文件,写入表头"""
        # Trade log表头
        trade_columns = ['start_time', 'end_time', 'symbol', 'target_quantity', 
                        'actual_quantity', 'vwap', 'execution_price', 'trade_value', 
                        'fee', 'slippage']
        pd.DataFrame(columns=trade_columns).to_csv(self.trade_log_file, index=False)
        
        # Position log表头 (需要根据symbols动态生成)
        # 这个在record_initial_state中处理
        logger.info(f"CSV文件已初始化")
    
    def record_initial_state(self, time, usdt_balance: float, symbols: list):
        """
        记录初始状态
        
        Args:
            time: 时间(datetime)
            usdt_balance: 初始USDT余额
            symbols: 交易对列表
        """
        record = {
            'time': time,
            'usdt_balance': usdt_balance,
            'trade_pnl': 0.0,
            'hold_pnl': 0.0,
            'fee_pnl': 0.0,
            'funding_pnl': 0.0,
            'total_pnl': 0.0
        }
        
        # 初始化所有币种仓位为0
        for symbol in symbols:
            record[f'{symbol}_position'] = 0.0
            record[f'{symbol}_price'] = 0.0
        
        # 初始化position log文件并写入第一行
        df = pd.DataFrame([record])
        df.to_csv(self.position_log_file, index=False)
        
        logger.info(f"[{time}] 记录初始状态: USDT={usdt_balance:.2f}")
    
    def record_trades(self, start_time, end_time, trades: dict):
        """
        记录交易信息
        
        Args:
            start_time: 周期开始时间(datetime)
            end_time: 周期结束时间(datetime)
            trades: 交易记录字典
        """
        if not trades:
            return
        
        records = []
        for symbol, trade_info in trades.items():
            record = {
                'start_time': start_time,
                'end_time': end_time,
                'symbol': symbol,
                'target_quantity': trade_info['target_quantity'],
                'actual_quantity': trade_info['actual_quantity'],
                'vwap': trade_info['vwap'],
                'execution_price': trade_info['execution_price'],
                'trade_value': trade_info['trade_value'],
                'fee': trade_info['fee'],
                'slippage': trade_info['slippage']
            }
            records.append(record)
            
            logger.debug(f"[{start_time}] 记录交易: {symbol} {trade_info['actual_quantity']:.6f} @ "
                    f"{trade_info['execution_price']:.2f}")
        
        # 实时追加到CSV文件
        if records:
            df = pd.DataFrame(records)
            df.to_csv(self.trade_log_file, mode='a', header=False, index=False)
    
    def record_position_state(self, time, usdt_balance: float, positions: dict, 
                            prices: dict, trade_pnl: float, hold_pnl: float,
                            fee_pnl: float, funding_pnl: float = 0.0):
        """
        记录周期结束时的状态
        
        Args:
            time: 时间(datetime)
            usdt_balance: USDT余额
            positions: 仓位字典
            prices: 价格字典
            trade_pnl: 交易PnL
            hold_pnl: 持有PnL
            fee_pnl: 手续费PnL(负数)
            funding_pnl: 资金费率PnL
        """
        total_pnl = trade_pnl + hold_pnl + fee_pnl + funding_pnl
        
        record = {
            'time': time,
            'usdt_balance': usdt_balance,
            'trade_pnl': trade_pnl,
            'hold_pnl': hold_pnl,
            'fee_pnl': fee_pnl,
            'funding_pnl': funding_pnl,
            'total_pnl': total_pnl
        }
        
        # 记录各币种仓位和价格
        for symbol in positions.keys():
            record[f'{symbol}_position'] = positions.get(symbol, 0.0)
            record[f'{symbol}_price'] = prices.get(symbol, 0.0)
        
        # 实时追加到CSV文件
        df = pd.DataFrame([record])
        df.to_csv(self.position_log_file, mode='a', header=False, index=False)
        
        logger.info(f"[{time}] 记录状态: USDT={usdt_balance:.2f}, "
                f"tradePnL={trade_pnl:.2f}, holdPnL={hold_pnl:.2f}, "
                f"feePnL={fee_pnl:.2f}, fundingPnL={funding_pnl:.2f}, totalPnL={total_pnl:.2f}")
    
    def save_records(self):
        """保存记录 - 由于已经实时写入,这里只做日志输出"""
        logger.info(f"交易记录已保存: {self.trade_log_file}")
        logger.info(f"仓位记录已保存: {self.position_log_file}")
    
    def get_summary(self) -> dict:
        """
        获取回测摘要统计
        
        Returns:
            统计摘要字典
        """
        # 从文件读取position数据
        position_df = pd.read_csv(self.position_log_file)
        
        if position_df.empty:
            return {}
        
        initial_balance = position_df.iloc[0]['usdt_balance']
        final_balance = position_df.iloc[-1]['usdt_balance']
        total_return = (final_balance - initial_balance) / initial_balance
        
        # 统计交易次数
        try:
            trade_df = pd.read_csv(self.trade_log_file)
            num_trades = len(trade_df)
        except:
            num_trades = 0
        
        summary = {
            'initial_balance': initial_balance,
            'final_balance': final_balance,
            'total_return': total_return,
            'total_trade_pnl': position_df['trade_pnl'].sum(),
            'total_hold_pnl': position_df['hold_pnl'].sum(),
            'total_fee_pnl': position_df['fee_pnl'].sum(),
            'total_funding_pnl': position_df['funding_pnl'].sum(),
            'max_balance': position_df['usdt_balance'].max(),
            'min_balance': position_df['usdt_balance'].min(),
            'num_trades': num_trades
        }
        
        logger.info("=" * 60)
        logger.info("回测摘要:")
        logger.info(f"  初始保证金: {summary['initial_balance']:.2f} USDT")
        logger.info(f"  最终保证金: {summary['final_balance']:.2f} USDT")
        logger.info(f"  总收益率: {summary['total_return']:.2%}")
        logger.info(f"  交易PnL: {summary['total_trade_pnl']:.2f} USDT")
        logger.info(f"  持有PnL: {summary['total_hold_pnl']:.2f} USDT")
        logger.info(f"  手续费PnL: {summary['total_fee_pnl']:.2f} USDT")
        logger.info(f"  资金费率PnL: {summary['total_funding_pnl']:.2f} USDT")
        logger.info(f"  交易次数: {summary['num_trades']}")
        logger.info("=" * 60)
        
        return summary