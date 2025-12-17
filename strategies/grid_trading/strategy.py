import backtrader as bt
from .config import GridTradingParams
import csv
import os
from datetime import datetime


class GridTradingStrategy(bt.Strategy):
    """网格交易策略"""
    
    params = (
        ('initial_position_ratio', GridTradingParams.initial_position_ratio),
        ('grid_buy_percent', GridTradingParams.grid_buy_percent),
        ('grid_sell_percent', GridTradingParams.grid_sell_percent),
        ('trade_percent', GridTradingParams.trade_percent),
        ('max_position_ratio', GridTradingParams.max_position_ratio),
        ('min_position_ratio', GridTradingParams.min_position_ratio),
        ('output_folder', None),
    )
    
    def __init__(self):
        self.dataclose = self.datas[0].close
        self.order = None
        
        # 交易统计
        self.position_size = 0  # 持仓数量
        self.total_invested = 0  # 累计投入
        self.net_invested = 0  # 净投入
        self.max_net_invested = 0  # 最大净投入
        self.last_price = 0  # 上次交易价格
        self.initial_cash = GridTradingParams.total_initial_cash
        self.buy_count = 0
        self.sell_count = 0
        self.max_drawdown = 0
        self.max_value = 0
        
        # 现金流记录（用于IRR计算）
        self.cash_flows = []
        
        # 准备操作日志文件
        if self.p.output_folder:
            log_path = os.path.join(self.p.output_folder, 'operation_log.csv')
            self.op_log_file = open(log_path, 'w', newline='', encoding='utf-8')
            self.op_writer = csv.writer(self.op_log_file)
            self.op_writer.writerow([
                '日期', '操作类型', '成交价格', '操作数量', 
                '操作金额', '操作后持仓', '操作后市值', '相对上次涨跌幅',
                '手续费'
            ])
            
            # 详细日志
            detail_path = os.path.join(self.p.output_folder, 'details.csv')
            self.detail_log_file = open(detail_path, 'w', newline='', encoding='utf-8')
            self.detail_writer = csv.writer(self.detail_log_file)
            self.detail_writer.writerow([
                '日期', '当前价格', '持仓数量', '当前市值',
                '累计投入', '净投入', '最大回撤'
            ])
        else:
            self.op_log_file = None
            self.detail_log_file = None
        
        self.total_trades = 0
        self.initialized = False
    
    def stop(self):
        """策略结束时关闭文件"""
        if self.op_log_file:
            self.op_log_file.close()
        if self.detail_log_file:
            self.detail_log_file.close()
        
        # 输出最终统计
        self.print_final_stats()
    
    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            pass
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'订单被取消/保证金不足/被拒绝')
        
        self.order = None
    
    def next(self):
        """每个交易日执行"""
        current_date = self.datas[0].datetime.date(0)
        current_price = self.dataclose[0]
        
        # 初始建仓
        if not self.initialized:
            self.initial_buy(current_price, current_date)
            self.initialized = True
            return
        
        # 计算相对于上次交易的涨跌幅
        if self.last_price > 0:
            change_ratio = (current_price - self.last_price) / self.last_price
            
            # 下跌超过网格买入阈值，执行买入
            if change_ratio <= -self.p.grid_buy_percent:
                self.execute_buy(current_price, current_date, change_ratio)
            
            # 上涨超过网格卖出阈值，执行卖出
            elif change_ratio >= self.p.grid_sell_percent:
                self.execute_sell(current_price, current_date, change_ratio)
        
        # 更新回撤
        current_value = self.get_current_value(current_price)
        self.update_drawdown(current_value)
        
        # 记录每日详情
        if self.detail_writer:
            self.detail_writer.writerow([
                current_date.isoformat(),
                f'{current_price:.2f}',
                self.position_size,
                f'{current_value:.2f}',
                f'{self.total_invested:.2f}',
                f'{self.net_invested:.2f}',
                f'{self.max_drawdown*100:.2f}%'
            ])
    
    def initial_buy(self, price, date):
        """初始建仓"""
        initial_amount = self.initial_cash * self.p.initial_position_ratio
        shares = round(initial_amount / price, 2)
        
        if shares <= 0:
            self.log(f'初始资金不足，无法建仓')
            return
        
        actual_cost = shares * price
        commission = actual_cost * 0.00005
        
        # 更新统计
        self.position_size = shares
        self.total_invested = actual_cost
        self.net_invested = actual_cost
        self.max_net_invested = actual_cost  # 初始建仓时设置最大净投入
        self.last_price = price
        self.max_value = actual_cost
        
        # 记录现金流
        self.cash_flows.append((date, -actual_cost))
        
        self.total_trades += 1
        self.buy_count += 1
        
        self.log(f'初始建仓 {shares}股 @ {price:.2f}, 金额: {actual_cost:.2f}')
        
        if self.op_writer:
            self.op_writer.writerow([
                date.isoformat(),
                '初始建仓',
                f'{price:.2f}',
                shares,
                f'{actual_cost:.2f}',
                shares,
                f'{actual_cost:.2f}',
                '0.00%',
                f'{commission:.2f}'
            ])
    
    def execute_buy(self, price, date, change_ratio):
        """执行买入"""
        # 计算当前仓位比例
        current_value = self.get_current_value(price)
        current_position_ratio = current_value / self.initial_cash if self.initial_cash > 0 else 0
        
        # 检查是否超过最大仓位
        if current_position_ratio >= self.p.max_position_ratio:
            return
        
        # 计算买入金额（使用初始资金的trade_percent）
        buy_amount = self.initial_cash * self.p.trade_percent
        shares_to_buy = round(buy_amount / price, 2)
        
        if shares_to_buy <= 0:
            return
        
        actual_cost = shares_to_buy * price
        commission = actual_cost * 0.00005
        
        # 更新统计
        self.position_size += shares_to_buy
        self.total_invested += actual_cost
        self.net_invested += actual_cost
        
        # 更新最大净投入
        if self.net_invested > self.max_net_invested:
            self.max_net_invested = self.net_invested
        
        self.last_price = price
        
        # 记录现金流
        self.cash_flows.append((date, -actual_cost))
        
        self.total_trades += 1
        self.buy_count += 1
        
        self.log(f'网格买入 {shares_to_buy}股 @ {price:.2f}, 金额: {actual_cost:.2f}, 触发跌幅: {change_ratio*100:.2f}%')
        
        if self.op_writer:
            self.op_writer.writerow([
                date.isoformat(),
                '网格买入',
                f'{price:.2f}',
                shares_to_buy,
                f'{actual_cost:.2f}',
                self.position_size,
                f'{self.get_current_value(price):.2f}',
                f'{change_ratio*100:.2f}%',
                f'{commission:.2f}'
            ])
    
    def execute_sell(self, price, date, change_ratio):
        """执行卖出"""
        # 计算当前仓位比例
        current_value = self.get_current_value(price)
        current_position_ratio = current_value / self.initial_cash if self.initial_cash > 0 else 0
        
        # 检查是否低于最小仓位
        if current_position_ratio <= self.p.min_position_ratio:
            return
        
        # 计算卖出金额（使用初始资金的trade_percent）
        sell_amount = self.initial_cash * self.p.trade_percent
        shares_to_sell = round(sell_amount / price, 2)
        
        # 确保不卖出超过持仓
        if shares_to_sell > self.position_size:
            shares_to_sell = self.position_size
        
        if shares_to_sell <= 0:
            return
        
        actual_value = shares_to_sell * price
        commission = actual_value * 0.00005
        
        # 更新统计
        self.position_size -= shares_to_sell
        self.net_invested -= actual_value
        self.last_price = price
        
        # 记录现金流
        self.cash_flows.append((date, actual_value))
        
        self.total_trades += 1
        self.sell_count += 1
        
        self.log(f'网格卖出 {shares_to_sell}股 @ {price:.2f}, 金额: {actual_value:.2f}, 触发涨幅: {change_ratio*100:.2f}%')
        
        if self.op_writer:
            self.op_writer.writerow([
                date.isoformat(),
                '网格卖出',
                f'{price:.2f}',
                -shares_to_sell,
                f'{-actual_value:.2f}',
                self.position_size,
                f'{self.get_current_value(price):.2f}',
                f'{change_ratio*100:.2f}%',
                f'{commission:.2f}'
            ])
    
    def get_current_value(self, price):
        """获取当前市值"""
        return self.position_size * price
    
    def update_drawdown(self, current_value):
        """更新最大回撤"""
        if current_value > self.max_value:
            self.max_value = current_value
        
        if self.max_value > 0:
            drawdown = (self.max_value - current_value) / self.max_value
            if drawdown > self.max_drawdown:
                self.max_drawdown = drawdown
    
    def print_final_stats(self):
        """打印最终统计"""
        print("\n" + "="*80)
        print("网格交易策略 - 最终统计报告")
        print("="*80)
        
        final_price = self.dataclose[0]
        final_value = self.get_current_value(final_price)
        
        print(f"\n初始资金: {self.initial_cash:,.2f}")
        print(f"累计投入: {self.total_invested:,.2f}")
        print(f"累计净投入: {self.net_invested:,.2f}")
        print(f"期末市值: {final_value:,.2f}")
        print(f"绝对收益: {final_value - self.net_invested:,.2f}")
        print(f"交易次数: {self.total_trades} (买入:{self.buy_count}, 卖出:{self.sell_count})")
        print(f"最大回撤: {self.max_drawdown*100:.2f}%")
        
        print("\n" + "="*80)
    
    def log(self, txt, dt=None):
        """日志输出"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')
