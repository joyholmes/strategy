# 全局配置文件
# 包含所有策略共享的配置

# Tushare Token
TUSHARE_TOKEN = '36c643f995ba9828b822f1872dda95372f89787eb912dad38c3b0375'

# 数据源配置
DATA_SOURCE = 'baostock'  # 'tushare' or 'akshare' or 'baostock'

# 通用回测配置
ENABLE_BENCHMARK = True  # 是否启用基准对比
COMMISSION = 0.00005  # 手续费率

# 常用股票代码
STOCK_CODES = {
    '沪深300': '000300.SH',
    '上证指数': '000001.SH',
    '深证成指': '399001.SZ',
}

# 常用时间周期
PERIODS = {
    '长周期': ('20210101', '20251201'),
    '熊市': ('20230201', '20240201'),
    '牛市': ('20241101', '20251201'),
    '震荡市': ('20210101', '20220101'),
}
