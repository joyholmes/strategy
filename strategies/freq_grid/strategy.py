import math
import backtrader as bt
import numpy as np
from .config import GridParams

class FreqGridStrategy(bt.Strategy):
    params = (
        ('Ao', GridParams.Ao),
        ('Af', GridParams.Af),
        ('Bo', GridParams.Bo),
        ('Bf', GridParams.Bf),
        ('threshold_mode', GridParams.threshold_mode),
        ('fixed_threshold', GridParams.fixed_threshold),
        ('output_folder', None),
        ('buffer_days', GridParams.buffer_days),
    )

    def __init__(self):
        # 核心数据
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        
        # 指标: ATR (用于动态阈值)
        self.atr = bt.indicators.ATR(self.datas[0], period=GridParams.atr_period)
        
        # 状态机变量
        self.zone = 'A'        # 当前区域
        self.Ba = 0.0          # 实际累计投入本金
        self.S_acc = 0.0       # 累计减仓回收资金
        self.P_op = 0.0        # 最近操作基准价
        
        # 快照变量 (D1, D2, D3)
        self.D1 = 0            # Zone C snapshot
        self.D2 = 0            # Zone D snapshot
        self.D3 = 0            # Zone E snapshot
        
        # 缓冲机制
        self.pending_zone = None
        self.pending_days = 0
        
        # 计算系数 K
        self.K = 0.0
        
        # 阶梯减仓计数器
        self.rise_count = 0
        
        # 统计
        self.max_Ba = 0.0
        self.total_trades = 0
        
        # 记录器
        self.op_writer = None
        self.detail_writer = None

    def start(self):
        if self.p.Ao > 0 and self.p.Af > 0 and self.p.Bo > 0 and self.p.Bf > 0:
             self.K = math.log(self.p.Bf / self.p.Bo) / math.log(self.p.Ao / self.p.Af)
        
        if self.p.output_folder:
            import csv
            import os
            op_path = os.path.join(self.p.output_folder, 'operation_log.csv')
            self.op_file = open(op_path, 'w', newline='', encoding='utf-8')
            self.op_writer = csv.writer(self.op_file)
            self.op_writer.writerow(['Date', 'Type', 'Price', 'Shares', 'Amount', 'Zone', 'Yield', 'Ba', 'S_acc'])
            
            det_path = os.path.join(self.p.output_folder, 'details.csv')
            self.det_file = open(det_path, 'w', newline='', encoding='utf-8')
            self.detail_writer = csv.writer(self.det_file)
            self.detail_writer.writerow(['Date', 'Close', 'Zone', 'Yield', 'PositionVal(Bc)', 'Ba', 'S_acc', 'LogicPos', 'Threshold', 'NextBuy', 'NextSell'])

    def stop(self):
        if hasattr(self, 'op_file'): self.op_file.close()
        if hasattr(self, 'det_file'): self.det_file.close()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]: return
        
        if order.status == order.Completed:
            price = order.executed.price
            size = order.executed.size 
            value = price * abs(size)
            
            if order.isbuy():
                self.Ba += value 
                if self.Ba > self.max_Ba: self.max_Ba = self.Ba
                op_type = "Buy"
                self.rise_count = 0 # 重置上涨计数
            else:
                self.S_acc += value 
                op_type = "Sell"
                self.rise_count += 1 # 增加上涨计数
                
            self.total_trades += 1
            # 关键修复: 每次成交后，都需要重置 P_op 为成交价
            # 文档中Zone F特别说明不更新，但为捕捉"下一个2%"，技术上仍需锚点。
            # 保持一致性，每次交易更新基准价。
            self.P_op = price 
            
            if self.op_writer:
                dt = self.datas[0].datetime.date(0)
                Bc = self.broker.get_value() - self.broker.get_cash()
                cur_yield = (Bc - self.Ba)/self.Ba if self.Ba > 0 else 0
                self.op_writer.writerow([dt, op_type, f"{price:.2f}", size, f"{value:.2f}", self.zone, f"{cur_yield:.2%}", f"{self.Ba:.2f}", f"{self.S_acc:.2f}"])
                
        self.order = None

    def get_threshold(self, price):
        if self.p.threshold_mode == 'dynamic':
            atr = self.atr[0]
            if price <= 0: return self.p.fixed_threshold
            delta = GridParams.atr_multiplier * atr / price
            return max(GridParams.dynamic_min, min(GridParams.dynamic_max, delta))
        else:
            return self.p.fixed_threshold

    def calculate_pyramid_target(self, current_price):
        if current_price >= self.p.Ao: return self.p.Bo
        if current_price <= self.p.Af: return self.p.Bf
        try:
             ratio = self.p.Ao / current_price
             # 金字塔核心公式
             target = self.p.Bo * (ratio ** self.K)
             return min(target, self.p.Bf)
        except:
             return self.p.Bo

    def next(self):
        dt = self.datas[0].datetime.date(0)
        price = self.dataclose[0]
        
        # 1. 初始化
        if self.Ba == 0:
            self.buy(size=int(self.p.Bo / price))
            if self.P_op == 0: self.P_op = price
            return

        # 2. 计算收益率
        Bc = self.broker.get_value() - self.broker.get_cash()
        Current_Yield = (Bc - self.Ba) / self.Ba if self.Ba > 0 else 0
        
        # 3. 区域状态切换
        target_zone = self.zone
        if self.zone == 'A':
            if Current_Yield < -0.30: target_zone = 'B'
            elif Current_Yield >= 0.15: target_zone = 'D'
        elif self.zone == 'B':
            if Current_Yield >= -0.30: target_zone = 'C'
        elif self.zone == 'C':
            if Current_Yield < -0.30: target_zone = 'B'
            elif Current_Yield >= 0.005: target_zone = 'D'
        elif self.zone == 'D':
            if Current_Yield < -0.005: target_zone = 'C'
            elif self.S_acc > 0.15 * self.Ba: target_zone = 'E'
        elif self.zone == 'E':
            if self.S_acc <= 0.15 * self.Ba: target_zone = 'D'
            elif self.S_acc >= 0.99 * self.Ba: target_zone = 'F'
        
        # Buffer Logic
        if target_zone != self.zone:
            if self.pending_zone == target_zone:
                self.pending_days += 1
            else:
                self.pending_zone = target_zone
                self.pending_days = 1
            
            if self.pending_days >= self.p.buffer_days:
                # Confirm Switch
                if target_zone == 'C': self.D1 = self.position.size
                elif target_zone == 'D': self.D2 = self.position.size
                elif target_zone == 'E': self.D3 = self.position.size
                
                self.P_op = price 
                self.rise_count = 0 # 切换区域重置计数
                
                self.zone = target_zone
                self.pending_zone = None
                self.pending_days = 0
        else:
            self.pending_zone = None
            self.pending_days = 0

        # 4. 执行交易
        delta = self.get_threshold(price)
        if self.order: return 

        next_buy_price = self.P_op * (1 - delta)
        next_sell_price = self.P_op * (1 + delta)
        
        # 区域 A & B: 金字塔加仓
        if self.zone in ['A', 'B']:
            if price <= next_buy_price:
                Bg = self.calculate_pyramid_target(price)
                if self.zone == 'B' and self.Ba >= self.p.Bf: pass
                elif Bg > Bc:
                    diff_val = Bg - Bc
                    size = int(diff_val / price)
                    if size > 0: self.buy(size=size)

        # 区域 A: 减仓
        if self.zone == 'A':
            if price >= next_sell_price:
                size = int(self.position.size * 0.02)
                if size > 0: self.sell(size=size)

        # 区域 C: 亏损可控区 - 阶梯减仓
        if self.zone == 'C':
            if price >= next_sell_price:
                # 第1次: 0.5%, 第2次: 1.0%, 第3次+: 2.0%
                ratios = [0.005, 0.010, 0.020]
                ratio = ratios[min(self.rise_count, 2)]
                
                size = int(self.D1 * ratio)
                if size > 0: self.sell(size=size)
            elif price <= next_buy_price:
                size = int(self.D1 * 0.005)
                if size > 0: self.buy(size=size)

        # 区域 D: 盈利本金慢速置换 - 阶梯减仓
        if self.zone == 'D':
            if price >= next_sell_price:
                 # 第1次: 1.0%, 第2次: 1.5%, 第3次+: 2.0%
                 ratios = [0.010, 0.015, 0.020]
                 ratio = ratios[min(self.rise_count, 2)]
                 
                 size = int(self.D2 * ratio) 
                 if size > 0: self.sell(size=size)
            elif price <= next_buy_price:
                 size = int(self.D2 * 0.01)
                 if size > 0: self.buy(size=size)

        # 区域 E: 盈利本金快速置换 - 阶梯减仓 & 特殊加仓阈值
        if self.zone == 'E':
            if price >= next_sell_price:
                 # 第1次: 2.0%, 第2次: 4.0%, 第3次+: 6.0%
                 ratios = [0.020, 0.040, 0.060]
                 ratio = ratios[min(self.rise_count, 2)]
                 
                 size = int(self.D3 * ratio)
                 if size > 0: self.sell(size=size)
            else:
                # 加仓阈值: 文档指定 "10% 或 2倍动态阈值"
                buy_threshold = 0.10 if self.p.threshold_mode == 'fixed' else 2 * delta
                if price <= self.P_op * (1 - buy_threshold): 
                     size = int(self.D3 * 0.01)
                     if size > 0: self.buy(size=size)
                 
        # Zone F: Compounding (Pure Profit Phase)
        # 此时本金已全部收回，全是利润在奔跑。
        if self.zone == 'F':
            # 使用较小的阈值 (例如 fixed_threshold的一半，或 2%)
            f_delta = max(0.02, delta * 0.5)
            f_next_buy = self.P_op * (1 - f_delta)
            f_next_sell = self.P_op * (1 + f_delta)
            
            if price >= f_next_sell:
                # 止盈 1% 仓位
                size = int(self.position.size * 0.01)
                if size > 0: self.sell(size=size)
            elif price <= f_next_buy:
                # 复利加仓 1% (注意: 此时全是利润，大胆加)
                valid_size = self.position.size if self.position.size > 0 else 1000
                size = int(valid_size * 0.01)
                if size > 0: self.buy(size=size)

        if self.detail_writer:
             self.detail_writer.writerow([
                 dt, f"{price:.2f}", self.zone, f"{Current_Yield:.2%}", 
                 f"{Bc:.2f}", f"{self.Ba:.2f}", f"{self.S_acc:.2f}", 
                 "-", f"{delta:.2%}", f"{next_buy_price:.2f}", f"{next_sell_price:.2f}"
             ])
