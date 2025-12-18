import backtrader as bt
import numpy as np
from .config import ValuationParams
import csv
import os
import datetime

# 自定义数据Feed以支持PE/PB
class ValuationPandasData(bt.feeds.PandasData):
    lines = ('pe', 'pb',)
    params = (
        ('pe', -1),
        ('pb', -1),
    )

class ValuationStrategy(bt.Strategy):
    """基于极限估值时机的交易策略 (Trigger & Hold)"""
    
    params = (
        ('total_initial_cash', ValuationParams.total_initial_cash),
        ('metric', ValuationParams.metric),
        ('lookback_years', ValuationParams.lookback_years),
        ('buy_percentile', ValuationParams.buy_percentile),
        ('sell_percentile', ValuationParams.sell_percentile),
        ('trade_start_date', None), # 开始交易日期，早于此日期的只计算不交易
        ('output_folder', None),
    )
    
    def __init__(self):
        self.dataclose = self.datas[0].close
        self.datape = self.datas[0].pe
        self.datapb = self.datas[0].pb
        
        self.order = None
        self.target_position_size = 0.0 # 这里的含义：期望的仓位状态 (1.0=满仓, 0.0=空仓)
        
        # 统计数据
        self.net_invested = 0
        self.max_net_invested = 0
        self.total_trades = 0
        self.current_percentile = 0
        
        # 验证数剧
        if self.p.metric == 'pe':
            self.valuation_data = self.datape
        else:
            self.valuation_data = self.datapb
        
        # 转换 trade_start_date
        self.trade_start_dt = None
        if self.p.trade_start_date:
            self.trade_start_dt = datetime.datetime.strptime(self.p.trade_start_date, '%Y%m%d').date()

        # 准备日志
        if self.p.output_folder:
            log_path = os.path.join(self.p.output_folder, 'operation_log.csv')
            self.op_log_file = open(log_path, 'w', newline='', encoding='utf-8')
            self.op_writer = csv.writer(self.op_log_file)
            self.op_writer.writerow([
                '日期', '操作类型', '成交价格', '数量', '金额', 
                '当前估值', '估值分位点', '目标仓位状态', '手续费'
            ])
            
            detail_path = os.path.join(self.p.output_folder, 'details.csv')
            self.detail_log_file = open(detail_path, 'w', newline='', encoding='utf-8')
            self.detail_writer = csv.writer(self.detail_log_file)
            self.detail_writer.writerow([
                '日期', '收盘价', '估值指标', '估值分位点', '持仓市值', 
                '现金', '总资产', '仓位比例', '信号'
            ])

    def stop(self):
        if hasattr(self, 'op_log_file'):
            self.op_log_file.close()
            self.detail_log_file.close()
            
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            self.total_trades += 1
            if order.isbuy():
                op_type = '买入'
                cost = order.executed.value
                self.net_invested += cost
                if self.net_invested > self.max_net_invested:
                    self.max_net_invested = self.net_invested
            else:
                op_type = '卖出'
                cost = -order.executed.value
                self.net_invested += cost # 卖出减少净投入
            
            self.log(f"订单完成: {op_type} {order.executed.size}股 @ {order.executed.price:.2f}, 金额: {cost:.2f}")
            
            if hasattr(self, 'op_writer'):
                self.op_writer.writerow([
                    self.datas[0].datetime.date(0),
                    op_type,
                    f"{order.executed.price:.2f}",
                    order.executed.size,
                    f"{abs(cost):.2f}",
                    f"{self.valuation_data[0]:.2f}",
                    f"{self.current_percentile:.2%}",
                    f"{self.target_position_size:.2f}",
                    f"{order.executed.comm:.2f}"
                ])
                
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log("订单取消/拒绝")
            
        self.order = None

    def next(self):
        # 检查估值数据是否存在
        current_val = self.valuation_data[0]
        if np.isnan(current_val) or current_val <= 0:
            return

        # 判断是否到达交易开始时间
        current_date_dt = self.datas[0].datetime.date(0)
        
        # 预热期：只计算，不记录详情(可选)，绝对不交易
        if self.trade_start_dt and current_date_dt < self.trade_start_dt:
            # 即使在预热期，我们也可以计算分位点，但为了效率和逻辑简单，这里不交易
            # 但我们需要计算分位点以便观察?
            # 不，Backtrader的预加载数据对于计算分位点是必须的，
            # 这里我们假设数据已经充足（通过 fetch_start_date 控制）
            return

        # 获取历史数据用于计算分位点 (全历史窗口)
        # 注意: 这里使用 len(self) 获取当前已处理的 BAR 数量
        # valuation_data 包含了预热数据
        # 我们希望窗口是: 从"数据开始"到"昨天" (或者包含今天?) 
        # 为了避免未来函数，分位点应该基于截止到今日的数据分布
        
        # 使用动态窗口: 从数据源头到现在
        count = len(self)
        try:
            # 获取所有历史数据 (Backtrader array index 0 is now, -1 is yesterday)
            # using get(ago=0, size=count) returns [t-(count-1), ..., t]
            history_data = self.valuation_data.get(ago=0, size=count)
            history_vals = [v for v in history_data if not np.isnan(v) and v > 0]
        except:
            # 数据不足时
            return
        
        if not history_vals:
            return
            
        # 计算分位点 (Percentile Rank)
        # 计算当前值在历史中的排名
        self.current_percentile = (np.array(history_vals) < current_val).mean()
        
        # === 核心策略逻辑 (Trigger & Hold) ===
        current_pos_size = self.broker.getposition(self.data).size
        is_holding = current_pos_size > 0
        
        signal = "-"
        
        if not is_holding:
            # 空仓状态: 等待买入时机 (低估)
            if self.current_percentile <= self.p.buy_percentile:
                signal = "BUY_SIGNAL"
                self.target_position_size = 1.0
                self.order_target_percent(target=1.0) # 满仓买入
            else:
                # 保持空仓
                self.target_position_size = 0.0
        else:
            # 持仓状态: 等待卖出时机 (高估)
            if self.current_percentile >= self.p.sell_percentile:
                signal = "SELL_SIGNAL"
                self.target_position_size = 0.0
                self.order_target_percent(target=0.0) # 清仓卖出
            else:
                # 保持持仓 (Hold)
                self.target_position_size = 1.0
        
        # 记录每日详情
        if hasattr(self, 'detail_writer'):
            value = self.broker.get_value()
            cash = self.broker.get_cash()
            position_val = value - cash
            pos_ratio = position_val / value if value > 0 else 0
            
            self.detail_writer.writerow([
                current_date_dt,
                f"{self.dataclose[0]:.2f}",
                f"{current_val:.2f}",
                f"{self.current_percentile:.4f}",
                f"{position_val:.2f}",
                f"{cash:.2f}",
                f"{value:.2f}",
                f"{pos_ratio:.4f}",
                signal
            ])

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')
