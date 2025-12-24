"""
Freq Grid Strategy V2 - 回测主程序

功能：
1. 数据获取与处理
2. 策略回测执行
3. 性能指标计算
4. 可视化图表生成
5. 报告输出
"""

import sys
import os
import backtrader as bt
import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from strategies.freq_grid_v2.config import StrategyConfig, ReportConfig
from strategies.freq_grid_v2.strategy import FreqGridV2Strategy
from common.data_fetcher import fetch_data

# 设置中文字体
try:
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
except:
    pass


class PandasData(bt.feeds.PandasData):
    """自定义数据格式"""
    params = (
        ('datetime', None),
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'volume'),
        ('openinterest', None),
    )


def calculate_global_metrics(details_df, operations_df, initial_cash):
    """
    计算全局核算指标
    
    Args:
        details_df: 每日明细DataFrame
        operations_df: 操作记录DataFrame  
        initial_cash: 初始资金
    
    Returns:
        dict: 全局指标字典
    """
    metrics = {}
    
    if details_df.empty:
        return metrics
    
    # 从最后一行获取终值
    last_row = details_df.iloc[-1]
    
    # 期末总资产
    terminal_assets = float(last_row['TotalAssets'])
    
    # 从操作记录计算总投入和总回收
    if not operations_df.empty:
        buys = operations_df[operations_df['Type'] == 'BUY']
        sells = operations_df[operations_df['Type'] == 'SELL']
        
        total_invested = buys['Amount'].astype(float).sum() if not buys.empty else 0
        total_withdrawn = sells['Amount'].astype(float).sum() if not sells.empty else 0
    else:
        total_invested = float(last_row['Ba'])
        total_withdrawn = float(last_row['S_acc'])
    
    # 全局净利润
    global_profit = terminal_assets - initial_cash
    
    # 全局累计收益率
    global_return = global_profit / initial_cash if initial_cash > 0 else 0
    
    # 计算回测天数和年化收益率
    if len(details_df) > 1:
        start_date = pd.to_datetime(details_df.iloc[0]['Date'])
        end_date = pd.to_datetime(details_df.iloc[-1]['Date'])
        days = (end_date - start_date).days
        years = days / 365.0
        
        if years > 0:
            global_annual_return = (1 + global_return) ** (1 / years) - 1
        else:
            global_annual_return = 0
    else:
        years = 0
        global_annual_return = 0
    
    # 计算全局最大回撤
    details_df['TotalAssets_float'] = details_df['TotalAssets'].astype(float)
    running_max = details_df['TotalAssets_float'].expanding().max()
    drawdown = (details_df['TotalAssets_float'] - running_max) / running_max
    global_max_drawdown = drawdown.min()
    
    # 现金使用效率
    details_df['CashUsage'] = details_df['Ba'].astype(float) - details_df['S_acc'].astype(float)
    max_cash_usage = details_df['CashUsage'].max()
    cash_efficiency = total_invested / max_cash_usage if max_cash_usage > 0 else 0
    
    # 本金回收时点
    capital_recovered_date = None
    if not details_df.empty:
        recovered = details_df[details_df['S_acc'].astype(float) >= details_df['Ba'].astype(float)]
        if not recovered.empty:
            capital_recovered_date = recovered.iloc[0]['Date']
    
    metrics.update({
        'total_invested': total_invested,
        'total_withdrawn': total_withdrawn,
        'terminal_assets': terminal_assets,
        'global_profit': global_profit,
        'global_return': global_return,
        'global_annual_return': global_annual_return,
        'global_max_drawdown': global_max_drawdown,
        'backtest_years': years,
        'max_cash_usage': max_cash_usage,
        'cash_efficiency': cash_efficiency,
        'capital_recovered_date': capital_recovered_date,
    })
    
    return metrics


