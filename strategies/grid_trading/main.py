import sys
import os
# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import backtrader as bt
from common.data_fetcher import fetch_data
from common.metrics import calculate_irr
from strategies.grid_trading.strategy import GridTradingStrategy
from strategies.grid_trading import config
from config import global_config
import datetime
import csv


def generate_report(cerebro, strat, output_folder, benchmark_return=None, buy_and_hold_return=None):
    """
    生成网格交易策略的报告
    """
    # 获取最终价格和日期
    final_price = strat.dataclose[0]
    final_date = strat.datas[0].datetime.date(0)
    
    # 计算核心指标
    final_value = strat.get_current_value(final_price)
    absolute_profit = final_value - strat.net_invested
    
    # 净投入收益率
    if strat.net_invested > 0:
        actual_return = absolute_profit / strat.net_invested * 100
    else:
        actual_return = 0
    
    # 计算IRR
    irr = calculate_irr(strat.cash_flows, final_value, final_date)
    
    # 生成文本报告
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append(f"网格交易策略回测报告")
    report_lines.append(f"回测标的: {config.STOCK_CODE}")
    report_lines.append(f"数据源: {global_config.DATA_SOURCE}")
    report_lines.append(f"回测区间: {config.START_DATE} 至 {config.END_DATE}")
    report_lines.append(f"报告生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    # 策略参数
    report_lines.append("--- 策略参数 ---")
    report_lines.append(f"初始资金: {strat.initial_cash:,.2f}")
    report_lines.append(f"初始仓位比例: {config.GridTradingParams.initial_position_ratio * 100:.1f}%")
    report_lines.append(f"网格买入阈值: {config.GridTradingParams.grid_buy_percent * 100:.1f}%")
    report_lines.append(f"网格卖出阈值: {config.GridTradingParams.grid_sell_percent * 100:.1f}%")
    report_lines.append(f"每次交易比例: {config.GridTradingParams.trade_percent * 100:.1f}%")
    report_lines.append(f"最大仓位比例: {config.GridTradingParams.max_position_ratio * 100:.1f}%")
    report_lines.append(f"最小仓位比例: {config.GridTradingParams.min_position_ratio * 100:.1f}%")
    report_lines.append("")
    
    # 策略表现
    report_lines.append("=" * 80)
    report_lines.append("--- 策略表现 ---")
    report_lines.append(f"初始资金:             {strat.initial_cash:>15,.2f}")
    report_lines.append(f"累计投入(Gross):      {strat.total_invested:>15,.2f}")
    report_lines.append(f"累计净投入(Net):      {strat.net_invested:>15,.2f}")
    report_lines.append(f"期末市值:             {final_value:>15,.2f}")
    report_lines.append(f"绝对收益:             {absolute_profit:>15,.2f}")
    report_lines.append(f"--- 核心收益率指标 ---")
    report_lines.append(f"净投入收益率:         {actual_return:>14.2f}%  ⭐")
    report_lines.append(f"IRR年化收益率:        {irr:>14.2f}%  ⭐⭐ (最准确)")
    report_lines.append(f"--- 交易统计 ---")
    report_lines.append(f"总交易次数:           {strat.total_trades:>15}")
    report_lines.append(f"买入次数:             {strat.buy_count:>15}")
    report_lines.append(f"卖出次数:             {strat.sell_count:>15}")
    report_lines.append(f"最大回撤:             {strat.max_drawdown*100:>14.2f}%")
    report_lines.append("")
    
    # 对比指标
    if buy_and_hold_return is not None:
        buy_and_hold_pct = buy_and_hold_return * 100
        report_lines.append("--- 对比指标 ---")
        report_lines.append(f"买入持有收益率:       {buy_and_hold_pct:>14.2f}%")
        report_lines.append(f"净投入相对表现:       {actual_return - buy_and_hold_pct:>14.2f}%")
        report_lines.append(f"IRR相对表现:          {irr - buy_and_hold_pct:>14.2f}%")
        report_lines.append("")
    
    if benchmark_return is not None:
        benchmark_pct = benchmark_return * 100
        report_lines.append(f"基准收益率:           {benchmark_pct:>14.2f}%")
        report_lines.append(f"净投入超额收益:       {actual_return - benchmark_pct:>14.2f}%")
        report_lines.append(f"IRR超额收益:          {irr - benchmark_pct:>14.2f}%")
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
        'Strategy': 'GridTrading',
        'StartDate': config.START_DATE,
        'EndDate': config.END_DATE,
        'TotalInitial': f"{strat.initial_cash:.2f}",
        'TotalInvested': f"{strat.total_invested:.2f}",
        'TotalNetInvested': f"{strat.net_invested:.2f}",
        'TotalFinalValue': f"{final_value:.2f}",
        'ActualReturnPct': f"{actual_return:.2f}",
        'IRR_Pct': f"{irr:.2f}",
        'BuyAndHoldReturnPct': f"{buy_and_hold_return*100:.2f}" if buy_and_hold_return else 'N/A',
        'BenchmarkReturnPct': f"{benchmark_return*100:.2f}" if benchmark_return else 'N/A',
        'TotalTrades': strat.total_trades,
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
        'ActualReturnPct', 'IRR_Pct',
        'BuyAndHoldReturnPct', 'BenchmarkReturnPct', 'TotalTrades',
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
    strategy_name = 'GridTrading'
    run_timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    folder_name = f"{config.STOCK_CODE}-{strategy_name}-{config.START_DATE}-{config.END_DATE}-{run_timestamp}"
    output_folder = os.path.join('results', folder_name)
    os.makedirs(output_folder, exist_ok=True)
    
    # 添加策略
    cerebro.addstrategy(GridTradingStrategy, output_folder=output_folder)
    
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
    
    # 设置初始资金
    cerebro.broker.setcash(config.GridTradingParams.total_initial_cash)
    
    # 设置手续费
    cerebro.broker.setcommission(commission=global_config.COMMISSION)
    
    # 运行回测
    print(f'\n开始回测...')
    print(f'策略: 网格交易策略')
    print(f'初始仓位: {config.GridTradingParams.initial_position_ratio * 100:.1f}%')
    print(f'网格间距: 买入-{config.GridTradingParams.grid_buy_percent * 100:.1f}% / 卖出+{config.GridTradingParams.grid_sell_percent * 100:.1f}%')
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
    print(f"  - details.csv           (每日详情)")
