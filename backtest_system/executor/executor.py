"""交易执行器"""
from datetime import timedelta
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class Executor:
    """
    交易执行器
    负责根据目标仓位执行交易，计算手续费和滑点
    """
    
    def __init__(self, config: dict):
        """
        初始化执行器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.params = config.get('params', {})
        
        # 执行参数
        self.execution_delay = self.params.get('execution_delay', 10)  # 执行延迟(秒)
        self.execution_window = self.params.get('execution_window', 20)  # 成交窗口(秒)
        self.fee_rate = self.params.get('fee_rate', 0.0004)  # 手续费率
        self.slippage_rate = self.params.get('slippage_rate', 0.0001)  # 滑点率
        self.max_volume_pct = self.params.get('max_volume_pct', 0.10)  # 最大成交量占比
        
        logger.info(f"执行器初始化: delay={self.execution_delay}s, window={self.execution_window}s, "
                   f"fee={self.fee_rate}, slippage={self.slippage_rate}, max_vol={self.max_volume_pct}")
    
    def execute(self, current_time, target_positions: dict, current_positions: dict,
                current_prices: dict, aggtrade_loader, aggtrade_data: dict,
                next_time) -> Tuple[dict, dict]:
        """
        执行交易
        
        Args:
            current_time: 当前时间(datetime)
            target_positions: 目标仓位字典
            current_positions: 当前仓位字典
            current_prices: 当前价格字典
            aggtrade_loader: aggtrade数据加载器
            aggtrade_data: 已加载的aggtrade数据
            next_time: 下一个优化时间点
        
        Returns:
            (trades, execution_info)
            trades: 交易记录字典，键为symbol，值为交易信息
            execution_info: 执行信息汇总
        """
        trades = {}
        execution_info = {
            'total_fee': 0.0,  # 总手续费(USDT)
            'trade_pnl': 0.0,  # 交易PnL(USDT)
            'executed_symbols': []
        }
        
        logger.info(f"[{current_time}] 开始执行交易")
        
        for symbol in target_positions.keys():
            target_pos = target_positions.get(symbol, 0)
            current_pos = current_positions.get(symbol, 0)
            current_price = current_prices.get(symbol)
            
            # 计算需要交易的数量
            trade_quantity = target_pos - current_pos
            
            if abs(trade_quantity) < 1e-8:
                logger.debug(f"[{current_time}] {symbol}: 无需交易")
                continue
            
            logger.info(f"[{current_time}] {symbol}: 需要交易 {trade_quantity:.6f} "
                       f"(当前: {current_pos:.6f} -> 目标: {target_pos:.6f})")
            
            # 执行交易
            trade_info = self._execute_single_trade(
                current_time, symbol, trade_quantity, current_price, current_pos,
                aggtrade_loader, aggtrade_data.get(symbol), next_time
            )
            
            if trade_info:
                trades[symbol] = trade_info
                execution_info['total_fee'] += trade_info['fee']
                execution_info['trade_pnl'] += trade_info['trade_pnl']
                execution_info['executed_symbols'].append(symbol)
        
        logger.info(f"[{current_time}] 交易执行完成: 总手续费={execution_info['total_fee']:.2f} USDT, "
                   f"交易PnL={execution_info['trade_pnl']:.2f} USDT")
        
        return trades, execution_info
    
    def _execute_single_trade(self, current_time, symbol: str, trade_quantity: float,
                             current_price: float, current_position: float,
                             aggtrade_loader, aggtrade_df, next_time) -> dict:
        """
        执行单个币种的交易
        
        Args:
            current_time: 当前时间
            symbol: 交易对
            trade_quantity: 交易数量(正数买入，负数卖出)
            current_price: 当前价格
            current_position: 当前持仓
            aggtrade_loader: aggtrade加载器
            aggtrade_df: aggtrade数据
            next_time: 下一个优化时间
        
        Returns:
            交易信息字典
        """
        # 计算执行时间窗口
        exec_start = current_time + timedelta(seconds=self.execution_delay)
        exec_end = exec_start + timedelta(seconds=self.execution_window)
        
        # 确保不超过下一个优化时间
        if exec_end > next_time:
            exec_end = next_time
        
        logger.debug(f"[{current_time}] {symbol}: 执行窗口 {exec_start} 到 {exec_end}")
        
        # 获取窗口内的VWAP和成交量
        vwap = aggtrade_loader.get_vwap(aggtrade_df, exec_start, exec_end)
        total_volume = aggtrade_loader.get_total_volume(aggtrade_df, exec_start, exec_end)
        
        if vwap is None:
            logger.warning(f"[{current_time}] {symbol}: 执行窗口内无成交数据，使用当前价格")
            vwap = current_price
            total_volume = 0
        
        # 检查成交量限制
        max_tradable = total_volume * self.max_volume_pct
        actual_quantity = trade_quantity
        
        if abs(trade_quantity) > max_tradable:
            actual_quantity = max_tradable if trade_quantity > 0 else -max_tradable
            logger.warning(f"[{current_time}] {symbol}: 交易量受限 {abs(trade_quantity):.6f} -> {abs(actual_quantity):.6f}")
        
        # 计算滑点后的成交价
        if trade_quantity > 0:  # 买入，价格上浮
            execution_price = vwap * (1 + self.slippage_rate)
        else:  # 卖出，价格下降
            execution_price = vwap * (1 - self.slippage_rate)
        
        # 计算交易金额和手续费
        trade_value = abs(actual_quantity) * execution_price
        fee = trade_value * self.fee_rate
        
        # 计算交易PnL（相对于当前价格）
        # 新开仓位的PnL（实际成交价与窗口结束价的差异）
        window_end_price = aggtrade_loader.get_last_price(aggtrade_df, exec_end)
        if window_end_price is None:
            window_end_price = execution_price
        
        trade_pnl = actual_quantity * (window_end_price - execution_price)
        
        trade_info = {
            'symbol': symbol,
            'time': current_time,
            'target_quantity': trade_quantity,
            'actual_quantity': actual_quantity,
            'vwap': vwap,
            'execution_price': execution_price,
            'trade_value': trade_value,
            'fee': fee,
            'slippage': execution_price - vwap,
            'total_volume': total_volume,
            'max_tradable': max_tradable,
            'trade_pnl': trade_pnl,
            'window_end_price': window_end_price
        }
        
        logger.info(f"[{current_time}] {symbol}: 成交 {actual_quantity:.6f} @ {execution_price:.2f}, "
                   f"手续费={fee:.2f} USDT, 交易PnL={trade_pnl:.2f} USDT")
        
        return trade_info
    
    def update_positions(self, current_positions: dict, trades: dict) -> dict:
        """
        更新仓位（不更新保证金，保证金统一在main.py中更新）
        
        Args:
            current_positions: 当前仓位
            trades: 本周期交易记录
        
        Returns:
            new_positions: 更新后的仓位
        """
        new_positions = current_positions.copy()
        
        for symbol, trade_info in trades.items():
            # 更新仓位
            new_positions[symbol] = new_positions.get(symbol, 0) + trade_info['actual_quantity']
        
        return new_positions