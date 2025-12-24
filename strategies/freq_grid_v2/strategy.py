"""
Freq Grid Strategy V2 - 核心策略实现

优化点：
1. 修复加仓公式实现错误
2. 完善区域转换逻辑和仓位恢复机制
3. 实现全局核算体系
4. 资金使用优先级管理
5. 完善的状态转换缓冲机制
"""

import math
import backtrader as bt
from .config import StrategyConfig


class FreqGridV2Strategy(bt.Strategy):
    """优化版动态网格仓位管理策略"""
    
    params = (
        ('Ao', StrategyConfig.Ao),
        ('Af', StrategyConfig.Af),
        ('Bo', StrategyConfig.Bo),
        ('Bf', StrategyConfig.Bf),
        ('threshold_mode', StrategyConfig.threshold_mode),
        ('fixed_threshold', StrategyConfig.fixed_threshold),
        ('buffer_days', StrategyConfig.buffer_days),
        ('output_folder', None),
    )

    def __init__(self):
        """初始化策略"""
        # === 价格数据 ===
        self.dataclose = self.datas[0].close
        self.datahigh = self.datas[0].high
        self.datalow = self.datas[0].low
        
        # === 技术指标 ===
        self.atr = bt.indicators.ATR(self.datas[0], period=StrategyConfig.atr_period)
        
        # === 核心状态变量 ===
        self.zone = 'A'              # 当前区域
        self.Ba = 0.0                # 实际累计投入本金
        self.Bc = 0.0                # 当前持仓市值
        self.Bg = 0.0                # 目标仓位金额 (重要！用于金字塔加仓)
        self.S_acc = 0.0             # 累计减仓回收资金
        self.P_op = 0.0              # 最近操作基准价
        
        # === 快照变量 (保存进入关键区域时的股数) ===
        self.D1 = 0                  # 进入区域C时的股数
        self.D2 = 0                  # 进入区域D时的股数
        self.D3 = 0                  # 进入区域E时的股数
        
        # === 阶梯减仓计数器 ===
        self.rise_count = 0          # 连续上涨触发次数 (用于阶梯减仓)
        
        # === 缓冲机制 ===
        self.pending_zone = None     # 待转换的目标区域
        self.pending_days = 0        # 已维持天数
        
        # === 金字塔系数 K ===
        self.K = 0.0
        
        # === 全局核算变量 ===
        self.total_invested = 0.0    # 总投入本金 (所有加仓累计)
        self.total_withdrawn = 0.0   # 总回收现金 (所有减仓累计)
        self.cash_balance = 0.0      # 现金账户余额 (初始化时设置)
        
        # === 统计变量 ===
        self.max_Ba = 0.0            # 历史最大投入
        self.total_trades = 0        # 总交易次数
        self.max_cash_usage = 0.0    # 最大现金占用
        
        # === 区域F增强模块 ===
        self.f_highest_price = 0.0   # 区域F期间的最高价
        self.c_base_price = 0.0      # 最后一次进入C区时的价格
        self.reentry_count = 0       # 重新建仓次数
        self.last_reentry_date = None
        
        # === 日志记录器 ===
        self.op_writer = None
        self.detail_writer = None

    def start(self):
        """策略启动时调用"""
        # 计算金字塔系数 K
        if self.p.Ao > 0 and self.p.Af > 0 and self.p.Bo > 0 and self.p.Bf > 0:
            self.K = math.log(self.p.Bf / self.p.Bo) / math.log(self.p.Ao / self.p.Af)
        
        # 初始化 Bg 为 Bo
        self.Bg = self.p.Bo
        
        # 初始化现金账户
        self.cash_balance = self.broker.get_cash()
        
        # 创建日志文件
        if self.p.output_folder:
            import csv
            import os
            
            # 操作日志
            op_path = os.path.join(self.p.output_folder, 'operations.csv')
            self.op_file = open(op_path, 'w', newline='', encoding='utf-8')
            self.op_writer = csv.writer(self.op_file)
            self.op_writer.writerow([
                'Date', 'Type', 'Price', 'Shares', 'Amount', 'Zone', 
                'Yield_i', 'Ba', 'Bc', 'S_acc', 'CashBalance'
            ])
            
            # 每日明细
            det_path = os.path.join(self.p.output_folder, 'daily_details.csv')
            self.det_file = open(det_path, 'w', newline='', encoding='utf-8')
            self.detail_writer = csv.writer(self.det_file)
            self.detail_writer.writerow([
                'Date', 'Close', 'Zone', 'Yield_i', 'Bc', 'Ba', 'S_acc', 
                'CashBalance', 'TotalAssets', 'GlobalYield', 
                'Threshold', 'NextBuy', 'NextSell', 'RiseCount'
            ])

    def stop(self):
        """策略结束时调用"""
        if hasattr(self, 'op_file'):
            self.op_file.close()
        if hasattr(self, 'det_file'):
            self.det_file.close()

    def notify_order(self, order):
        """订单通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status == order.Completed:
            price = order.executed.price
            size = order.executed.size
            value = price * abs(size)
            
            if order.isbuy():
                # 加仓逻辑
                # 优先使用累计减仓资金
                if self.S_acc >= value:
                    self.S_acc -= value
                else:
                    # 不足部分使用新资金
                    new_money = value - self.S_acc
                    self.S_acc = 0
                    self.Ba += new_money
                    self.total_invested += new_money
                    self.cash_balance -= new_money
                
                # 更新统计
                if self.Ba > self.max_Ba:
                    self.max_Ba = self.Ba
                
                # 更新现金占用
                current_usage = self.total_invested - self.total_withdrawn
                if current_usage > self.max_cash_usage:
                    self.max_cash_usage = current_usage
                
                op_type = "BUY"
                self.rise_count = 0  # 加仓后重置上涨计数
                
            else:
                # 减仓逻辑
                self.S_acc += value
                self.total_withdrawn += value
                self.cash_balance += value
                
                op_type = "SELL"
                self.rise_count += 1  # 减仓后增加上涨计数
            
            # 更新操作基准价 (除了区域F的特殊情况)
            self.P_op = price
            self.total_trades += 1
            
            # 记录操作日志
            if self.op_writer:
                dt = self.datas[0].datetime.date(0)
                self.Bc = self.broker.get_value() - self.broker.get_cash()
                cur_yield = (self.Bc - self.Ba) / self.Ba if self.Ba > 0 else 0
                
                self.op_writer.writerow([
                    dt, op_type, f"{price:.4f}", size, f"{value:.2f}", 
                    self.zone, f"{cur_yield:.4f}", f"{self.Ba:.2f}", 
                    f"{self.Bc:.2f}", f"{self.S_acc:.2f}", f"{self.cash_balance:.2f}"
                ])
        
        self.order = None

    def get_threshold(self, price):
        """获取动态或固定阈值"""
        if self.p.threshold_mode == 'dynamic':
            atr = self.atr[0]
            if price <= 0:
                return self.p.fixed_threshold
            
            delta = StrategyConfig.atr_multiplier * atr / price
            return max(StrategyConfig.dynamic_min, min(StrategyConfig.dynamic_max, delta))
        else:
            return self.p.fixed_threshold

    def calculate_pyramid_target(self, current_price):
        """
        计算金字塔目标仓位
        
        使用文档中的公式：
        y = 100 × (1 - x/100)^(-K) - 100
        Bg_new = Bg × (1 + y/100)
        
        但为了简化，我们直接使用等价的金字塔公式：
        Bg = Bo × (Ao / current_price)^K
        """
        if current_price >= self.p.Ao:
            return self.p.Bo
        
        if current_price <= self.p.Af:
            return self.p.Bf
        
        try:
            ratio = self.p.Ao / current_price
            target = self.p.Bo * (ratio ** self.K)
            return min(target, self.p.Bf)
        except:
            return self.p.Bo

    def next(self):
        """每个交易日调用"""
        dt = self.datas[0].datetime.date(0)
        price = self.dataclose[0]
        
        # === 1. 初始建仓 ===
        if self.Ba == 0 and self.position.size == 0:
            size = int(self.p.Bo / price)
            if size > 0:
                self.order = self.buy(size=size)
                if self.P_op == 0:
                    self.P_op = price
            return
        
        # === 2. 计算当前状态 ===
        self.Bc = self.broker.get_value() - self.broker.get_cash()
        current_yield = (self.Bc - self.Ba) / self.Ba if self.Ba > 0 else 0
        
        # === 3. 区域状态判断与转换 ===
        target_zone = self._determine_target_zone(current_yield)
        
        # 缓冲机制：区域转换需维持指定天数
        if target_zone != self.zone:
            if self.pending_zone == target_zone:
                self.pending_days += 1
            else:
                self.pending_zone = target_zone
                self.pending_days = 1
            
            # 确认切换
            if self.pending_days >= self.p.buffer_days:
                self._switch_zone(target_zone, price)
        else:
            # 没有转换，重置缓冲
            self.pending_zone = None
            self.pending_days = 0
        
        # === 4. 执行交易逻辑 ===
        if hasattr(self, 'order') and self.order:
            return  # 有未完成订单，跳过
        
        self._execute_zone_logic(price)
        
        # === 5. 记录每日明细 ===
        if self.detail_writer:
            self._write_daily_details(dt, price, current_yield)

    def _determine_target_zone(self, current_yield):
        """根据收益率和资金状态判断目标区域"""
        if self.zone == 'A':
            if current_yield < StrategyConfig.zone_b_entry:
                return 'B'
            elif current_yield >= 0.15:  # 文档: i >= 15% 直接进入D区
                return 'D'
            return 'A'
        
        elif self.zone == 'B':
            if current_yield >= StrategyConfig.zone_c_entry:
                return 'C'
            return 'B'
        
        elif self.zone == 'C':
            if current_yield < StrategyConfig.zone_b_entry:
                return 'B'
            elif current_yield >= StrategyConfig.zone_d_entry:
                return 'D'
            return 'C'
        
        elif self.zone == 'D':
            if current_yield < StrategyConfig.zone_d_exit:
                return 'C'
            elif self.S_acc > StrategyConfig.zone_e_entry_ratio * self.Ba:
                return 'E'
            return 'D'
        
        elif self.zone == 'E':
            if self.S_acc <= StrategyConfig.zone_e_entry_ratio * self.Ba:
                return 'D'
            elif self.S_acc >= StrategyConfig.zone_f_entry_ratio * self.Ba:
                return 'F'
            return 'E'
        
        elif self.zone == 'F':
            # 区域F一旦进入，理论上不再退出
            return 'F'
        
        return self.zone

    def _switch_zone(self, new_zone, price):
        """执行区域切换"""
        old_zone = self.zone
        
        # 记录快照股数
        if new_zone == 'C':
            self.D1 = self.position.size
            self.c_base_price = price  # 记录C区基准价(用于F区回调监测)
        elif new_zone == 'D':
            self.D2 = self.position.size
        elif new_zone == 'E':
            self.D3 = self.position.size
        elif new_zone == 'F':
            # 进入F区，记录最高价
            self.f_highest_price = price
        
        # 仓位恢复逻辑 (文档要求)
        # 例如：从D返回C时，应"加仓到D2"
        if old_zone == 'D' and new_zone == 'C':
            # 需要恢复到D2股数
            current_shares = self.position.size
            if current_shares < self.D2:
                diff = self.D2 - current_shares
                if diff > 0:
                    self.order = self.buy(size=diff)
        
        elif old_zone == 'E' and new_zone == 'D':
            # 需要恢复到D3股数
            current_shares = self.position.size
            if current_shares < self.D3:
                diff = self.D3 - current_shares
                if diff > 0:
                    self.order = self.buy(size=diff)
        
        # 更新基准价和计数器
        self.P_op = price
        self.rise_count = 0
        self.zone = new_zone
        self.pending_zone = None
        self.pending_days = 0

    def _execute_zone_logic(self, price):
        """根据当前区域执行交易逻辑"""
        delta = self.get_threshold(price)
        next_buy_price = self.P_op * (1 - delta)
        next_sell_price = self.P_op * (1 + delta)
        
        if self.zone == 'A':
            self._zone_a_logic(price, next_buy_price, next_sell_price)
        elif self.zone == 'B':
            self._zone_b_logic(price, next_buy_price)
        elif self.zone == 'C':
            self._zone_c_logic(price, next_buy_price, next_sell_price)
        elif self.zone == 'D':
            self._zone_d_logic(price, next_buy_price, next_sell_price)
        elif self.zone == 'E':
            self._zone_e_logic(price, next_buy_price, next_sell_price, delta)
        elif self.zone == 'F':
            self._zone_f_logic(price)

    def _zone_a_logic(self, price, next_buy, next_sell):
        """区域A: 初始建仓区"""
        # 加仓：金字塔公式
        if price <= next_buy:
            target = self.calculate_pyramid_target(price)
            if target > self.Bc:
                diff_value = target - self.Bc
                size = int(diff_value / price)
                if size > 0:
                    self.order = self.buy(size=size)
                    # 更新Bg为新的目标值
                    self.Bg = target
        
        # 减仓：每上涨4%，减仓2%
        elif price >= next_sell:
            size = int(self.position.size * StrategyConfig.zone_a_sell_ratio)
            if size > 0:
                self.order = self.sell(size=size)

    def _zone_b_logic(self, price, next_buy):
        """区域B: 严重亏损区 - 只加仓不减仓"""
        if price <= next_buy:
            # 检查是否还有资金
            if self.Ba >= self.p.Bf:
                return  # 资金已耗尽
            
            target = self.calculate_pyramid_target(price)
            if target > self.Bc:
                diff_value = min(target - self.Bc, self.p.Bf - self.Ba)
                size = int(diff_value / price)
                if size > 0:
                    self.order = self.buy(size=size)
                    self.Bg = target

    def _zone_c_logic(self, price, next_buy, next_sell):
        """区域C: 亏损可控区 - 阶梯减仓"""
        if price >= next_sell:
            # 阶梯减仓: 第1次0.5%, 第2次1%, 第3次+2%
            ratio = StrategyConfig.zone_c_sell_ratios[min(self.rise_count, 2)]
            size = int(self.D1 * ratio)
            if size > 0:
                self.order = self.sell(size=size)
        
        elif price <= next_buy:
            # 加仓: 0.5% * D1
            size = int(self.D1 * StrategyConfig.zone_c_buy_ratio)
            if size > 0:
                self.order = self.buy(size=size)

    def _zone_d_logic(self, price, next_buy, next_sell):
        """区域D: 盈利本金慢速置换区"""
        if price >= next_sell:
            # 阶梯减仓: 第1次1%, 第2次1.5%, 第3次+2%
            ratio = StrategyConfig.zone_d_sell_ratios[min(self.rise_count, 2)]
            size = int(self.D2 * ratio)
            if size > 0:
                self.order = self.sell(size=size)
        
        elif price <= next_buy:
            # 加仓: 1% * D2
            size = int(self.D2 * StrategyConfig.zone_d_buy_ratio)
            if size > 0:
                self.order = self.buy(size=size)

    def _zone_e_logic(self, price, next_buy, next_sell, delta):
        """区域E: 盈利本金快速置换区"""
        if price >= next_sell:
            # 阶梯减仓: 第1次2%, 第2次4%, 第3次+6%
            ratio = StrategyConfig.zone_e_sell_ratios[min(self.rise_count, 2)]
            size = int(self.D3 * ratio)
            if size > 0:
                self.order = self.sell(size=size)
        
        else:
            # 加仓阈值: 10% 或 2.5倍动态阈值
            buy_threshold = delta * StrategyConfig.zone_e_buy_threshold_multiplier
            if price <= self.P_op * (1 - buy_threshold):
                size = int(self.D3 * StrategyConfig.zone_e_buy_ratio)
                if size > 0:
                    self.order = self.buy(size=size)

    def _zone_f_logic(self, price):
        """区域F: 投资利润复利期"""
        # 更新最高价
        if price > self.f_highest_price:
            self.f_highest_price = price
        
        # 使用固定阈值(如3%)
        f_delta = StrategyConfig.zone_f_threshold
        f_next_buy = self.P_op * (1 - f_delta)
        f_next_sell = self.P_op * (1 + f_delta)
        
        if price >= f_next_sell:
            # 减仓1%
            size = int(self.position.size * StrategyConfig.zone_f_trade_ratio)
            if size > 0:
                self.order = self.sell(size=size)
        
        elif price <= f_next_buy:
            # 加仓1% (使用已回收资金)
            size = int(self.position.size * StrategyConfig.zone_f_trade_ratio)
            if size > 0 and self.S_acc > size * price:
                self.order = self.buy(size=size)
        
        # TODO: 区域F增强模块 - 重新建仓监测
        # 这需要支持多策略实例，暂时不实现

    def _write_daily_details(self, dt, price, current_yield):
        """写入每日明细记录"""
        total_assets = self.cash_balance + self.Bc
        global_yield = (total_assets - StrategyConfig.total_initial_cash) / StrategyConfig.total_initial_cash
        
        delta = self.get_threshold(price)
        next_buy = self.P_op * (1 - delta)
        next_sell = self.P_op * (1 + delta)
        
        self.detail_writer.writerow([
            dt, f"{price:.4f}", self.zone, f"{current_yield:.4f}",
            f"{self.Bc:.2f}", f"{self.Ba:.2f}", f"{self.S_acc:.2f}",
            f"{self.cash_balance:.2f}", f"{total_assets:.2f}", f"{global_yield:.4f}",
            f"{delta:.4f}", f"{next_buy:.4f}", f"{next_sell:.4f}", self.rise_count
        ])
