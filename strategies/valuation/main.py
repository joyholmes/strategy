import sys
import os
# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import backtrader as bt
from common.data_fetcher import fetch_data
from common.metrics import calculate_irr
from strategies.valuation.strategy import ValuationStrategy, ValuationPandasData
from strategies.valuation import config
from config import global_config
import datetime
import csv
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def generate_visualization(output_folder):
    """生成可视化图表"""
    details_path = os.path.join(output_folder, 'details.csv')
    op_log_path = os.path.join(output_folder, 'operation_log.csv')
    
    if not os.path.exists(details_path):
        return
        
    df = pd.read_csv(details_path)
    df['日期'] = pd.to_datetime(df['日期'])
    
    op_log = pd.DataFrame()
    if os.path.exists(op_log_path):
        op_log = pd.read_csv(op_log_path)
        op_log['日期'] = pd.to_datetime(op_log['日期'])

    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)
    fig.suptitle(f'估值策略回测可视化 - {config.STOCK_CODE}', fontsize=16, fontweight='bold')
    
    # ========== 图1: 价格走势 + 买卖点 ==========
    ax1 = axes[0]
    ax1.plot(df['日期'], df['收盘价'], label='收盘价', color='#2E86AB', linewidth=1.5)
    
    # 标记买入点
    if not op_log.empty:
        buy_points = op_log[op_log['操作类型'] == '买入']
        if not buy_points.empty:
            ax1.scatter(buy_points['日期'], buy_points['成交价格'], 
                       color='#06D6A0', marker='^', s=100, label='买入', zorder=5, edgecolors='white')
        
        sell_points = op_log[op_log['操作类型'] == '卖出']
        if not sell_points.empty:
            ax1.scatter(sell_points['日期'], sell_points['成交价格'], 
                       color='#EF476F', marker='v', s=100, label='卖出', zorder=5, edgecolors='white')

    ax1.set_title('价格走势与买卖点', fontsize=12, fontweight='bold')
    ax1.set_ylabel('价格')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # ========== 图2: 资金走势 ==========
    ax2 = axes[1]
    ax2.plot(df['日期'], df['总资产'], label='总资产', color='#8A2BE2', linewidth=2)
    # 添加基准对比 (假设全部初始资金买入持有)
    initial_price = df['收盘价'].iloc[0]
    initial_cash = df['总资产'].iloc[0]
    shares = initial_cash / initial_price
    benchmark_values = df['收盘价'] * shares
    ax2.plot(df['日期'], benchmark_values, label='基准(买入持有)', color='gray', linestyle='--', alpha=0.6)
    
    ax2.set_title('资产曲线 vs 基准', fontsize=12, fontweight='bold')
    ax2.set_ylabel('金额')
    ax2.legend(loc='upper left')
    ax2.grid(True, alpha=0.3)
    
    # ========== 图3: 估值分位点与仓位 ==========
    ax3 = axes[2]
    # 双轴
    ax3_right = ax3.twinx()
    
    # 绘制分位点 (右轴)
    ax3_right.plot(df['日期'], df['估值分位点'], label='估值分位点', color='orange', alpha=0.6, linewidth=1)
    ax3_right.set_ylabel('PE/PB 分位点', color='orange')
    ax3_right.fill_between(df['日期'], 0.2, 0.8, color='gray', alpha=0.1, label='正常估值区间')
    ax3_right.axhline(y=0.2, color='green', linestyle=':', alpha=0.5)
    ax3_right.axhline(y=0.8, color='red', linestyle=':', alpha=0.5)
    
    # 绘制仓位 (左轴)
    ax3.fill_between(df['日期'], 0, df['仓位比例'], color='#06D6A0', alpha=0.3, label='仓位比例')
    ax3.set_ylabel('仓位比例', color='green')
    ax3.set_ylim(0, 1.1)
    
    ax3.set_title('估值分位点与仓位变化', fontsize=12, fontweight='bold')
    # 合并图例
    lines, labels = ax3.get_legend_handles_labels()
    lines2, labels2 = ax3_right.get_legend_handles_labels()
    ax3.legend(lines + lines2, labels + labels2, loc='upper left')
    ax3.grid(True, alpha=0.3)
    
    # 格式化日期轴
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.gcf().autofmt_xdate()
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, 'valuation_plot.png'))
    plt.close()

