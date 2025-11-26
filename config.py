# tushare_token.py
TUSHARE_TOKEN = '36c643f995ba9828b822f1872dda95372f89787eb912dad38c3b0375'  # Replace with your Tushare token

# Data source: 'tushare' or 'akshare' or 'baostock'
DATA_SOURCE = 'baostock'

# Backtest settings
ENABLE_BENCHMARK = True # Set to True to enable benchmark comparison
STOCK_CODE = '000300.SH'

# 牛市周期 20241101 - 20251101
# 熊市周期 20230201 - 20240201
# 震荡周期 20201101 - 20251101

START_DATE = '20230201'
END_DATE = '20240201'
INITIAL_CASH = 100000.0
STAKE_PERCENT = 0.95  # Percentage of portfolio to trade
COMMISSION = 0.00005  # Commission fee

# Strategy parameters
class MACDStrategyParams:
    maperiod = 15
    fastperiod = 12
    slowperiod = 26
    signalperiod = 9
