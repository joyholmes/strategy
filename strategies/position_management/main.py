import sys
import os
# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import backtrader as bt
from common.data_fetcher import fetch_data
from common.metrics import calculate_irr
from strategies.position_management.strategy import PositionManagementStrategy
from strategies.position_management import config
from config import global_config
import datetime
import csv


def generate_report(cerebro, strat, output_folder, benchmark_return=None, buy_and_hold_return=None):
    """
    生成仓位管理策略的报告
    """
    # 获取最终价格和日期
    final_price = strat.dataclose[0]
    final_date = strat.datas[0].datetime.date(0)
    
    # 收集各周期数据
    cycle_data = []
    total_initial = 0
    total_invested = 0
    total_net_invested = 0
    total_final_value = 0
    total_max_add = 0
    total_rebalance_count = 0
    all_cash_flows = []  # 汇总所有现金流
    
    for tracker in strat.cycle_trackers:
        final_value = tracker.get_current_value(final_price)
        
        # 计算各种收益率
        # 计算各种收益率
        absolute_profit = final_value - tracker.net_invested  # 绝对收益 = 期末市值 - 净投入
        nominal_return = (final_value - tracker.initial_cash) / tracker.initial_cash * 100  # 相对初始投入
        
        # 实际投资收益率 (基于净投入)
        if tracker.net_invested > 0:
            actual_return = absolute_profit / tracker.net_invested * 100
        else:
            actual_return = 0  # 净投入为负或0，收益率无意义（或无穷大）
        
        # 计算平均持仓成本收益率
        avg_cost = tracker.total_invested / tracker.position_size if tracker.position_size > 0 else 0
        avg_cost_return = (final_price - avg_cost) / avg_cost * 100 if avg_cost > 0 else 0
        
        # 计算IRR
        cycle_irr = calculate_irr(tracker.cash_flows, final_value, final_date)
        
        # 资金使用效率
        capital_efficiency = final_value / tracker.total_invested if tracker.total_invested > 0 else 0
        
        cycle_info = {
            'cycle_id': tracker.cycle_id,
            'vix_threshold': tracker.vix_threshold * 100,
            'initial_cash': tracker.initial_cash,
            'total_invested': tracker.total_invested,
            'net_invested': tracker.net_invested,
            'max_single_add': tracker.max_single_add,
            'final_value': final_value,
            'absolute_profit': absolute_profit,
            'nominal_return': nominal_return,  # 改名：相对初始投入收益率
            'actual_return': actual_return,    # 改名：净投入收益率
            'avg_cost': avg_cost,              # 新增：平均持仓成本
            'avg_cost_return': avg_cost_return,  # 新增：平均成本收益率
            'irr': cycle_irr,                  # 新增：IRR年化收益率
            'capital_efficiency': capital_efficiency,  # 新增：资金使用效率
            'rebalance_count': tracker.rebalance_count,
            'buy_count': tracker.buy_count,
            'sell_count': tracker.sell_count,
            'max_drawdown': tracker.max_drawdown * 100
        }
        cycle_data.append(cycle_info)
        
        total_initial += tracker.initial_cash
        total_invested += tracker.total_invested
        total_net_invested += tracker.net_invested
        total_final_value += final_value
        total_max_add += tracker.max_single_add
        total_rebalance_count += tracker.rebalance_count
        all_cash_flows.extend(tracker.cash_flows)
    
    # 计算整体指标
    total_nominal_return = (total_final_value - total_initial) / total_initial * 100  # 相对初始投入
    total_absolute_profit = total_final_value - total_net_invested
    
    if total_net_invested > 0:
        total_actual_return = total_absolute_profit / total_net_invested * 100
    else:
        total_actual_return = 0
        
    total_irr = calculate_irr(all_cash_flows, total_final_value, final_date)  # 整体IRR
    total_capital_efficiency = total_final_value / total_invested if total_invested > 0 else 0
    
    # 生成文本报告
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append(f"仓位管理策略回测报告")
    report_lines.append(f"回测标的: {config.STOCK_CODE}")
    report_lines.append(f"数据源: {config.DATA_SOURCE}")
    report_lines.append(f"回测区间: {config.START_DATE} 至 {config.END_DATE}")
    report_lines.append(f"报告生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    # 策略参数
    report_lines.append("--- 策略参数 ---")
    report_lines.append(f"总初始资金: {total_initial:,.2f}")
    report_lines.append(f"GDP年化增长率: {config.PositionManagementParams.gdp_rate * 100:.1f}%")
    report_lines.append(f"周期数量: {len(strat.cycle_trackers)}")
    report_lines.append("")
    
    # 各周期详细数据
    report_lines.append("--- 各周期详细数据 ---")
    for cycle in cycle_data:
        report_lines.append(f"\n【{cycle['cycle_id']}】")
        report_lines.append(f"  VIX阈值:              {cycle['vix_threshold']:.1f}%")
        report_lines.append(f"  初始投入:             {cycle['initial_cash']:>15,.2f}")
        report_lines.append(f"  累计投入(Gross):      {cycle['total_invested']:>15,.2f}")
        report_lines.append(f"  累计净投入(Net):      {cycle['net_invested']:>15,.2f}")
        report_lines.append(f"  最大追加:             {cycle['max_single_add']:>15,.2f}")
        report_lines.append(f"  期末市值:             {cycle['final_value']:>15,.2f}")
        report_lines.append(f"  绝对收益:             {cycle['absolute_profit']:>15,.2f}")
        report_lines.append(f"  --- 收益率指标 ---")
        report_lines.append(f"  相对初始投入收益率:   {cycle['nominal_return']:>14.2f}%")
        report_lines.append(f"  净投入收益率:         {cycle['actual_return']:>14.2f}%  ⭐")
        report_lines.append(f"  IRR年化收益率:        {cycle['irr']:>14.2f}%  ⭐⭐")
        report_lines.append(f"  平均成本收益率:       {cycle['avg_cost_return']:>14.2f}%")
        report_lines.append(f"  --- 其他指标 ---")
        report_lines.append(f"  平均持仓成本:         {cycle['avg_cost']:>15.2f}")
        report_lines.append(f"  资金使用效率:         {cycle['capital_efficiency']:>15.3f}")
        report_lines.append(f"  调仓次数:             {cycle['rebalance_count']:>15} (补仓:{cycle['buy_count']}, 减仓:{cycle['sell_count']})")
        report_lines.append(f"  最大回撤:             {cycle['max_drawdown']:>14.2f}%")
    
    report_lines.append("")
    report_lines.append("=" * 80)
    
    # 整体策略表现
    report_lines.append("--- 整体策略表现 ---")
    report_lines.append(f"总初始投入:           {total_initial:>15,.2f}")
    report_lines.append(f"总累计投入(Gross):    {total_invested:>15,.2f}")
    report_lines.append(f"总累计净投入(Net):    {total_net_invested:>15,.2f}")
    report_lines.append(f"总最大追加:           {total_max_add:>15,.2f}")
    report_lines.append(f"总期末市值:           {total_final_value:>15,.2f}")
    report_lines.append(f"总绝对收益:           {total_absolute_profit:>15,.2f}")
    report_lines.append(f"--- 收益率指标 ---")
    report_lines.append(f"相对初始投入收益率:   {total_nominal_return:>14.2f}%")
    report_lines.append(f"净投入收益率:         {total_actual_return:>14.2f}%  ⭐ (真实收益)")
    report_lines.append(f"IRR年化收益率:        {total_irr:>14.2f}%  ⭐⭐ (最准确)")
    report_lines.append(f"资金使用效率:         {total_capital_efficiency:>15.3f}")
    report_lines.append(f"总调仓次数:           {total_rebalance_count:>15}")
    report_lines.append("")
    
    # 对比指标
    if buy_and_hold_return is not None:
        buy_and_hold_pct = buy_and_hold_return * 100
        report_lines.append("--- 对比指标 ---")
        report_lines.append(f"买入持有收益率:       {buy_and_hold_pct:>14.2f}%")
        report_lines.append(f"相对表现(vs初始):     {total_nominal_return - buy_and_hold_pct:>14.2f}%")
        report_lines.append(f"相对表现(vs实际):     {total_actual_return - buy_and_hold_pct:>14.2f}%")
        report_lines.append(f"相对表现(IRR):        {total_irr - buy_and_hold_pct:>14.2f}%")
        report_lines.append("")
    
    if benchmark_return is not None:
        benchmark_pct = benchmark_return * 100
        report_lines.append(f"基准收益率:           {benchmark_pct:>14.2f}%")
        report_lines.append(f"超额收益(vs初始):     {total_nominal_return - benchmark_pct:>14.2f}%")
        report_lines.append(f"超额收益(vs实际):     {total_actual_return - benchmark_pct:>14.2f}%")
        report_lines.append(f"超额收益(IRR):        {total_irr - benchmark_pct:>14.2f}%")
        report_lines.append("")
    
    report_lines.append("=" * 80)
    
    # 写入文件
    report_content = "\n".join(report_lines)
    report_path = os.path.join(output_folder, 'backtest_results.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    print(report_content)
    
    # 返回汇总数据
    summary = {
        'StockCode': config.STOCK_CODE,
        'Strategy': 'PositionManagement',
        'StartDate': config.START_DATE,
        'EndDate': config.END_DATE,
        'TotalInitial': f"{total_initial:.2f}",
        'TotalInvested': f"{total_invested:.2f}",
        'TotalNetInvested': f"{total_net_invested:.2f}",
        'TotalFinalValue': f"{total_final_value:.2f}",
        'NominalReturnPct': f"{total_nominal_return:.2f}",  # 相对初始投入收益率
        'ActualReturnPct': f"{total_actual_return:.2f}",    # 净投入收益率
        'IRR_Pct': f"{total_irr:.2f}",                      # IRR年化收益率
        'CapitalEfficiency': f"{total_capital_efficiency:.3f}",  # 资金使用效率
        'BuyAndHoldReturnPct': f"{buy_and_hold_return*100:.2f}" if buy_and_hold_return else 'N/A',
        'BenchmarkReturnPct': f"{benchmark_return*100:.2f}" if benchmark_return else 'N/A',
        'TotalRebalanceCount': total_rebalance_count,
    }
    
    return summary


def update_summary(summary_data, run_timestamp, folder_name):
    """
    更新汇总CSV文件
    """
    summary_file = os.path.join('results', 'summary.csv')
    
    summary_data['RunTimestamp'] = run_timestamp
    summary_data['ResultFolder'] = folder_name
    
    header = [
        'StockCode', 'Strategy', 'StartDate', 'EndDate',
        'TotalInitial', 'TotalInvested', 'TotalNetInvested', 'TotalFinalValue', 
        'NominalReturnPct', 'ActualReturnPct', 'IRR_Pct', 'CapitalEfficiency',
        'BuyAndHoldReturnPct', 'BenchmarkReturnPct', 'TotalRebalanceCount',
        'RunTimestamp', 'ResultFolder'
    ]
    
    file_exists = os.path.isfile(summary_file)
    
    with open(summary_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if not file_exists:
            writer.writeheader()
        writer.writerow(summary_data)
    
    print(f"\n汇总数据已追加到 {summary_file}")


if __name__ == '__main__':
    cerebro = bt.Cerebro(stdstats=False)
    
    # 创建唯一输出目录
    strategy_name = 'PositionManagement'
    run_timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    folder_name = f"{config.STOCK_CODE}-{strategy_name}-{config.START_DATE}-{config.END_DATE}-{run_timestamp}"
    output_folder = os.path.join('results', folder_name)
    os.makedirs(output_folder, exist_ok=True)
    
    # 添加策略
    cerebro.addstrategy(PositionManagementStrategy, output_folder=output_folder)
    
    # 添加观察者
    cerebro.addobserver(bt.observers.Broker)
    cerebro.addobserver(bt.observers.Value)
    
    # 获取数据
    print(f"正在获取数据: {config.STOCK_CODE} ({config.START_DATE} - {config.END_DATE})...")
    data = fetch_data(config.STOCK_CODE, config.START_DATE, config.END_DATE)
    feed = bt.feeds.PandasData(dataname=data, name=config.STOCK_CODE)
    cerebro.adddata(feed)
    
    # 计算买入持有收益
    buy_and_hold_return = None
    if not data.empty:
        buy_and_hold_return = (data['close'].iloc[-1] - data['close'].iloc[0]) / data['close'].iloc[0]
    
    # 获取基准数据（可选）
    benchmark_return = None
    if config.ENABLE_BENCHMARK and config.STOCK_CODE != '000300.SH':
        print("正在获取基准数据 (沪深300)...")
        benchmark_data = fetch_data('000300.SH', config.START_DATE, config.END_DATE)
        if not benchmark_data.empty:
            benchmark_return = (benchmark_data['close'].iloc[-1] - benchmark_data['close'].iloc[0]) / benchmark_data['close'].iloc[0]
    
    # 设置初始资金（这里不实际使用，因为策略自己管理资金）
    cerebro.broker.setcash(config.PositionManagementParams.total_initial_cash)
    
    # 设置手续费
    cerebro.broker.setcommission(commission=config.COMMISSION)
    
    # 运行回测
    print(f'\n开始回测...')
    print(f'策略: 仓位管理策略')
    print(f'周期数: {len(config.PositionManagementParams.cycles)}')
    print("=" * 80)
    
    results = cerebro.run()
    strat = results[0]
    
    # 生成报告
    summary_data = generate_report(cerebro, strat, output_folder, benchmark_return, buy_and_hold_return)
    
    # 更新汇总文件
    update_summary(summary_data, run_timestamp, folder_name)
    
    print(f"\n所有结果已保存至: {output_folder}")
    print(f"  - backtest_results.txt  (总结报告)")
    print(f"  - operation_log.csv     (操作日志)")
    print(f"  - cycle_details.csv     (周期详情)")
