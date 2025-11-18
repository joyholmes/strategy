import backtrader as bt
from data_fetcher import fetch_data
from strategies.macd_strategy import MACDStrategy
import config
import datetime

def generate_report(cerebro, strat, results, benchmark_return=None):
    """
    Generates a text report from the backtest results.
    """
    analysis = strat.analyzers.getbyname('mytradeanalyzer').get_analysis()
    returns = strat.analyzers.getbyname('myreturns').get_analysis()
    sharpe = strat.analyzers.getbyname('mysharpe').get_analysis()
    drawdown = strat.analyzers.getbyname('mydrawdown').get_analysis()

    report_lines = []
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
    report_lines.append(f"Final Cash:              {cerebro.broker.getcash():.2f}")
    report_lines.append(f"Final Position Value:    {cerebro.broker.getvalue() - cerebro.broker.getcash():.2f}")
    
    total_comm = 0
    if 'total' in analysis and analysis.get('total', {}).get('total', 0) > 0:
        total_comm = analysis.pnl.net.total - analysis.pnl.gross.total
    report_lines.append(f"Cumulative Commission:   {total_comm:.2f}")
    report_lines.append("\n")

    report_lines.append("--- Portfolio Performance ---")
    total_return = returns.get('rtot', 0)
    report_lines.append(f"Total Return:            {total_return * 100:.2f}%")
    if benchmark_return is not None:
        report_lines.append(f"Benchmark (CSI 300) Return: {benchmark_return * 100:.2f}%")
    report_lines.append("\n")

    report_lines.append("--- Performance Metrics ---")
    report_lines.append(f"Sharpe Ratio:            {sharpe.get('sharperatio', 'N/A')}")
    report_lines.append(f"Max Drawdown:            {drawdown.max.drawdown:.2f}%")
    report_lines.append("\n")

    report_lines.append("--- Trade Statistics ---")
    if 'total' in analysis and analysis.get('total', {}).get('total', 0) > 0:
        report_lines.append(f"Total Trades:            {analysis.total.total}")
        report_lines.append(f"Winning Trades:          {analysis.won.total}")
        report_lines.append(f"Losing Trades:           {analysis.lost.total}")
        report_lines.append(f"Win Rate:                {analysis.won.total / analysis.total.total * 100:.2f}%")
        report_lines.append(f"Average Win ($):         {analysis.won.pnl.average:.2f}")
        report_lines.append(f"Average Loss ($):        {analysis.lost.pnl.average:.2f}")
        report_lines.append(f"Best Winning Trade ($):  {analysis.won.pnl.max:.2f}")
        report_lines.append(f"Worst Losing Trade ($):  {analysis.lost.pnl.max:.2f}")
    else:
        report_lines.append("No trades were executed.")
    
    report_lines.append("\n")
    report_lines.append("="*50)

    report_content = "\n".join(report_lines)
    
    with open('backtest_results.txt', 'w') as f:
        f.write(report_content)
    
    print(report_content)


if __name__ == '__main__':
    cerebro = bt.Cerebro(stdstats=False) # Disable standard stats to customize plot

    # Add a strategy
    cerebro.addstrategy(MACDStrategy)

    # Add analyzers
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='mysharpe')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='myreturns')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='mydrawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='mytradeanalyzer')
    
    # Add Observers
    cerebro.addobserver(bt.observers.Broker)
    cerebro.addobserver(bt.observers.Trades)
    cerebro.addobserver(bt.observers.BuySell)
    cerebro.addobserver(bt.observers.Value)


    # Fetch data and add to Cerebro
    data = fetch_data(config.STOCK_CODE, config.START_DATE, config.END_DATE)
    feed = bt.feeds.PandasData(dataname=data, name=config.STOCK_CODE)
    cerebro.adddata(feed)

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

    # Generate and print the report
    generate_report(cerebro, strat, results, benchmark_return)

    # Plot the result and save to file
    print("Saving plot to backtest_plot.png...")
    
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
        fig.savefig('backtest_plot.png', dpi=300)
        print("Plot saved successfully.")
    else:
        print("Could not save plot.")
