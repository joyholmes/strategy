import backtrader as bt
from data_fetcher import fetch_data
from strategies.macd_strategy import MACDStrategy
import config
import datetime
import os
import csv

def generate_report(cerebro, strat, results, output_folder, benchmark_return=None, buy_and_hold_return=None):
    """
    Generates a text report and returns a dictionary with key metrics.
    """
    analysis = strat.analyzers.getbyname('mytradeanalyzer').get_analysis()
    returns = strat.analyzers.getbyname('myreturns').get_analysis()
    sharpe = strat.analyzers.getbyname('mysharpe').get_analysis()
    drawdown = strat.analyzers.getbyname('mydrawdown').get_analysis()

    # --- Generate Text Report ---
    report_lines = []
    # ... (rest of the text report generation is the same)
    report_lines.append("="*50)
    report_lines.append(f"Backtest Report for: {config.STOCK_CODE}")
    report_lines.append(f"Data Source: {config.DATA_SOURCE}")
    report_lines.append(f"Period: {config.START_DATE} to {config.END_DATE}")
    report_lines.append(f"Report Generated at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("="*50)
    report_lines.append("\n")

    report_lines.append("--- Strategy Parameters ---")
    report_lines.append(f"MACD Fast Period: {strat.params.fastperiod}")
    report_lines.append(f"MACD Slow Period: {strat.params.slowperiod}")
    report_lines.append(f"MACD Signal Period: {strat.params.signalperiod}")
    report_lines.append(f"Stake Percentage: {config.STAKE_PERCENT*100}%")
    report_lines.append("\n")

    report_lines.append("--- Final Capital Status ---")
    report_lines.append(f"Initial Portfolio Value: {cerebro.broker.startingcash:.2f}")
    report_lines.append(f"Final Portfolio Value:   {cerebro.broker.getvalue():.2f}")
    
    total_return_pct = returns.get('rtot', 0) * 100
    buy_and_hold_pct = (buy_and_hold_return * 100) if buy_and_hold_return is not None else 'N/A'
    benchmark_return_pct = (benchmark_return * 100) if benchmark_return is not None else 'N/A'
    
    report_lines.append("\n")
    report_lines.append("--- Portfolio Performance ---")
    report_lines.append(f"Strategy Total Return:   {total_return_pct:.2f}%")
    if buy_and_hold_return is not None:
        report_lines.append(f"Buy and Hold Return:     {buy_and_hold_pct:.2f}%")
    if benchmark_return is not None:
        report_lines.append(f"Benchmark (CSI 300) Return: {benchmark_return_pct:.2f}%")
    report_lines.append("\n")

    sharpe_ratio = sharpe.get('sharperatio', 'N/A')
    max_drawdown_pct = drawdown.max.drawdown
    
    report_lines.append("--- Performance Metrics ---")
    report_lines.append(f"Sharpe Ratio:            {sharpe_ratio}")
    report_lines.append(f"Max Drawdown:            {max_drawdown_pct:.2f}%")
    report_lines.append("\n")

    total_trades = analysis.total.total if 'total' in analysis else 0
    win_rate_pct = (analysis.won.total / total_trades * 100) if total_trades > 0 else 0

    report_lines.append("--- Trade Statistics ---")
    if total_trades > 0:
        report_lines.append(f"Total Trades:            {total_trades}")
        report_lines.append(f"Winning Trades:          {analysis.won.total}")
        report_lines.append(f"Losing Trades:           {analysis.lost.total}")
        report_lines.append(f"Win Rate:                {win_rate_pct:.2f}%")
    else:
        report_lines.append("No trades were executed.")
    
    report_lines.append("\n"+"="*50)
    report_content = "\n".join(report_lines)
    
    report_path = os.path.join(output_folder, 'backtest_results.txt')
    with open(report_path, 'w') as f:
        f.write(report_content)
    
    print(report_content)

    # --- Return summary dictionary ---
    summary = {
        'StockCode': config.STOCK_CODE,
        'Strategy': MACDStrategy.__name__,
        'StartDate': config.START_DATE,
        'EndDate': config.END_DATE,
        'MACD_Fast': strat.params.fastperiod,
        'MACD_Slow': strat.params.slowperiod,
        'MACD_Signal': strat.params.signalperiod,
        'TotalReturnPct': f"{total_return_pct:.2f}",
        'BuyAndHoldReturnPct': f"{buy_and_hold_pct:.2f}" if isinstance(buy_and_hold_pct, float) else 'N/A',
        'BenchmarkReturnPct': f"{benchmark_return_pct:.2f}" if isinstance(benchmark_return_pct, float) else 'N/A',
        'MaxDrawdownPct': f"{max_drawdown_pct:.2f}",
        'SharpeRatio': f"{sharpe_ratio:.4f}" if isinstance(sharpe_ratio, float) else 'N/A',
        'WinRatePct': f"{win_rate_pct:.2f}",
        'TotalTrades': total_trades,
    }
    return summary

def update_summary(summary_data, run_timestamp, folder_name):
    """
    Appends the summary of the backtest to the summary.csv file.
    """
    summary_file = os.path.join('results', 'summary.csv')
    
    # Add run-specific info to the summary
    summary_data['RunTimestamp'] = run_timestamp
    summary_data['ResultFolder'] = folder_name

    header = [
        'StockCode', 'Strategy', 'StartDate', 'EndDate', 
        'MACD_Fast', 'MACD_Slow', 'MACD_Signal', 'TotalReturnPct', 'BuyAndHoldReturnPct',
        'BenchmarkReturnPct', 'MaxDrawdownPct', 'SharpeRatio', 'WinRatePct', 'TotalTrades',
        'RunTimestamp', 'ResultFolder'
    ]

    file_exists = os.path.isfile(summary_file)
    
    with open(summary_file, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if not file_exists:
            writer.writeheader()
        writer.writerow(summary_data)
    
    print(f"\nSummary appended to {summary_file}")


if __name__ == '__main__':
    cerebro = bt.Cerebro(stdstats=False)

    # --- Create unique output directory ---
    strategy_name = MACDStrategy.__name__
    run_timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    folder_name = f"{config.STOCK_CODE}-{strategy_name}-{config.START_DATE}-{config.END_DATE}-{run_timestamp}"
    output_folder = os.path.join('results', folder_name)
    os.makedirs(output_folder, exist_ok=True)

    # Add a strategy, passing the output folder
    cerebro.addstrategy(MACDStrategy, output_folder=output_folder)

    # Add analyzers
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='mysharpe')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='myreturns')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='mydrawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='mytradeanalyzer')
    
    # ... (rest of the setup is the same)
    # Add Observers
    cerebro.addobserver(bt.observers.Broker)
    cerebro.addobserver(bt.observers.Trades)
    cerebro.addobserver(bt.observers.BuySell)
    cerebro.addobserver(bt.observers.Value)

    # Fetch data and add to Cerebro
    data = fetch_data(config.STOCK_CODE, config.START_DATE, config.END_DATE)
    feed = bt.feeds.PandasData(dataname=data, name=config.STOCK_CODE)
    cerebro.adddata(feed)

    # Calculate Buy and Hold return
    buy_and_hold_return = None
    if not data.empty:
        buy_and_hold_return = (data['close'].iloc[-1] - data['close'].iloc[0]) / data['close'].iloc[0]

    # Fetch benchmark data (optional)
    benchmark_return = None
    if config.ENABLE_BENCHMARK:
        print("Fetching benchmark data for CSI 300 Index (000300.SH)...")
        benchmark_data = fetch_data('000300.SH', config.START_DATE, config.END_DATE)
        if not benchmark_data.empty:
            benchmark_feed = bt.feeds.PandasData(dataname=benchmark_data, name='CSI 300')
            cerebro.adddata(benchmark_feed)
            
            benchmark_start = benchmark_data['close'].iloc[0]
            benchmark_end = benchmark_data['close'].iloc[-1]
            benchmark_return = (benchmark_end - benchmark_start) / benchmark_start

    # Set our desired cash start
    cerebro.broker.setcash(config.INITIAL_CASH)

    # Add a PercentSizer sizer according to the stake percent
    cerebro.addsizer(bt.sizers.PercentSizer, percents=config.STAKE_PERCENT * 100)

    # Set the commission
    cerebro.broker.setcommission(commission=config.COMMISSION)

    # Print out the starting conditions
    print(f'Starting Portfolio Value: {cerebro.broker.getvalue():.2f}')

    # Run over everything
    results = cerebro.run()
    strat = results[0]

    # Generate report and get summary
    summary_data = generate_report(cerebro, strat, results, output_folder, benchmark_return, buy_and_hold_return)

    # Update the master summary file
    update_summary(summary_data, run_timestamp, folder_name)

    # Plot the result and save to file
    plot_path = os.path.join(output_folder, 'backtest_plot.png')
    print(f"Saving plot to {plot_path}...")
    
    # Set plot parameters
    plot_params = {
        'style': 'candles',
        'barup': 'red',
        'bardown': 'green',
        'volup': 'red',
        'voldown': 'green',
        'iplot': False,
        'volume': True,
        'plotdist': 0.1,
        'subchart': True,
    }

    figures = cerebro.plot(**plot_params)
    if figures and figures[0]:
        fig = figures[0][0]
        fig.set_size_inches(18.5, 10.5)
        fig.savefig(plot_path, dpi=300)
        print("Plot saved successfully.")
    else:
        print("Could not save plot.")

    print(f"\nAll results saved in: {output_folder}")
