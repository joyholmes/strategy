import backtrader as bt
from config import PositionManagementParams
import csv
import os
from datetime import datetime


class CycleTracker:
    """单个周期的跟踪器"""
    
    def __init__(self, cycle_id, initial_cash, vix_threshold, gdp_rate=0.07):
        self.cycle_id = cycle_id
        self.initial_cash = initial_cash  # 初始投入
        self.vix_threshold = vix_threshold  # 波动率阈值
        self.gdp_rate = gdp_rate  # GDP年化增长率
        
        # 持仓跟踪
        self.position_size = 0  # 持仓数量
        self.last_rebalance_value = 0  # 上次调仓后的金额
        self.last_rebalance_date = None  # 上次调仓日期
        self.days_since_rebalance = 0  # 距离上次调仓的交易日数
        
        # 资金统计
        self.total_invested = 0  # 累计投入
        self.max_single_add = 0  # 单次最大追加
        self.rebalance_count = 0  # 调仓次数
        self.buy_count = 0  # 补仓次数
        self.sell_count = 0  # 减仓次数
        
        # 收益跟踪
        self.max_value = 0  # 历史最高市值
        self.max_drawdown = 0  # 最大回撤
        
        # 同日调仓标记
        self.rebalanced_today = False
        self.last_check_date = None
        
        # 现金流记录（用于计算IRR）
        # 格式：[(日期, 现金流), ...] 负数表示流出（买入），正数表示流入（卖出）
        self.cash_flows = []
        
    def get_current_value(self, price):
        """获取当前市值"""
        return self.position_size * price
    
    def get_change_ratio(self, current_price):
        """计算相对于上次调仓的涨跌幅"""
        if self.last_rebalance_value == 0:
            return 0
        current_value = self.get_current_value(current_price)
        return (current_value - self.last_rebalance_value) / self.last_rebalance_value
    
    def should_rebalance(self, current_price):
        """判断是否需要调仓"""
        change_ratio = self.get_change_ratio(current_price)
        
        # 下跌超过阈值，需要补仓
        if change_ratio <= -self.vix_threshold:
            return 'BUY'
        # 上涨超过阈值，需要减仓
        elif change_ratio >= self.vix_threshold:
            return 'SELL'
        return None
    
    def calculate_target_value(self, action):
        """计算目标金额"""
        # 如果同日第二次调仓，day=0
        days = 0 if self.rebalanced_today else self.days_since_rebalance
        
        # 基础目标 = 初始仓位 × (1 + GDP/250 × day)
        base_target = self.initial_cash * (1 + self.gdp_rate / 250 * days)
        
        if action == 'BUY':
            # 补仓：目标金额 = base_target
            return base_target
        else:  # SELL
            # 减仓：目标金额 = 初始仓位 × (1 + GDP/250 × day + VIX/4)
            # 这里应该是乘以 (1 + VIX/4)，而不是加上
            return self.initial_cash * (1 + self.gdp_rate / 250 * days + self.vix_threshold / 4)
    
    def update_drawdown(self, current_value):
        """更新最大回撤"""
        if current_value > self.max_value:
            self.max_value = current_value
        
        if self.max_value > 0:
            drawdown = (self.max_value - current_value) / self.max_value
            if drawdown > self.max_drawdown:
                self.max_drawdown = drawdown


