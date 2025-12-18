# strategies/valuation_extreme/config.py
from config import global_config

# 标的代码 (默认沪深300)
STOCK_CODE = '000300.SH' 

# 回测时间
START_DATE = '20210101'
END_DATE = '20251201'

# 策略参数
class ValuationParams:
    # 投资总额
    total_initial_cash = 100000.0
    
    # 指标类型: 'pe' (市盈率) 或 'pb' (市净率)
    metric = 'pe'
    
    # 历史数据回溯年限 (用于计算百分位)
    lookback_years = 5
    
    # 策略逻辑：极限时机 (Trigger & Hold)
    # 只有当估值极低时买入并持有，极高时卖出，中间不动
    buy_percentile = 0.15   # 15%分位以下满仓买入
    sell_percentile = 0.85  # 85%分位以上清仓卖出

# 引入全局配置
# 确保数据源支持指数估值 (推荐 akshare)
if global_config.DATA_SOURCE != 'akshare':
    print("警告: 建议将全局 DATA_SOURCE 设置为 'akshare' 以获取更准确的指数估值数据")
