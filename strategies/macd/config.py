# MACD策略配置

# 回测设置
STOCK_CODE = '000300.SH'
START_DATE = '20230201'
END_DATE = '20240201'
INITIAL_CASH = 100000.0
STAKE_PERCENT = 0.95  # 交易仓位百分比

# MACD策略参数
class MACDParams:
    maperiod = 15
    fastperiod = 12
    slowperiod = 26
    signalperiod = 9