class PositionManagementStrategy(bt.Strategy):
    """仓位管理策略"""
    
    params = (
        ('cycles', PositionManagementParams.cycles),  # 周期配置列表
        ('gdp_rate', PositionManagementParams.gdp_rate),  # GDP增长率
        ('output_folder', None),  # 输出文件夹
    )
    
    def __init__(self):
        self.dataclose = self.datas[0].close
        self.order = None
        
        # 初始化周期跟踪器
        self.cycle_trackers = []
        for cycle_config in self.p.cycles:
            tracker = CycleTracker(
                cycle_id=cycle_config['id'],
                initial_cash=cycle_config['initial_cash'],
                vix_threshold=cycle_config['vix_threshold'],
                gdp_rate=self.p.gdp_rate
            )
            self.cycle_trackers.append(tracker)
        
        # 准备操作日志文件
        if self.p.output_folder:
            log_path = os.path.join(self.p.output_folder, 'operation_log.csv')
            self.op_log_file = open(log_path, 'w', newline='', encoding='utf-8')
            self.op_writer = csv.writer(self.op_log_file)
            self.op_writer.writerow([
                '日期', '周期ID', '操作类型', '成交价格', '操作数量', 
                '操作金额', '操作后持仓', '操作后市值', '距上次调仓天数',
                '触发涨跌幅', '目标金额', '手续费'
            ])
            
            # 周期详细日志
            detail_path = os.path.join(self.p.output_folder, 'cycle_details.csv')
            self.detail_log_file = open(detail_path, 'w', newline='', encoding='utf-8')
            self.detail_writer = csv.writer(self.detail_log_file)
            self.detail_writer.writerow([
                '日期', '周期ID', '当前价格', '持仓数量', '当前市值',
                '距上次调仓天数', '相对涨跌幅', '累计投入', '最大回撤'
            ])
        else:
            self.op_log_file = None
            self.detail_log_file = None
        
        # 全局统计
        self.total_trades = 0
        self.current_date = None
    
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
            # 订单完成，记录在日志中（已在execute_rebalance中处理）
            pass
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'订单被取消/保证金不足/被拒绝')
        
        self.order = None
    
    def next(self):
        """每个交易日执行"""
        current_date = self.datas[0].datetime.date(0)
        current_price = self.dataclose[0]
        
        # 检查是否是新的交易日
        if self.current_date != current_date:
            self.current_date = current_date
            # 重置同日调仓标记
            for tracker in self.cycle_trackers:
                tracker.rebalanced_today = False
        
        # 检查每个周期
        for tracker in self.cycle_trackers:
            # 更新距离上次调仓的天数
            if tracker.last_check_date != current_date:
                if tracker.last_rebalance_date is not None:
                    tracker.days_since_rebalance += 1
                tracker.last_check_date = current_date
            
            # 初始建仓
            if tracker.position_size == 0 and tracker.rebalance_count == 0:
                self.initial_buy(tracker, current_price, current_date)
                continue
            
            # 检查是否需要调仓
            action = tracker.should_rebalance(current_price)
            if action:
                self.execute_rebalance(tracker, action, current_price, current_date)
            
            # 更新回撤
            current_value = tracker.get_current_value(current_price)
            tracker.update_drawdown(current_value)
            
            # 记录每日详情
            if self.detail_writer:
                change_ratio = tracker.get_change_ratio(current_price)
                self.detail_writer.writerow([
                    current_date.isoformat(),
                    tracker.cycle_id,
                    f'{current_price:.2f}',
                    tracker.position_size,
                    f'{current_value:.2f}',
                    tracker.days_since_rebalance,
                    f'{change_ratio*100:.2f}%',
                    f'{tracker.total_invested:.2f}',
                    f'{tracker.max_drawdown*100:.2f}%'
                ])
    
    def initial_buy(self, tracker, price, date):
        """初始建仓"""
        # 对于高价标的，允许小数股交易（保留2位小数）
        shares = round(tracker.initial_cash / price, 2)
        
        if shares <= 0:
            self.log(f'周期{tracker.cycle_id}: 初始资金不足，无法建仓')
            return
        
        actual_cost = shares * price
        commission = actual_cost * 0.00005  # 假设手续费
        
        # 更新跟踪器
        tracker.position_size = shares
        tracker.last_rebalance_value = actual_cost
        tracker.last_rebalance_date = date
        tracker.days_since_rebalance = 0
        tracker.total_invested = actual_cost
        tracker.rebalance_count += 1
        tracker.buy_count += 1
        tracker.max_value = actual_cost
        
        # 记录现金流（买入为负）
        tracker.cash_flows.append((date, -actual_cost))
        
        self.total_trades += 1
        
        # 记录日志
        self.log(f'周期{tracker.cycle_id}: 初始建仓 {shares}股 @ {price:.2f}, 金额: {actual_cost:.2f}')
        
        if self.op_writer:
            self.op_writer.writerow([
                date.isoformat(),
                tracker.cycle_id,
                '初始建仓',
                f'{price:.2f}',
                shares,
                f'{actual_cost:.2f}',
                shares,
                f'{actual_cost:.2f}',
                0,
                '0.00%',
                f'{tracker.initial_cash:.2f}',
                f'{commission:.2f}'
            ])
    
    def execute_rebalance(self, tracker, action, price, date):
        """执行调仓"""
        current_value = tracker.get_current_value(price)
        target_value = tracker.calculate_target_value(action)
        change_ratio = tracker.get_change_ratio(price)
        days = 0 if tracker.rebalanced_today else tracker.days_since_rebalance
        
        if action == 'BUY':
            # 补仓
            add_value = target_value - current_value
            # 对于高价标的，允许小数股交易（保留2位小数）
            shares_to_buy = round(add_value / price, 2)
            
            if shares_to_buy <= 0:
                return
            
            actual_cost = shares_to_buy * price
            commission = actual_cost * 0.00005
            
            # 更新统计
            tracker.position_size += shares_to_buy
            tracker.total_invested += actual_cost
            if actual_cost > tracker.max_single_add:
                tracker.max_single_add = actual_cost
            tracker.buy_count += 1
            
            # 记录现金流（买入为负）
            tracker.cash_flows.append((date, -actual_cost))
            
            op_type = '补仓'
            
        else:  # SELL
            # 减仓
            reduce_value = current_value - target_value
            # 对于高价标的，允许小数股交易（保留2位小数）
            shares_to_sell = round(reduce_value / price, 2)
            
            if shares_to_sell <= 0 or shares_to_sell > tracker.position_size:
                return
            
            actual_value = shares_to_sell * price
            commission = actual_value * 0.00005
            
            # 更新统计
            tracker.position_size -= shares_to_sell
            # 减仓不增加投入，但要记录
            tracker.sell_count += 1
            
            # 记录现金流（卖出为正）
            tracker.cash_flows.append((date, actual_value))
            
            op_type = '减仓'
            actual_cost = -actual_value  # 负数表示卖出
        
        # 更新调仓记录
        tracker.last_rebalance_value = tracker.get_current_value(price)
        tracker.last_rebalance_date = date
        tracker.rebalance_count += 1
        self.total_trades += 1
        
        # 标记今日已调仓
        if not tracker.rebalanced_today:
            tracker.rebalanced_today = True
            tracker.days_since_rebalance = 0
        
        # 记录日志
        self.log(
            f'周期{tracker.cycle_id}: {op_type} {abs(shares_to_buy if action=="BUY" else shares_to_sell)}股 '
            f'@ {price:.2f}, 金额: {abs(actual_cost):.2f}, '
            f'触发涨跌幅: {change_ratio*100:.2f}%, 距上次{days}天'
        )
        
        if self.op_writer:
            self.op_writer.writerow([
                date.isoformat(),
                tracker.cycle_id,
                op_type,
                f'{price:.2f}',
                shares_to_buy if action == 'BUY' else -shares_to_sell,
                f'{actual_cost:.2f}',
                tracker.position_size,
                f'{tracker.get_current_value(price):.2f}',
                days,
                f'{change_ratio*100:.2f}%',
                f'{target_value:.2f}',
                f'{commission:.2f}'
            ])
    
    def print_final_stats(self):
        """打印最终统计"""
        print("\n" + "="*80)
        print("仓位管理策略 - 最终统计报告")
        print("="*80)
        
        # 获取最终价格
        final_price = self.dataclose[0]
        
        # 各周期统计
        total_initial = 0
        total_invested = 0
        total_final_value = 0
        total_max_add = 0
        
        for tracker in self.cycle_trackers:
            final_value = tracker.get_current_value(final_price)
            return_rate = (final_value - tracker.initial_cash) / tracker.initial_cash * 100
            
            print(f"\n【周期 {tracker.cycle_id}】")
            print(f"  VIX阈值: {tracker.vix_threshold*100:.1f}%")
            print(f"  初始投入: {tracker.initial_cash:,.2f}")
            print(f"  累计投入: {tracker.total_invested:,.2f}")
            print(f"  最大追加: {tracker.max_single_add:,.2f}")
            print(f"  期末市值: {final_value:,.2f}")
            print(f"  绝对收益: {final_value - tracker.total_invested:,.2f}")
            print(f"  收益率: {return_rate:.2f}%")
            print(f"  调仓次数: {tracker.rebalance_count} (补仓:{tracker.buy_count}, 减仓:{tracker.sell_count})")
            print(f"  最大回撤: {tracker.max_drawdown*100:.2f}%")
            
            total_initial += tracker.initial_cash
            total_invested += tracker.total_invested
            total_final_value += final_value
            total_max_add += tracker.max_single_add
        
        # 整体统计
        total_return_rate = (total_final_value - total_initial) / total_initial * 100
        
        print(f"\n【整体策略】")
        print(f"  总初始投入: {total_initial:,.2f}")
        print(f"  总累计投入: {total_invested:,.2f}")
        print(f"  总最大追加: {total_max_add:,.2f}")
        print(f"  总期末市值: {total_final_value:,.2f}")
        print(f"  总绝对收益: {total_final_value - total_invested:,.2f}")
        print(f"  总收益率: {total_return_rate:.2f}%")
        print(f"  总调仓次数: {sum(t.rebalance_count for t in self.cycle_trackers)}")
        
        print("\n" + "="*80)
    
    def log(self, txt, dt=None):
        """日志输出"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')
