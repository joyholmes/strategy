
import sys
import os
import backtrader as bt
import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from strategies.freq_grid.config import GridParams
from strategies.freq_grid.strategy import FreqGridStrategy
from common.data_fetcher import fetch_data

# 设置中文字体
try:
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
except:
    pass

class PandasData(bt.feeds.PandasData):
    params = (
        ('datetime', None),
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'volume'),
        ('openinterest', None),
    )

def generate_visualization(output_folder, stock_code):
    """生成可视化图表"""
    details_path = os.path.join(output_folder, 'details.csv')
    op_log_path = os.path.join(output_folder, 'operation_log.csv')
    
    if not os.path.exists(details_path): return
    df = pd.read_csv(details_path)
    if df.empty: return
    df['Date'] = pd.to_datetime(df['Date'])
    
    op_log = pd.DataFrame()
    if os.path.exists(op_log_path):
        op_log = pd.read_csv(op_log_path)
        if not op_log.empty:
            op_log['Date'] = pd.to_datetime(op_log['Date'])

    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)
    fig.suptitle(f'网格策略回测 (FreqGrid) - {stock_code}', fontsize=16, fontweight='bold')
    
    # 图1: 价格 + 买卖点
    ax1 = axes[0]
    ax1.plot(df['Date'], df['Close'], label='Price', color='#2E86AB', linewidth=1)
    
    if not op_log.empty:
        buys = op_log[op_log['Type'].str.contains('Buy')]
        sells = op_log[op_log['Type'].str.contains('Sell')]
        if not buys.empty: 
            ax1.scatter(buys['Date'], buys['Price'], color='red', marker='^', s=60, label='Buy', zorder=5)
        if not sells.empty: 
            ax1.scatter(sells['Date'], sells['Price'], color='green', marker='v', s=60, label='Sell', zorder=5)
    
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_title("价格与交易点")
    ax1.set_ylabel("价格")

    # 图2: 资金构成
    ax2 = axes[1]
    ax2.plot(df['Date'], df['PositionVal(Bc)'], label='持仓市值 (Bc)', color='#F7B801')
    ax2.plot(df['Date'], df['Ba'], label='投入本金 (Ba)', color='#F18701', linestyle='--')
    ax2.plot(df['Date'], df['S_acc'], label='累计回收 (S_acc)', color='#7678ED')
    
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_title("资金构成 (市值 vs 本金 vs 现金回收)")
    ax2.set_ylabel("金额")

    # 图3: 收益率与Zone
    ax3 = axes[2]
    # 将 Zone 映射为数字以便绘图
    zone_map = {'A': 1, 'B': 0, 'C': 2, 'D': 3, 'E': 4, 'F': 5}
    # 处理 Zone 列可能出现的空值或非字符
    df['ZoneNum'] = df['Zone'].map(zone_map).fillna(1)
    
    # Yield 清洗 ('-15.3%' -> -0.153)
    def clean_yield(x):
        try:
            return float(x.replace('%', '')) / 100
        except:
            return 0.0
            
    df['YieldVal'] = df['Yield'].apply(clean_yield)
    
    ax3.plot(df['Date'], df['YieldVal'], label='Current Yield', color='purple')
    
    ax3r = ax3.twinx()
    ax3r.scatter(df['Date'], df['ZoneNum'], s=3, color='gray', alpha=0.3, label='Zone')
    ax3r.set_yticks(list(zone_map.values()))
    ax3r.set_yticklabels(list(zone_map.keys()))
    
    ax3.axhline(0, color='black', linewidth=1, linestyle='-')
    ax3.legend(loc='upper left')
    ax3.set_title("浮动收益率(Yield) 与 区域状态(Zone)")
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, 'backtest_plot.png'))
    plt.close()

def run_strategy():
    cerebro = bt.Cerebro()

    # 1. Config & Data
    stock_code = GridParams.stock_code
    start_date = "20150101"
    end_date = "20251201"
    
    print(f"Fetching data for {stock_code} from {start_date} to {end_date}...")
    try:
        df = fetch_data(stock_code, start_date, end_date)
        
        # Scaling Price
        print("Scaling Price by 1/100 ...")
        cols_to_scale = ['open', 'high', 'low', 'close']
        for col in cols_to_scale:
            df[col] = df[col] / 100.0
        
    except Exception as e:
        print(f"Error fetching data: {e}")
        return

    data = PandasData(dataname=df)
    cerebro.adddata(data)

    # 2. Add Strategy
    output_folder = os.path.join("results", f"{stock_code}_FreqGrid_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(output_folder, exist_ok=True)
    
    first_close = df['close'].iloc[0]
    print(f"First Date Close: {first_close:.2f} (Config Ao: {GridParams.Ao})")
    
    cerebro.addstrategy(FreqGridStrategy, output_folder=output_folder)

    # 3. Broker & Analyzers
    cerebro.broker.setcash(GridParams.total_initial_cash)
    cerebro.broker.setcommission(commission=0.0003)
    
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.02)
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade')

    print(f"Starting Portfolio Value: {cerebro.broker.get_value():.2f}")
    results = cerebro.run()
    
    final_val = cerebro.broker.get_value()
    strat = results[0]
    
    # 4. Generate Report
    roi = (final_val - GridParams.total_initial_cash) / GridParams.total_initial_cash
    
    dd = strat.analyzers.drawdown.get_analysis()
    max_dd = dd.max.drawdown if 'max' in dd else 0
    sharpe = strat.analyzers.sharpe.get_analysis().get('sharperatio', 0)
    
    # 辅助显示全部信息
    # 如果 Ba 是0 (没买过), max_Ba 也是 0
    invest_ratio = strat.max_Ba/GridParams.total_initial_cash if GridParams.total_initial_cash else 0
    
    report_lines = [
        "=" * 40,
        f"FreqGrid Strategy Report - {stock_code}",
        f"Range: {start_date} - {end_date}",
        "=" * 40,
        f"Initial Cash: {GridParams.total_initial_cash:,.2f}",
        f"Final Value : {final_val:,.2f}",
        f"Return      : {roi:.2%}",
        f"Max Drawdown: {max_dd:.2f}%",
        f"Sharpe Ratio: {sharpe if sharpe else 0:.2f}",
        "-" * 40,
        f"Trades      : {strat.total_trades}",
        f"Max Invested: {strat.max_Ba:,.2f} ({invest_ratio:.1%})",
        f"Total Sold(S): {strat.S_acc:,.2f}",
        "-" * 40,
        "Params:",
        f"  Ao (Ref Price): {GridParams.Ao}",
        f"  Af (Floor)    : {GridParams.Af}",
        f"  Bo (Initial)  : {GridParams.Bo}",
        f"  Bf (Max)      : {GridParams.Bf}",
        "=" * 40
    ]
    
    report_path = os.path.join(output_folder, 'report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
        
    print('\n'.join(report_lines))
    print(f"Report saved to: {report_path}")
    
    # 5. Visualization
    try:
        generate_visualization(output_folder, stock_code)
        print(f"Plot saved to: {os.path.join(output_folder, 'backtest_plot.png')}")
    except Exception as e:
        print(f"Visualization failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    run_strategy()
