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
    if not os.path.exists(details_path):
        return
        
    df = pd.read_csv(details_path)
    df['日期'] = pd.to_datetime(df['日期'])
    
    fig, axes = plt.subplots(3, 1, figsize=(16, 12))
    
    # 图1: 价格与分位点
    ax1 = axes[0]
    ax1.plot(df['日期'], df['收盘价'], label='价格', color='blue')
    ax1.set_ylabel('价格')
    ax1.legend(loc='upper left')
    
    ax1_right = ax1.twinx()
    ax1_right.plot(df['日期'], df['估值分位点'], label='估值分位点', color='orange', alpha=0.5)
    ax1_right.set_ylabel('分位点')
    ax1_right.fill_between(df['日期'], 0.2, 0.8, color='gray', alpha=0.1, label='正常区间')
    ax1_right.legend(loc='upper right')
    ax1.set_title('价格与估值分位点趋势')
    
    # 图2: 仓位变化
    ax2 = axes[1]
    ax2.plot(df['日期'], df['仓位比例'], label='实际仓位', color='green')
    ax2.plot(df['日期'], df['目标仓位'], label='目标仓位', color='red', linestyle='--')
    ax2.set_ylabel('仓位比例')
    ax2.set_title('仓位变化')
    ax2.legend()
    
    # 图3: 资产曲线
    ax3 = axes[2]
    ax3.plot(df['日期'], df['总资产'], label='总资产', color='purple')
    ax3.set_ylabel('金额')
    ax3.set_title('总资产曲线')
    ax3.legend()
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_folder, 'valuation_plot.png'))
    plt.close()

def generate_report(cerebro, strat, output_folder, benchmark_return=None):
    final_value = cerebro.broker.get_value()
    initial_cash = strat.p.total_initial_cash
    
    # 计算收益
    total_return = (final_value - initial_cash) / initial_cash
    annualized_return = (1 + total_return) ** (365 / len(strat)) - 1 if len(strat) > 0 else 0
    
    # 报告内容
    lines = []
    lines.append("="*50)
    lines.append("估值策略回测报告")
    lines.append(f"标的: {config.STOCK_CODE}")
    lines.append(f"指标: {config.ValuationParams.metric.upper()}")
    lines.append("-" * 30)
    lines.append(f"初始资金: {initial_cash:,.2f}")
    lines.append(f"期末资产: {final_value:,.2f}")
    lines.append(f"最大净投入: {strat.max_net_invested:,.2f}")
    lines.append(f"期末净投入: {strat.net_invested:,.2f}")
    lines.append(f"净收益: {final_value - strat.net_invested:,.2f}")
    lines.append("-" * 30)
    lines.append(f"总收益率: {total_return:.2%}")
    lines.append(f"交易次数: {strat.total_trades}")
    
    if benchmark_return:
        lines.append(f"基准收益: {benchmark_return:.2%}")
        lines.append(f"超额收益: {total_return - benchmark_return:.2%}")
        
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
    
    # 运行
    print("开始回测...")
    results = cerebro.run()
    strat = results[0]
    
    # 基准
    benchmark_return = None
    if config.ENABLE_BENCHMARK:
        try:
            # 简单计算: (Last - First) / First
            benchmark_return = (data['close'].iloc[-1] - data['close'].iloc[0]) / data['close'].iloc[0]
        except:
            pass
            
    generate_report(cerebro, strat, output_folder, benchmark_return)
    generate_visualization(output_folder)
    print(f"\n结果已保存至: {output_folder}")
