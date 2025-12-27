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
    """
    估值动态网格策略 (Valuation Dynamic Grid)
    核心公式: 目标仓位 = 1 - 当前分位
    交易触发: 
      - 低估区: 买入阈值极小 (容易买), 卖出阈值极大 (难卖)
      - 高估区: 卖出阈值极小 (容易卖), 买入阈值极大 (难买)
    """
    
    params = (
        ('total_initial_cash', ValuationParams.total_initial_cash),
        ('metric', ValuationParams.metric),
        ('lookback_years', ValuationParams.lookback_years),
        ('min_threshold', ValuationParams.min_threshold),
        ('max_threshold', ValuationParams.max_threshold),
        ('full_pos_quantile', ValuationParams.full_pos_quantile),
        ('empty_pos_quantile', ValuationParams.empty_pos_quantile),
        ('convex_hold_k', ValuationParams.convex_hold_k),
        ('reference_values', None), # 固定的历史参考数据
        ('trade_start_date', None),
        ('output_folder', None),
    )
    
    def __init__(self):
        self.dataclose = self.datas[0].close
        self.datape = self.datas[0].pe
        self.datapb = self.datas[0].pb
        
        self.order = None
        self.target_position_size = 0.0 # 记录上一次下达的目标仓位
        
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
            
        # 预处理参考数据
        self.ref_history_vals = None
        if self.p.reference_values and len(self.p.reference_values) > 0:
            self.ref_history_vals = np.array([x for x in self.p.reference_values if not np.isnan(x) and x > 0])
            print(f"策略已加载固定参考区间数据: {len(self.ref_history_vals)} 条记录")
        
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
        self.detail_writer.writerow(['日期', '收盘价', '估值指标', '估值分位点', '持仓市值', '现金', '总资产', '实际仓位', '目标仓位', '买入阈值', '卖出阈值', '信号'])

    def stop(self):
        if hasattr(self, 'op_log_file'):
            self.op_log_file.close()
            self.detail_log_file.close()
            
    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Margin, order.Rejected, order.Canceled]:
            self.log(f"订单未完成: 状态={order.getstatusname()}")
            self.order = None
            return
        
        if order.status in [order.Completed]:
            self.total_trades += 1
            execution_amount = order.executed.price * abs(order.executed.size)
            
            if order.isbuy():
                op_type = '买入'
                self.net_invested += execution_amount
                if self.net_invested > self.max_net_invested:
                    self.max_net_invested = self.net_invested
            else:
                op_type = '卖出'
                self.net_invested -= execution_amount
            
            self.log(f"订单完成: {op_type} {order.executed.size}股 @ {order.executed.price:.2f}, 金额: {execution_amount:.2f}")
            
            if hasattr(self, 'op_writer'):
                self.op_writer.writerow([
                    self.datas[0].datetime.date(0), op_type, f"{order.executed.price:.2f}",
                    order.executed.size, f"{execution_amount:.2f}", f"{self.valuation_data[0]:.2f}",
                    f"{self.current_percentile:.2%}", f"{self.target_position_size:.2f}", f"{order.executed.comm:.2f}"
                ])
        self.order = None

    def calculate_thresholds(self, percentile):
        """
        计算动态非对称阈值
        - 低分位(0%): Buy_Thresh = Min, Sell_Thresh = Max
        - 高分位(100%): Buy_Thresh = Max, Sell_Thresh = Min
        线性插值
        """
        min_t = self.p.min_threshold
        max_t = self.p.max_threshold
        
        # 买入阈值: 分位约低，阈值越小 (越灵敏)
        # linear mapping: 0 -> min, 1 -> max
        buy_threshold = min_t + (max_t - min_t) * percentile
        
        # 卖出阈值: 分位越低，阈值越大 (越迟钝)
        # linear mapping: 0 -> max, 1 -> min
        sell_threshold = max_t - (max_t - min_t) * percentile
        
        return buy_threshold, sell_threshold

    def next(self):
        current_val = self.valuation_data[0]
        if np.isnan(current_val) or current_val <= 0: return

        current_date_dt = self.datas[0].datetime.date(0)
        if self.trade_start_dt and current_date_dt < self.trade_start_dt: return

        # 1. 计算分位点
        if self.ref_history_vals is not None:
            self.current_percentile = (self.ref_history_vals < current_val).mean()
        else:
            count = len(self)
            try:
                history_data = self.valuation_data.get(ago=0, size=count)
                history_vals = [v for v in history_data if not np.isnan(v) and v > 0]
            except: return
            if not history_vals: return
            self.current_percentile = (np.array(history_vals) < current_val).mean()
        
        # 2. 计算理想目标仓位 (Anchor) - 凸函数映射 (Convex Function)
        # 实现"低位吸筹，中位死拿，高位才卖"
        full_limit = self.p.full_pos_quantile
        empty_limit = self.p.empty_pos_quantile
        k = self.p.convex_hold_k
        
        if self.current_percentile <= full_limit:
            ideal_target_pos = 1.0
        elif self.current_percentile >= empty_limit:
            ideal_target_pos = 0.0
        else:
            # 归一化分位点到 0~1 区间
            # norm_p = 0 (at full_limit) -> 1 (at empty_limit)
            norm_p = (self.current_percentile - full_limit) / (empty_limit - full_limit)
            
            # 使用幂函数实现滞后卖出: y = 1 - x^k
            # 当 k > 1 时，x 在 0~0.5 时，x^k 很小，y 依然接近 1
            ideal_target_pos = 1.0 - (norm_p ** k)
            
        # 3. 计算动态阈值
        buy_thresh, sell_thresh = self.calculate_thresholds(self.current_percentile)
        
        # 4. 获取当前实际仓位
        value = self.broker.get_value()
        cash = self.broker.get_cash()
        actual_pos_percent = (value - cash) / value if value > 0 else 0
        
        # 5. 决策生成 (基于缓冲区的状态机)
        final_target_pos = self.target_position_size # 默认保持上一次的目标 (假设不动)
        
        # 实际上，如果"不动"，也应该让 target 跟随 actual ? 
        # 不，Backtrader 中 order_target_percent 是状态。
        # 如果我们不发单，target_position_size 应该等于 actual_pos_percent (随着市值波动)
        # 但为了逻辑清晰，我们只在产生信号时更新 self.target_position_size
        
        # 计算偏差: 理想 - 实际
        # diff > 0: 说明仓位不足，想买
        # diff < 0: 说明仓位过多，想卖
        diff = ideal_target_pos - actual_pos_percent
        
        signal = "持有"
        
        # 触发买入: 偏差 > 买入阈值 (说明仓位显著低于理想值，且超过了阻尼)
        # 低位时 buy_thresh 很小，稍微一点偏差就买
        if diff > buy_thresh:
            final_target_pos = ideal_target_pos
            signal = f"买入(缺口{diff:.1%}>{buy_thresh:.1%})"
            
        # 触发卖出: 偏差 < -卖出阈值 (说明仓位显著高于理想值，且偏离了阻尼)
        # 低位时 sell_thresh 很大，要偏离很多才卖
        elif diff < -sell_thresh:
            final_target_pos = ideal_target_pos
            signal = f"卖出(过剩{-diff:.1%}>{sell_thresh:.1%})"
            
        else:
            # 在缓冲区内，不做任何操作
            # 但为了防止 target_position_size 变量与实际脱节太久(仅用于log)，可以校准一下
            final_target_pos = actual_pos_percent
            
        # 6. 执行
        # 只有当确定的 final_target 与当前实际仓位有显著差异(也是阈值判断的一部分)时，order_target 会自动处理
        # 这里只要 signal 不是持有，或者我们显式更新了 target
        if signal != "持有":
            self.target_position_size = final_target_pos
            self.order_target_percent(target=final_target_pos)
            self.log(f"信号触发: {signal}, 调整仓位至 {final_target_pos:.2%}")
        else:
            self.target_position_size = actual_pos_percent # 仅用于记录

        # 7. 记录
        if hasattr(self, 'detail_writer'):
            self.detail_writer.writerow([
                current_date_dt, f"{self.dataclose[0]:.2f}", f"{current_val:.2f}",
                f"{self.current_percentile:.4f}", f"{value-cash:.2f}", f"{cash:.2f}",
                f"{value:.2f}", f"{actual_pos_percent:.4f}", f"{ideal_target_pos:.4f}",
                f"{buy_thresh:.4f}", f"{sell_thresh:.4f}", signal
            ])

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')