def generate_visualization(output_folder, stock_code):
    """生成可视化图表"""
    details_path = os.path.join(output_folder, 'daily_details.csv')
    op_log_path = os.path.join(output_folder, 'operations.csv')
    
    if not os.path.exists(details_path):
        print("No details file found")
        return
    
    df = pd.read_csv(details_path)
    if df.empty:
        print("Details dataframe is empty")
        return
    
    df['Date'] = pd.to_datetime(df['Date'])
    
    # 读取操作记录
    op_log = pd.DataFrame()
    if os.path.exists(op_log_path):
        op_log = pd.read_csv(op_log_path)
        if not op_log.empty:
            op_log['Date'] = pd.to_datetime(op_log['Date'])
    
    # 创建图表
    fig = plt.figure(figsize=(20, 14))
    gs = GridSpec(5, 2, figure=fig, hspace=0.3, wspace=0.3)
    
    fig.suptitle(f'Freq Grid V2 策略回测报告 - {stock_code}', 
                 fontsize=18, fontweight='bold', y=0.995)
    
    # === 图1: 价格 + 买卖点 + 区域标注 ===
    ax1 = fig.add_subplot(gs[0, :])
    ax1.plot(df['Date'], df['Close'], label='价格', color='#2E86AB', linewidth=1.5)
    
    # 标注买卖点
    if not op_log.empty:
        buys = op_log[op_log['Type'] == 'BUY']
        sells = op_log[op_log['Type'] == 'SELL']
        if not buys.empty:
            ax1.scatter(buys['Date'], buys['Price'], color='red', 
                       marker='^', s=40, label='买入', zorder=5, alpha=0.6)
        if not sells.empty:
            ax1.scatter(sells['Date'], sells['Price'], color='green', 
                       marker='v', s=40, label='卖出', zorder=5, alpha=0.6)
    
    # 区域背景色
    zone_colors = {
        'A': '#FFE5E5', 'B': '#FFD4D4', 'C': '#FFF8DC',
        'D': '#E8F5E9', 'E': '#E3F2FD', 'F': '#F3E5F5'
    }
    
    for zone, color in zone_colors.items():
        zone_data = df[df['Zone'] == zone]
        if not zone_data.empty:
            for idx in range(len(zone_data) - 1):
                ax1.axvspan(zone_data.iloc[idx]['Date'], 
                           zone_data.iloc[idx + 1]['Date'],
                           alpha=0.15, color=color)
    
    ax1.legend(loc='best', fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.set_title("价格走势与交易点 (带区域背景色)", fontsize=12, fontweight='bold')
    ax1.set_ylabel("价格")
    
    # === 图2: 资金构成 (Bc, Ba, S_acc) ===
    ax2 = fig.add_subplot(gs[1, :])
    ax2.plot(df['Date'], df['Bc'].astype(float), label='持仓市值 (Bc)', color='#F7B801', linewidth=1.5)
    ax2.plot(df['Date'], df['Ba'].astype(float), label='累计投入 (Ba)', color='#F18701', linewidth=1.5, linestyle='--')
    ax2.plot(df['Date'], df['S_acc'].astype(float), label='累计回收 (S_acc)', color='#7678ED', linewidth=1.5)
    
    ax2.legend(loc='best', fontsize=9)
    ax2.grid(True, alpha=0.3)
    ax2.set_title("资金构成曲线", fontsize=12, fontweight='bold')
    ax2.set_ylabel("金额")
    
    # === 图3: 全局资产曲线 ===
    ax3 = fig.add_subplot(gs[2, :])
    df['TotalAssets_float'] = df['TotalAssets'].astype(float)
    ax3.plot(df['Date'], df['TotalAssets_float'], 
             label='总资产 (现金+持仓)', color='#6A1B9A', linewidth=2)
    ax3.axhline(StrategyConfig.total_initial_cash, color='gray', 
                linestyle='--', linewidth=1, label='初始资金')
    
    ax3.legend(loc='best', fontsize=9)
    ax3.grid(True, alpha=0.3)
    ax3.set_title("全局资产曲线 (核心评估指标)", fontsize=12, fontweight='bold')
    ax3.set_ylabel("总资产")
    
    # === 图4: 双收益率对比 ===
    ax4 = fig.add_subplot(gs[3, 0])
    df['Yield_i_float'] = df['Yield_i'].astype(float) * 100
    df['GlobalYield_float'] = df['GlobalYield'].astype(float) * 100
    
    ax4.plot(df['Date'], df['Yield_i_float'], 
             label='策略内部收益率 (i)', color='#FF6F00', linewidth=1)
    ax4.plot(df['Date'], df['GlobalYield_float'], 
             label='全局累计收益率', color='#1976D2', linewidth=1.5)
    ax4.axhline(0, color='black', linewidth=1, linestyle='-')
    
    ax4.legend(loc='best', fontsize=8)
    ax4.grid(True, alpha=0.3)
    ax4.set_title("双收益率对比", fontsize=11, fontweight='bold')
    ax4.set_ylabel("收益率 (%)")
    
    # === 图5: 区域分布 ===
    ax5 = fig.add_subplot(gs[3, 1])
    zone_counts = df['Zone'].value_counts()
    colors_pie = [zone_colors.get(z, '#CCCCCC') for z in zone_counts.index]
    
    ax5.pie(zone_counts.values, labels=zone_counts.index, autopct='%1.1f%%',
            colors=colors_pie, startangle=90)
    ax5.set_title("区域停留时间占比", fontsize=11, fontweight='bold')
    
    # === 图6: 回撤曲线 ===
    ax6 = fig.add_subplot(gs[4, 0])
    running_max = df['TotalAssets_float'].expanding().max()
    drawdown = (df['TotalAssets_float'] - running_max) / running_max * 100
    
    ax6.fill_between(df['Date'], drawdown, 0, color='#D32F2F', alpha=0.3)
    ax6.plot(df['Date'], drawdown, color='#B71C1C', linewidth=1)
    ax6.axhline(0, color='black', linewidth=1)
    
    ax6.grid(True, alpha=0.3)
    ax6.set_title("回撤曲线 (基于总资产)", fontsize=11, fontweight='bold')
    ax6.set_ylabel("回撤 (%)")
    
    # === 图7: 现金流分析 ===
    ax7 = fig.add_subplot(gs[4, 1])
    
    if not op_log.empty:
        op_log['Amount_float'] = op_log['Amount'].astype(float)
        op_log_sorted = op_log.sort_values('Date')
        
        # 累计投入和累计回收
        buys_cumsum = op_log_sorted[op_log_sorted['Type'] == 'BUY']['Amount_float'].cumsum()
        sells_cumsum = op_log_sorted[op_log_sorted['Type'] == 'SELL']['Amount_float'].cumsum()
        
        buy_dates = op_log_sorted[op_log_sorted['Type'] == 'BUY']['Date']
        sell_dates = op_log_sorted[op_log_sorted['Type'] == 'SELL']['Date']
        
        if not buys_cumsum.empty:
            ax7.plot(buy_dates, buys_cumsum.values, 
                    label='累计投入', color='#D32F2F', linewidth=1.5, marker='o', markersize=2)
        if not sells_cumsum.empty:
            ax7.plot(sell_dates, sells_cumsum.values, 
                    label='累计回收', color='#388E3C', linewidth=1.5, marker='s', markersize=2)
    
    ax7.legend(loc='best', fontsize=8)
    ax7.grid(True, alpha=0.3)
    ax7.set_title("现金流分析", fontsize=11, fontweight='bold')
    ax7.set_ylabel("累计金额")
    
    # 保存图表
    plt.savefig(os.path.join(output_folder, 'backtest_comprehensive.png'), dpi=150, bbox_inches='tight')
    plt.close()


def generate_report(output_folder, strat, final_value, global_metrics):
    """生成文字报告"""
    
    roi = (final_value - StrategyConfig.total_initial_cash) / StrategyConfig.total_initial_cash
    invest_ratio = strat.max_Ba / StrategyConfig.total_initial_cash if StrategyConfig.total_initial_cash > 0 else 0
    
    report_lines = [
        "=" * 60,
        "Freq Grid V2 策略回测报告",
        f"标的: {StrategyConfig.stock_code}",
        f"回测区间: {StrategyConfig.start_date} - {StrategyConfig.end_date}",
        "=" * 60,
        "",
        "【一、策略内部口径】",
        f"  初始资金:     {StrategyConfig.total_initial_cash:>15,.2f}",
        f"  期末资产:     {final_value:>15,.2f}",
        f"  期末收益率:   {roi:>15.2%}",
        f"  最大投入(Ba): {strat.max_Ba:>15,.2f}  ({invest_ratio:.1%})",
        f"  累计回收(S):  {strat.S_acc:>15,.2f}",
        f"  交易次数:     {strat.total_trades:>15}",
        "",
        "【二、全局核算口径】（权威评估依据）",
        f"  总投入本金:         {global_metrics.get('total_invested', 0):>15,.2f}",
        f"  总回收现金:         {global_metrics.get('total_withdrawn', 0):>15,.2f}",
        f"  期末总资产:         {global_metrics.get('terminal_assets', 0):>15,.2f}",
        f"  全局净利润:         {global_metrics.get('global_profit', 0):>15,.2f}",
        f"  全局累计收益率:     {global_metrics.get('global_return', 0):>15.2%}",
        f"  全局年化收益率:     {global_metrics.get('global_annual_return', 0):>15.2%}",
        f"  全局最大回撤:       {global_metrics.get('global_max_drawdown', 0):>15.2%}",
        f"  回测年数:           {global_metrics.get('backtest_years', 0):>15.2f}",
        f"  最大现金占用:       {global_metrics.get('max_cash_usage', 0):>15,.2f}",
        f"  本金回收时点:       {global_metrics.get('capital_recovered_date', 'N/A')}",
        "",
        "【三、策略参数】",
        f"  Ao (初始基准价):    {StrategyConfig.Ao}",
        f"  Af (预期最低价):    {StrategyConfig.Af}",
        f"  Bo (初始仓位):      {StrategyConfig.Bo:,.0f}",
        f"  Bf (最大投资):      {StrategyConfig.Bf:,.0f}",
        f"  阈值模式:           {StrategyConfig.threshold_mode}",
        f"  固定阈值:           {StrategyConfig.fixed_threshold:.2%}",
        f"  缓冲天数:           {StrategyConfig.buffer_days}",
        "",
        "【四、风险提示】",
        f"  - 策略假设持续持有直至区域F",
        f"  - 回测不包含极端黑天鹅事件",
        f"  - 实盘需考虑流动性和滑点",
        "=" * 60,
    ]
    
    report_path = os.path.join(output_folder, 'report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    
    print('\n'.join(report_lines))
    print(f"\n报告已保存: {report_path}")


def run_backtest():
    """运行回测"""
    print("=" * 60)
    print("Freq Grid V2 策略回测系统")
    print("=" * 60)
    
    cerebro = bt.Cerebro()
    
    # === 1. 获取数据 ===
    stock_code = StrategyConfig.stock_code
    start_date = StrategyConfig.start_date
    end_date = StrategyConfig.end_date
    
    print(f"\n正在获取数据: {stock_code} ({start_date} - {end_date})...")
    
    try:
        df = fetch_data(stock_code, start_date, end_date)
        
        # 价格缩放 (指数需要除以100)
        if stock_code.endswith('.SH') or stock_code.endswith('.SZ'):
            if stock_code.startswith('0003') or stock_code.startswith('3999'):  # 指数
                print("检测到指数代码，价格缩放1/100")
                for col in ['open', 'high', 'low', 'close']:
                    df[col] = df[col] / 100.0
        
        print(f"数据获取成功，共 {len(df)} 条记录")
        print(f"首日收盘价: {df['close'].iloc[0]:.2f}")
        print(f"末日收盘价: {df['close'].iloc[-1]:.2f}")
        
    except Exception as e:
        print(f"数据获取失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # === 2. 添加数据到Cerebro ===
    data = PandasData(dataname=df)
    cerebro.adddata(data)
    
    # === 3. 创建输出目录 ===
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    output_folder = os.path.join("results", f"{stock_code}_FreqGridV2_{timestamp}")
    os.makedirs(output_folder, exist_ok=True)
    print(f"\n输出目录: {output_folder}")
    
    # === 4. 添加策略 ===
    cerebro.addstrategy(FreqGridV2Strategy, output_folder=output_folder)
    
    # === 5. 配置Broker ===
    cerebro.broker.setcash(StrategyConfig.total_initial_cash)
    cerebro.broker.setcommission(commission=StrategyConfig.commission)
    
    # === 6. 添加分析器 ===
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.02)
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade')
    
    # === 7. 运行回测 ===
    print("\n开始回测...")
    print(f"初始资金: {cerebro.broker.get_value():,.2f}")
    
    results = cerebro.run()
    strat = results[0]
    final_value = cerebro.broker.get_value()
    
    print(f"期末资产: {final_value:,.2f}")
    print(f"收益率: {(final_value - StrategyConfig.total_initial_cash) / StrategyConfig.total_initial_cash:.2%}")
    
    # === 8. 计算全局指标 ===
    print("\n计算全局核算指标...")
    details_df = pd.read_csv(os.path.join(output_folder, 'daily_details.csv'))
    operations_df = pd.read_csv(os.path.join(output_folder, 'operations.csv'))
    
    global_metrics = calculate_global_metrics(
        details_df, operations_df, StrategyConfig.total_initial_cash
    )
    
    # === 9. 生成报告 ===
    print("\n生成报告...")
    generate_report(output_folder, strat, final_value, global_metrics)
    
    # === 10. 生成图表 ===
    if ReportConfig.generate_plot:
        print("\n生成可视化图表...")
        try:
            generate_visualization(output_folder, stock_code)
            print(f"图表已保存: {os.path.join(output_folder, 'backtest_comprehensive.png')}")
        except Exception as e:
            print(f"图表生成失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("回测完成！")
    print("=" * 60)


if __name__ == '__main__':
    run_backtest()
