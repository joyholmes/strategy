import backtrader as bt
import numpy as np
from .config import ValuationParams
import csv
import os
import datetime

class ValuationPandasData(bt.feeds.PandasData):
    lines = ('pe', 'pb',)
    params = (('pe', -1), ('pb', -1),)

class ValuationStrategy(bt.Strategy):
    """基于金字塔双线逻辑的估值策略 (Pyramid Buy/Sell & Hold)"""
    
    params = (
        ('total_initial_cash', ValuationParams.total_initial_cash),
        ('metric', ValuationParams.metric),
        ('lookback_years', ValuationParams.lookback_years),
        ('buy_tiers', ValuationParams.buy_tiers),
        ('sell_tiers', ValuationParams.sell_tiers),
        ('trade_start_date', None),
        ('output_folder', None),
    )
    
    def __init__(self):
        self.dataclose = self.datas[0].close
        self.datape = self.datas[0].pe
        self.datapb = self.datas[0].pb
        
        self.order = None
        self.target_position_size = 0.0
        
        # 统计变量
        self.net_invested = 0
        self.max_net_invested = 0
        self.total_trades = 0
        self.current_percentile = 0
        
        # 验证指标
        if self.p.metric == 'pe':
            self.valuation_data = self.datape
        else:
            self.valuation_data = self.datapb
        
        # 日期处理
        self.trade_start_dt = None
        if self.p.trade_start_date:
            self.trade_start_dt = datetime.datetime.strptime(self.p.trade_start_date, '%Y%m%d').date()

        # 日志初始化
        if self.p.output_folder:
            self.init_loggers(self.p.output_folder)

    def init_loggers(self, folder):
        log_path = os.path.join(folder, 'operation_log.csv')
        self.op_log_file = open(log_path, 'w', newline='', encoding='utf-8')
        self.op_writer = csv.writer(self.op_log_file)
        self.op_writer.writerow(['日期', '操作类型', '成交价格', '数量', '金额', '当前估值', '估值分位点', '目标仓位', '手续费'])
        
        detail_path = os.path.join(folder, 'details.csv')
        self.detail_log_file = open(detail_path, 'w', newline='', encoding='utf-8')
        self.detail_writer = csv.writer(self.detail_log_file)
        self.detail_writer.writerow(['日期', '收盘价', '估值指标', '估值分位点', '持仓市值', '现金', '总资产', '仓位比例', '信号'])

    def stop(self):
        if hasattr(self, 'op_log_file'):
            self.op_log_file.close()
            self.detail_log_file.close()
            
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            self.total_trades += 1
            op_type = '买入' if order.isbuy() else '卖出'
            cost = order.executed.value if order.isbuy() else -order.executed.value
            
            if order.isbuy():
                self.net_invested += cost
                if self.net_invested > self.max_net_invested:
                    self.max_net_invested = self.net_invested
            else:
                self.net_invested += cost
            
            self.log(f"订单完成: {op_type} {order.executed.size}股 @ {order.executed.price:.2f}, 金额: {cost:.2f}")
            
            if hasattr(self, 'op_writer'):
                self.op_writer.writerow([
                    self.datas[0].datetime.date(0), op_type, f"{order.executed.price:.2f}",
                    order.executed.size, f"{abs(cost):.2f}", f"{self.valuation_data[0]:.2f}",
                    f"{self.current_percentile:.2%}", f"{self.target_position_size:.2f}", f"{order.executed.comm:.2f}"
                ])
        self.order = None

    def next(self):
        current_val = self.valuation_data[0]
        if np.isnan(current_val) or current_val <= 0: return

        current_date_dt = self.datas[0].datetime.date(0)
        if self.trade_start_dt and current_date_dt < self.trade_start_dt: return

        # 计算分位点
        count = len(self)
        try:
            history_data = self.valuation_data.get(ago=0, size=count)
            history_vals = [v for v in history_data if not np.isnan(v) and v > 0]
        except: return
        
        if not history_vals: return
        self.current_percentile = (np.array(history_vals) < current_val).mean()
        
        # === 核心策略逻辑: 双线持仓控制 ===
        
        # 1. 计算"最低应有仓位" (Floor) - 由买入规则决定
        min_target_pos = 0.0
        for limit, target in self.p.buy_tiers:
            if self.current_percentile <= limit:
                # 找到满足条件的最大的仓位要求 (越低估仓位越大)
                # 假设 buy_tiers 按 limit 降序或无序，我们需要取 max
                if target > min_target_pos:
                    min_target_pos = target
                    
        # 2. 计算"最高允许仓位" (Ceiling) - 由卖出规则决定
        max_target_pos = 1.0
        for limit, target in self.p.sell_tiers:
            if self.current_percentile >= limit:
                # 找到满足条件的最小仓位限制 (越高估仓位越小)
                if target < max_target_pos:
                    max_target_pos = target
        
        # 3. 获取当前实际仓位状态 (0.0 ~ 1.0)
        # 注意: 这里使用 self.target_position_size 作为逻辑状态记录，
        # 而不是 broker.getposition，以避免因价格波动导致的市值变化干扰逻辑判断
        # (例如：想要保持50%，但因为涨了变成了55%，如果不调仓，逻辑上还是认为是"50%档位")
        # 但为了更稳健，我们还是看实际持仓比例，允许一定误差？
        # 不，对于"不操作"区间，我们应该维持的是 share 数量不变，还是 value 比例不变？
        # 通常估值策略是 value based。
        # 这里为了简单，我们比较"当前的逻辑目标"。
        
        # 决策生成
        current_logical_pos = self.target_position_size # 上一次设定的目标
        final_target_pos = current_logical_pos
        
        signal = "-"
        
        # 逻辑：如果不满足最低要求 -> 买入补足
        if current_logical_pos < min_target_pos:
            final_target_pos = min_target_pos
            signal = f"买入(补至{min_target_pos:.0%})"
            
        # 逻辑：如果超过最高限制 -> 卖出降低
        elif current_logical_pos > max_target_pos:
            final_target_pos = max_target_pos
            signal = f"卖出(降至{max_target_pos:.0%})"
            
        # 否则 -> 保持不动 (Hold)
        # 例如 current=0.7, min=0, max=1 -> 保持0.7
        else:
            final_target_pos = current_logical_pos
            signal = "持有"

        # 执行
        if final_target_pos != self.target_position_size:
            self.target_position_size = final_target_pos
            self.order_target_percent(target=final_target_pos)
        
        # 记录
        if hasattr(self, 'detail_writer'):
            value = self.broker.get_value()
            cash = self.broker.get_cash()
            pos_ratio = (value - cash) / value if value > 0 else 0
            self.detail_writer.writerow([
                current_date_dt, f"{self.dataclose[0]:.2f}", f"{current_val:.2f}",
                f"{self.current_percentile:.4f}", f"{value-cash:.2f}", f"{cash:.2f}",
                f"{value:.2f}", f"{pos_ratio:.4f}", signal
            ])

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')
