import backtrader as bt
from config import MACDStrategyParams
import csv

class MACDStrategy(bt.Strategy):
    params = (
        ('maperiod', MACDStrategyParams.maperiod),
        ('fastperiod', MACDStrategyParams.fastperiod),
        ('slowperiod', MACDStrategyParams.slowperiod),
        ('signalperiod', MACDStrategyParams.signalperiod),
    )

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.order = None

        # Prepare operation log file
        self.op_log_file = open('operation_log.csv', 'w', newline='')
        self.op_writer = csv.writer(self.op_log_file)
        self.op_writer.writerow([
            '操作日期', '操作类型', '成交价格', '成交数量', 
            '成交后持仓', '持仓金额', '成交后现金', '总金额', '手续费'
        ])

        # Add a MACD indicator
        self.macd = bt.indicators.MACD(
            self.datas[0],
            period_me1=self.p.fastperiod,
            period_me2=self.p.slowperiod,
            period_signal=self.p.signalperiod
        )

        # Cross of macd and signal
        self.crossover = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)

    def stop(self):
        """Close the operation log file when the backtest is over."""
        self.op_log_file.close()

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            op_type = '买入' if order.isbuy() else '卖出'
            
            position_value = self.position.size * self.position.price if self.position else 0
            
            self.log(
                f'{op_type} EXECUTED, Price: {order.executed.price:.2f}, '
                f'Cost: {order.executed.value:.2f}, Comm: {order.executed.comm:.2f}'
            )
            
            # Write to operation log
            self.op_writer.writerow([
                self.datas[0].datetime.date(0).isoformat(),
                op_type,
                f'{order.executed.price:.2f}',
                order.executed.size,
                self.position.size,
                f'{position_value:.2f}',
                f'{self.broker.getcash():.2f}',
                f'{self.broker.getvalue():.2f}',
                f'{order.executed.comm:.2f}'
            ])

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' %
                 (trade.pnl, trade.pnlcomm))

    def next(self):
        # Simply log the closing price of the series from the reference
        # self.log('Close, %.2f' % self.dataclose[0]) # This is too noisy, disable for now

        # Check if an order is pending ... if yes, we cannot send a 2nd one
        if self.order:
            return

        # Check if we are in the market
        if not self.position:
            # Not yet ... we MIGHT BUY if ...
            if self.crossover > 0:
                self.log('BUY CREATE, %.2f' % self.dataclose[0])
                self.order = self.buy()

        else:
            if self.crossover < 0:
                self.log('SELL CREATE, %.2f' % self.dataclose[0])
                self.order = self.sell()

    def log(self, txt, dt=None):
        ''' Logging function for this strategy'''
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))
