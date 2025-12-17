# 网格交易策略配置

# 回测设置
STOCK_CODE = '000300.SH'
START_DATE = '20210101'
END_DATE = '20251201'
INITIAL_CASH = 100000.0

# 从全局配置导入
from config.global_config import COMMISSION, ENABLE_BENCHMARK

# 网格交易策略参数
class GridTradingParams:
    # 总初始资金
    total_initial_cash = 100000.0
    
    # 初始仓位比例（建仓时使用的资金比例）
    initial_position_ratio = 0.5  # 50%初始仓位
    
    # 网格参数
    grid_buy_percent = 0.01   # 下跌1%买入
    grid_sell_percent = 0.01  # 上涨1%卖出
    
    # 每次交易的资金比例
    trade_percent = 0.02  # 每次买入或卖出使用2%的可用资金
    
    # 最大仓位比例
    max_position_ratio = 0.9  # 最多使用90%的资金
    
    # 最小仓位比例
    min_position_ratio = 0.1  # 至少保留10%的仓位
