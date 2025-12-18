import sys
import os
# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import backtrader as bt
from common.data_fetcher import fetch_data
from strategies.valuation_pyramid.strategy import ValuationStrategy, ValuationPandasData
from strategies.valuation_pyramid import config
from config import global_config
import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# 设置中文字体
try:
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
except:
    pass

def generate_visualization(output_folder):
    """生成可视化图表"""
    details_path = os.path.join(output_folder, 'details.csv')
    op_log_path = os.path.join(output_folder, 'operation_log.csv')
    
    if not os.path.exists(details_path): return
    df = pd.read_csv(details_path)
    df['日期'] = pd.to_datetime(df['日期'])
    
    op_log = pd.DataFrame()
    if os.path.exists(op_log_path):
        op_log = pd.read_csv(op_log_path)
        op_log['日期'] = pd.to_datetime(op_log['日期'])

    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)
    fig.suptitle(f'金字塔双线估值策略回测 - {config.STOCK_CODE}', fontsize=16, fontweight='bold')
    
    # 图1: 价格 + 买卖点
    ax1 = axes[0]
    ax1.plot(df['日期'], df['收盘价'], label='收盘价', color='#2E86AB')
    if not op_log.empty:
        buys = op_log[op_log['操作类型'] == '买入']
        sells = op_log[op_log['操作类型'] == '卖出']
        if not buys.empty: ax1.scatter(buys['日期'], buys['成交价格'], color='red', marker='^', s=80, label='买入', zorder=5)
        if not sells.empty: ax1.scatter(sells['日期'], sells['成交价格'], color='green', marker='v', s=80, label='卖出', zorder=5)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_title("价格走势")

    # 图2: 资产
    ax2 = axes[1]
    ax2.plot(df['日期'], df['总资产'], label='总资产', color='#8A2BE2')
    # 基准
    init_cash = df['总资产'].iloc[0]
    init_price = df['收盘价'].iloc[0]
    bm_val = df['收盘价'] * (init_cash / init_price)
    ax2.plot(df['日期'], bm_val, label='基准(买入持有)', color='gray', linestyle='--')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_title("资产曲线")

    # 图3: 估值与仓位
    ax3 = axes[2]
    ax3r = ax3.twinx()
    ax3r.plot(df['日期'], df['估值分位点'], color='orange', alpha=0.6, label='分位点')
    
    # 画线
    buy_levels = config.ValuationParams.buy_tiers
    sell_levels = config.ValuationParams.sell_tiers
    for l, t in buy_levels:
        ax3r.axhline(l, color='green', linestyle='--', alpha=0.3)
    for l, t in sell_levels:
        ax3r.axhline(l, color='red', linestyle='--', alpha=0.3)
        
    ax3.fill_between(df['日期'], 0, df['仓位比例'], color='#06D6A0', alpha=0.3, label='仓位')
    ax3.set_ylim(0, 1.1)
    ax3.legend(loc='upper left')
    ax3r.legend(loc='upper right')
    ax3.set_title("分位点与仓位")
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, 'valuation_plot.png'))
    plt.close()

def generate_report(cerebro, strat, output_folder, benchmark_return, fetch_start_date, trading_start_date, ref_period_info=None):
    final_value = cerebro.broker.get_value()
    initial_cash = strat.p.total_initial_cash
    
    # 统计
    details_path = os.path.join(output_folder, 'details.csv')
    df = pd.read_csv(details_path)
    
    # 估值分布统计源
    if strat.ref_history_vals is not None:
        full_vals = strat.ref_history_vals
        dist_source = "固定历史参考区间"
    else:
        full_vals = [x for x in list(strat.valuation_data.array) if x > 0 and not np.isnan(x)]
        dist_source = "滚动历史窗口"
        
    val_series = pd.Series(full_vals)
    val_stats = val_series.describe()
    
    total_ret = (final_value - initial_cash) / initial_cash
    
    lines = []
    lines.append("="*60)
    lines.append(f"金字塔双线估值策略报告 - {config.STOCK_CODE}")
    lines.append("="*60)
    lines.append("\n[策略机制]")
    lines.append("类型: 金字塔建仓 + 中间持有 + 分批止盈")
    
    if ref_period_info:
        lines.append(f"分位点参考系: {dist_source} ({ref_period_info})")
    else:
        lines.append(f"分位点参考系: {dist_source} (滚动过去 {config.ValuationParams.lookback_years} 年)")
        
    lines.append("买入逻辑 (Min Target):")
    for l, t in config.ValuationParams.buy_tiers:
        lines.append(f"  - 分位点 < {l:.0%}: 仓位补足至 {t:.0%}")
    lines.append("卖出逻辑 (Max Limit):")
    for l, t in config.ValuationParams.sell_tiers:
        lines.append(f"  - 分位点 > {l:.0%}: 仓位限制在 {t:.0%}")
    lines.append("中间区域: 维持当前仓位不动。")
    
    lines.append(f"\n[收益表现]")
    lines.append(f"总收益率: {total_ret:.2%}")
    lines.append(f"基准收益: {benchmark_return:.2%}")
    lines.append(f"超额收益: {total_ret - benchmark_return:.2%}")
    drawdown = 0
    if 'drawdown' in strat.analyzers.getnames():
        drawdown = strat.analyzers.drawdown.get_analysis()['max']['drawdown']
    lines.append(f"最大回撤: {drawdown:.2f}%")
    
    lines.append(f"\n[交易统计]")
    lines.append(f"总交易次数: {strat.total_trades}")
    
    with open(os.path.join(output_folder, 'backtest_results.txt'), 'w') as f:
        f.write('\n'.join(lines))
    print('\n'.join(lines))