def generate_report(cerebro, strat, output_folder, benchmark_return=None):
    final_value = cerebro.broker.get_value()
    initial_cash = strat.p.total_initial_cash
    net_profit = final_value - strat.net_invested
    
    # 获取分析器结果
    drawdown_info = strat.analyzers.drawdown.get_analysis()
    max_drawdown = drawdown_info.max.drawdown if 'max' in drawdown_info else 0
    
    sharpe_info = strat.analyzers.sharpe.get_analysis()
    sharpe_ratio = sharpe_info.get('sharperatio', 0)
    if sharpe_ratio is None: sharpe_ratio = 0
    
    # 计算估值统计
    # 注意：这里需要重新读取csv来获取完整的估值数据，因为strat对象里只保留了部分
    details_path = os.path.join(output_folder, 'details.csv')
    df = pd.read_csv(details_path)
    pe_stats = df['估值指标'].describe()
    
    # 时间周期计算
    total_days = len(strat)
    years = total_days / 365.0
    total_return = (final_value - initial_cash) / initial_cash
    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0.1 else 0

    lines = []
    lines.append("=" * 60)
    lines.append(f"估值策略回测报告 - {config.STOCK_CODE}")
    lines.append("=" * 60)
    
    lines.append("\n[基本信息]")
    lines.append(f"回测标的: {config.STOCK_CODE}")
    lines.append(f"策略指标: {config.ValuationParams.metric.upper()}")
    # 获取实际回测日期范围
    start_date = df['日期'].iloc[0]
    end_date = df['日期'].iloc[-1]
    lines.append(f"回测周期: {start_date} 至 {end_date}")
    lines.append(f"持续时间: {total_days} 天 ({years:.2f} 年)")
    lines.append(f"数据预载: {config.ValuationParams.lookback_years} 年 (用于消除冷启动波动)")

    lines.append("\n[资金表现]")
    lines.append(f"初始资金: {initial_cash:,.2f}")
    lines.append(f"期末资产: {final_value:,.2f}")
    lines.append(f"最大净投入: {strat.max_net_invested:,.2f}")
    lines.append(f"期末净投入: {strat.net_invested:,.2f}")
    # 净收益建议用绝对增值
    abs_profit = final_value - initial_cash
    lines.append(f"累计净利: {abs_profit:,.2f}") 
    lines.append(f"总收益率: {total_return:.2%}")
    lines.append(f"年化收益: {annual_return:.2%}")
    lines.append(f"最大回撤: {max_drawdown:.2f}%")
    lines.append(f"夏普比率: {sharpe_ratio:.2f}")

    lines.append("\n[基准对比 (买入持有)]")
    lines.append(f"基准收益: {benchmark_return:.2%}")
    lines.append(f"超额收益: {total_return - benchmark_return:.2%}")
    lines.append("(注: 基准收益 = (期末价 - 期初价) / 期初价)")

    lines.append("\n[估值统计]")
    lines.append(f"指标类型: {config.ValuationParams.metric.upper()}")
    lines.append(f"区间最高: {pe_stats['max']:.2f}")
    lines.append(f"区间最低: {pe_stats['min']:.2f}")
    lines.append(f"区间平均: {pe_stats['mean']:.2f}")
    lines.append(f"期末数值: {df['估值指标'].iloc[-1]:.2f}")
    lines.append(f"期末分位: {df['估值分位点'].iloc[-1]:.2%}")

    lines.append("\n[交易统计]")
    lines.append(f"总交易次数: {strat.total_trades}")
    
    # 尝试获取TradeAnalyzer详细数据
    trade_info = strat.analyzers.trades.get_analysis()
    if 'total' in trade_info and trade_info.total.closed > 0:
        total_closed = trade_info.total.closed
        won_total = trade_info.won.total
        lost_total = trade_info.lost.total
        lines.append(f"  - 完成回合: {total_closed}")
        lines.append(f"  - 盈利回合: {won_total}")
        lines.append(f"  - 亏损回合: {lost_total}")
        win_rate = won_total / total_closed
        lines.append(f"  - 胜率: {win_rate:.2%}")
    else:
        lines.append("  - (无已平仓交易统计)")

    report_path = os.path.join(output_folder, 'backtest_results.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
        
    print('\n'.join(lines))

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    
    # 添加策略
    run_timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    output_folder = os.path.join('results', f'{config.STOCK_CODE}-Valuation-{config.START_DATE}-{config.END_DATE}-{run_timestamp}')
    os.makedirs(output_folder, exist_ok=True)
    
    # 获取数据
    print(f"获取数据: {config.STOCK_CODE}")
    try:
        # 为了解决分位点计算的冷启动问题，我们需要预载历史数据
        # 比如往前多取 lookback_years (默认5年) 的数据
        fetch_start_date = (datetime.datetime.strptime(config.START_DATE, '%Y%m%d') - 
                           datetime.timedelta(days=int(config.ValuationParams.lookback_years * 365 + 30))).strftime('%Y%m%d')
        print(f"  - 数据预加载起始日期: {fetch_start_date} (用于计算历史分位点)")
        print(f"  - 策略交易起始日期: {config.START_DATE}")

        data = fetch_data(config.STOCK_CODE, fetch_start_date, config.END_DATE)
        
        # 检查是否有估值数据
        if data['pe'].isnull().all() and data['pb'].isnull().all():
            print("警告: 未获取到PE/PB数据! 策略可能无法正常运行。请检查数据源是否支持指数估值。")
            if global_config.DATA_SOURCE == 'baostock' and config.STOCK_CODE.endswith('.SH'):
                print("提示: Baostock通常不提供指数PE。请尝试切换数据源为Tushare或Akshare，或者使用个股代码回测。")
        
        # 转换为自定义DataFeed
        feed = ValuationPandasData(dataname=data, name=config.STOCK_CODE)
        cerebro.adddata(feed)
        
        # 传入实际交易开始日期给策略，用于过滤
        cerebro.addstrategy(ValuationStrategy, 
                          output_folder=output_folder,
                          trade_start_date=config.START_DATE)
        
        # 移除之前的 addstrategy 调用
        
    except Exception as e:
        print(f"数据获取失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"数据获取失败: {e}")
        sys.exit(1)
        
    # 资金
    cerebro.broker.setcash(config.ValuationParams.total_initial_cash)
    cerebro.broker.setcommission(commission=global_config.COMMISSION)

    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    
    # 运行
    print("开始回测...")
    results = cerebro.run()
    strat = results[0]
    
    # 计算基准收益 (买入持有策略)
    benchmark_return = 0.0
    if len(strat) > 0:
        try:
            # 获取策略实际交易期间的首尾价格
            # 注意: strat.dataclose 是整个预加载后的序列
            # 我们需要知道策略何时开始交易的
            # 简单起见，我们重新读取details.csv里的第一天和最后一天
            # 或者直接用 strat.dataclose 的最后一段（根据回测天数推算）
            
            # 更好的方法: 从 details.csv 读取比较稳
            details_path = os.path.join(output_folder, 'details.csv')
            if os.path.exists(details_path):
                df_bm = pd.read_csv(details_path)
                if not df_bm.empty:
                    p_start = df_bm['收盘价'].iloc[0]
                    p_end = df_bm['收盘价'].iloc[-1]
                    if p_start > 0:
                        benchmark_return = (p_end - p_start) / p_start
        except Exception as e:
            print(f"基准收益计算出错: {e}")

    generate_report(cerebro, strat, output_folder, benchmark_return)
    generate_visualization(output_folder)
    print(f"\n结果已保存至: {output_folder}")
