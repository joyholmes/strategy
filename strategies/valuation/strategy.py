import backtrader as bt
import numpy as np
from .config import ValuationParams
import csv
import os

# 自定义数据Feed以支持PE/PB
class ValuationPandasData(bt.feeds.PandasData):
    lines = ('pe', 'pb',)
    params = (
        ('pe', -1),
        ('pb', -1),
    )

class ValuationStrategy(bt.Strategy):
    """基于PE/PB估值分位点的交易策略"""
    
    params = (
        ('total_initial_cash', ValuationParams.total_initial_cash),
        ('metric', ValuationParams.metric),
        ('lookback_years', ValuationParams.lookback_years),
        ('position_tiers', ValuationParams.position_tiers),
        ('output_folder', None),
    )
    
    def __init__(self):
        self.dataclose = self.datas[0].close
        self.datape = self.datas[0].pe
        self.datapb = self.datas[0].pb
        
        self.order = None
        
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
            
        # 准备日志
        if self.p.output_folder:
            log_path = os.path.join(self.p.output_folder, 'operation_log.csv')
            self.op_log_file = open(log_path, 'w', newline='', encoding='utf-8')
            self.op_writer = csv.writer(self.op_log_file)
            self.op_writer.writerow([
                '日期', '操作类型', '成交价格', '数量', '金额', 
                '当前估值', '估值分位点', '目标仓位', '手续费'
            ])
            
            detail_path = os.path.join(self.p.output_folder, 'details.csv')
            self.detail_log_file = open(detail_path, 'w', newline='', encoding='utf-8')
            self.detail_writer = csv.writer(self.detail_log_file)
            self.detail_writer.writerow([
                '日期', '收盘价', '估值指标', '估值分位点', '持仓市值', 
                '现金', '总资产', '仓位比例', '目标仓位'
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
                    f"{self.target_position_size:.2f}", # 注意：这不是准确的当前仓位，是目标
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

        # 获取历史数据用于计算分位点
        # Backtrader获取历史数据: self.valuation_data.get(ago=0, size=lookback_days)
        # 简单估算：lookback_years * 252
        lookback_days = int(self.p.lookback_years * 252)
        
        # 确保有足够的数据计算分位点
        if len(self) < lookback_days:
            # 数据不足时，可以使用至今为止的所有数据，或者不操作
            # 这里选择使用至今所有数据
            history_data = self.valuation_data.get(ago=0, size=len(self))
        else:
            history_data = self.valuation_data.get(ago=0, size=lookback_days)
            
        history_vals = [v for v in history_data if not np.isnan(v) and v > 0]
        
        if not history_vals:
            return
            
        # 计算分位点 (Percentile Rank)
        # 使用 scipy.stats.percentileofscore 或者简单的 numpy 统计
        self.current_percentile = (np.array(history_vals) < current_val).mean()
        
        # 确定目标仓位
        target_pos = 0.0
        for limit, pos in self.p.position_tiers:
            if self.current_percentile <= limit:
                target_pos = pos
                break
        
        self.target_position_size = target_pos # 记录一下用于日志
        
        # 执行调仓
        # order_target_percent 会自动计算需要买卖的数量
        self.order_target_percent(target=target_pos)
        
        # 记录每日详情
        if hasattr(self, 'detail_writer'):
            value = self.broker.get_value()
            cash = self.broker.get_cash()
            position_val = value - cash
            pos_ratio = position_val / value if value > 0 else 0
            
            self.detail_writer.writerow([
                self.datas[0].datetime.date(0),
                f"{self.dataclose[0]:.2f}",
                f"{current_val:.2f}",
                f"{self.current_percentile:.4f}",
                f"{position_val:.2f}",
                f"{cash:.2f}",
                f"{value:.2f}",
                f"{pos_ratio:.4f}",
                f"{target_pos:.2f}"
            ])

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')