if __name__ == '__main__':
    cerebro = bt.Cerebro()
    
    run_ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    out_dir = os.path.join('results', f'{config.STOCK_CODE}-Pyramid-{config.START_DATE}-{run_ts}')
    os.makedirs(out_dir, exist_ok=True)
    
    # 准备参考分位点数据
    reference_values = None
    ref_period_info = None
    metric_name = config.ValuationParams.metric
    
    if hasattr(config.ValuationParams, 'use_fixed_reference') and config.ValuationParams.use_fixed_reference:
        ref_start = config.ValuationParams.reference_start_date
        ref_end = config.ValuationParams.reference_end_date
        print(f"正在获取历史参考数据: {ref_start} 至 {ref_end} ...")
        
        try:
            ref_data = fetch_data(config.STOCK_CODE, ref_start, ref_end)
            if metric_name in ref_data.columns:
                # 提取非空值
                reference_values = ref_data[metric_name].dropna().tolist()
                reference_values = [x for x in reference_values if x > 0]
                print(f"  - 获取到 {len(reference_values)} 条有效估值数据")
                ref_period_info = f"{ref_start} - {ref_end}"
            else:
                print(f"警告: 参考数据中不包含 {metric_name} 列")
        except Exception as e:
            print(f"获取参考数据失败: {e}")
            sys.exit(1)
            
        # 如果使用了参考数据，回测数据就不需要很长的 lookback 了，
        # 只需要往前一点点 (比如30天) 确保均线等（虽然本策略可能不用）能计算即可
        fetch_start = (datetime.datetime.strptime(config.START_DATE, '%Y%m%d') - datetime.timedelta(days=30)).strftime('%Y%m%d')
    else:
        # 使用滚动窗口，需要长 lookback
        fetch_start = (datetime.datetime.strptime(config.START_DATE, '%Y%m%d') - datetime.timedelta(days=int(config.ValuationParams.lookback_years*365+30))).strftime('%Y%m%d')
    
    print(f"获取回测数据: {fetch_start} 至 {config.END_DATE}")
    data = fetch_data(config.STOCK_CODE, fetch_start, config.END_DATE)
    
    cerebro.adddata(ValuationPandasData(dataname=data, name=config.STOCK_CODE))
    
    # 传递 reference_values 给策略
    cerebro.addstrategy(ValuationStrategy, 
                       output_folder=out_dir, 
                       trade_start_date=config.START_DATE,
                       reference_values=reference_values)
    
    cerebro.broker.setcash(config.ValuationParams.total_initial_cash)
    cerebro.broker.setcommission(commission=global_config.COMMISSION)
    
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    
    print("开始回测...")
    results = cerebro.run()
    strat = results[0]
    
    # Calc Benchmark
    bm_ret = 0.0
    try:
        df = pd.read_csv(os.path.join(out_dir, 'details.csv'))
        if not df.empty:
            p0, p1 = df['收盘价'].iloc[0], df['收盘价'].iloc[-1]
            bm_ret = (p1 - p0) / p0
    except: pass
    
    generate_report(cerebro, strat, out_dir, bm_ret, fetch_start, config.START_DATE, ref_period_info)
    generate_visualization(out_dir)
