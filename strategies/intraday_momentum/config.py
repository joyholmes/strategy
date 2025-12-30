
# 策略参数配置

class Config:
    # --- 时间设置 ---
    TIME_AUCTION_CHECK = "09:24:59"
    TIME_MARKET_OPEN_CHECK = "09:35:01"
    TIME_MARKET_CLOSE = "15:00:00"
    
    # --- 买入阈值 ---
    BUY_VOLUME_RATIO_THRESHOLD = 2.5       # 量比 > 2.5
    BUY_MAX_DROP_FROM_PRE_CLOSE = -0.01    # 最低价跌幅 >= -1% (即跌幅小于1%)
    BUY_MAX_RISE_FROM_LOW = 0.02           # 现价相对最低价涨幅 <= 2%
    
    # --- 卖出阈值 ---
    SELL_AUCTION_DROP_THRESHOLD = -0.02    # 集合竞价跌幅 <= -2%
    SELL_BELOW_VWAP_MINUTES = 5            # 跌破均线持续分钟数
    
    # --- 资金管理 ---
    TOTAL_CAPITAL = 200000.0               # 模拟总资金
    SINGLE_STOCK_MAX_CAPITAL = 50000.0     # 单只个股最大买入金额
    MULTI_STOCK_THRESHOLD_CAPITAL = 50000.0 # 资金大于此值时按涨幅排序分批买入

    # --- 系统设置 ---
    DATA_POLL_INTERVAL = 3                 # 数据轮询间隔(秒)
    
    # --- 日志设置 ---
    LOG_DIR = "logs"
    LOG_FILE_PREFIX = "intraday_momentum"
