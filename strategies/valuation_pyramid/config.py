# strategies/valuation_pyramid/config.py
from config import global_config

# 标的代码
STOCK_CODE = '600030.SH' # 中信证券

# 回测时间
START_DATE = '20150101'
END_DATE = '20251201'

# 策略参数
class ValuationParams:
    # 投资总额
    total_initial_cash = 100000.0
    
    # 指标类型: 'pe' (市盈率) 或 'pb' (市净率)
    # 券商股必须用 PB，用 PE 会失效
    metric = 'pb'
    
    # 历史数据回溯年限 (仅当不使用固定参考区间时生效)
    lookback_years = 5
    
    # === 历史分位点参考系 (New) ===
    # 如果开启，策略将使用这段固定时间的估值分布来计算分位点，而不是滚动回溯
    # 优点: 标准固定，不会随时间推移而“漂移”，可以锁定某段典型牛熊周期作为标尺
    use_fixed_reference = False
    reference_start_date = '20160101' # 参考区间开始
    reference_end_date = '20210101'   # 参考区间结束

    
    # === 金字塔双线逻辑参数 ===
    
    # 买入阶梯 (Pyramid Buy Tiers)
    # 逻辑: 当 分位点 < limit 时，确保仓位至少达到 target
    # 意图: 越跌越买，构建安全底仓
    buy_tiers = [
        (0.30, 0.3),  # 把门线：分位点降到30%以下，至少建仓30%
        (0.20, 0.7),  # 主力线：分位点降到20%以下，至少加仓到70%
        (0.15, 1.0),  # 搏杀线：分位点降到15%以下，满仓
    ]
    
    # 卖出阶梯 (Pyramid Sell Tiers)
    # 逻辑: 当 分位点 > limit 时，强制仓位降低到 target
    # 意图: 越涨越卖，分批止盈
    sell_tiers = [
        (0.70, 0.7),  # 警戒线：分位点升破70%，仓位强制降到70%
        (0.80, 0.3),  # 清仓线：分位点升破80%，仓位强制降到30%
        (0.90, 0.1),  # 清仓线：分位点升破90%，仓位强制降到10%
        (0.95, 0.0),  # 清仓线：分位点升破95%，仓位强制降到0%
    ]
    
    # 中间地带 (30% ~ 70%):
    # 既不触发买入规则(min_target=0)，也不触发卖出规则(max_target=1.0)
    # 逻辑结果 -> 维持当前仓位不动（Hold）

# 引入全局配置
if global_config.DATA_SOURCE != 'akshare':
    print("警告: 建议将全局 DATA_SOURCE 设置为 'akshare' 以获取更准确的指数估值数据")
