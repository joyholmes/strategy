# tushare_token.py
TUSHARE_TOKEN = '36c643f995ba9828b822f1872dda95372f89787eb912dad38c3b0375'  # Replace with your Tushare token

# Data source: 'tushare' or 'akshare' or 'baostock'
DATA_SOURCE = 'baostock'

# Backtest settings
ENABLE_BENCHMARK = True # Set to True to enable benchmark comparison
STOCK_CODE = '000300.SH'

# 牛市周期 20241101 - 20251101
# 熊市周期 20230201 - 20240201
# 震荡周期 20210101 - 20220101
# 长周期 20210101 - 20251201

START_DATE = '20210101'
END_DATE = '20251201'
INITIAL_CASH = 100000.0
STAKE_PERCENT = 0.95  # Percentage of portfolio to trade
COMMISSION = 0.00005  # Commission fee

# Strategy parameters
class MACDStrategyParams:
    maperiod = 15
    fastperiod = 12
    slowperiod = 26
    signalperiod = 9

# Position Management Strategy parameters
class PositionManagementParams:
    # 总初始资金
    total_initial_cash = 100000.0
    
    # GDP年化增长率
    gdp_rate = 0.07
    
    # 周期配置
    # 每个周期包含: id(周期编号), ratio(仓位比例), vix_threshold(波动率阈值)
    cycles = [
        {
            'id': 'Cycle_1',
            'ratio': 0.10,
            'initial_cash': 100000.0 * 0.10,  # 10,000
            'vix_threshold': 0.02  # 2%
        },
        {
            'id': 'Cycle_2',
            'ratio': 0.20,
            'initial_cash': 100000.0 * 0.20,  # 20,000
            'vix_threshold': 0.04  # 4%
        },
        {
            'id': 'Cycle_3',
            'ratio': 0.30,
            'initial_cash': 100000.0 * 0.30,  # 30,000
            'vix_threshold': 0.08  # 8%
        },
        {
            'id': 'Cycle_4',
            'ratio': 0.40,
            'initial_cash': 100000.0 * 0.40,  # 40,000
            'vix_threshold': 0.16  # 16%
        },
    ]

