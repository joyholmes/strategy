# strategies/valuation_pyramid/config.py
from config import global_config

# 标的代码
STOCK_CODE = '600036.SH' # 招商银行

# 回测时间
START_DATE = '20150101'
END_DATE = '20251201'

# 策略参数
class ValuationParams:
    # 投资总额
    total_initial_cash = 100000.0
    
    # 指标类型: 'pe' (市盈率) 或 'pb' (市净率)
    metric = 'pb'  # 银行必须看PB
    
    # 历史数据回溯年限 (仅当不使用固定参考区间时生效)
    lookback_years = 10
    
    # === 历史分位点参考系 (New) ===
    # 如果开启，策略将使用这段固定时间的估值分布来计算分位点，而不是滚动回溯
    use_fixed_reference = False
    reference_start_date = '20160101'
    reference_end_date = '20210101'
    
    # === 金字塔双线逻辑参数 ===
    
    # 买入阶梯 (Pyramid Buy Tiers)
    # 银行估值极低，要在“地板下的地板”买入
    buy_tiers = [
        (0.20, 0.3),  # 20%分位：才开始考虑
        (0.10, 0.6),  # 10%分位：加仓
        (0.05, 0.9),  # 5%分位：重仓
        (0.01, 1.0),  # 1%分位：满仓 (几乎就是净资产打折到底了)
    ]
    
    # 卖出阶梯 (Pyramid Sell Tiers)
    # 银行估值很难回到高位，只要回到中枢(50%)就可以开始兑现
    sell_tiers = [
        (0.50, 0.5),  # 50%分位：对于银行来说已经是“高估”了
        (0.70, 0.1),  # 70%分位：几乎可以清仓
        (0.80, 0.0),  # 80%分位：完全清仓
    ]
    
    # 中间地带 (30% ~ 70%):
    # 既不触发买入规则(min_target=0)，也不触发卖出规则(max_target=1.0)
    # 逻辑结果 -> 维持当前仓位不动（Hold）

# 引入全局配置
if global_config.DATA_SOURCE != 'akshare':
    print("警告: 建议将全局 DATA_SOURCE 设置为 'akshare' 以获取更准确的指数估值数据")
