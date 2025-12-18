# strategies/valuation_pyramid/config.py
from config import global_config

# 标的代码
STOCK_CODE = '000300.SH' 

# 回测时间
START_DATE = '20200101'
END_DATE = '20251201'

# 策略参数
class ValuationParams:
    # 投资总额
    total_initial_cash = 100000.0
    
    # 指标类型: 'pe' (市盈率) 或 'pb' (市净率)
    metric = 'pe'
    
    # 历史数据回溯年限
    lookback_years = 5
    
    # === 金字塔双线逻辑参数 ===
    
    # 买入阶梯 (Pyramid Buy Tiers)
    # 逻辑: 当 分位点 < limit 时，确保仓位至少达到 target
    # 意图: 越跌越买，构建安全底仓
    buy_tiers = [
        (0.30, 0.3),  # 把门线：分位点降到30%以下，至少建仓30%
        (0.20, 0.7),  # 主力线：分位点降到20%以下，至少加仓到70%
        (0.10, 1.0),  # 搏杀线：分位点降到10%以下，满仓
    ]
    
    # 卖出阶梯 (Pyramid Sell Tiers)
    # 逻辑: 当 分位点 > limit 时，强制仓位降低到 target
    # 意图: 越涨越卖，分批止盈
    sell_tiers = [
        (0.70, 0.5),  # 警戒线：分位点升破70%，仓位强制降到50% (锁定一半利润)
        (0.85, 0.0),  # 清仓线：分位点升破85%，清仓 (泡沫离场)
    ]
    
    # 中间地带 (30% ~ 70%):
    # 既不触发买入规则(min_target=0)，也不触发卖出规则(max_target=1.0)
    # 逻辑结果 -> 维持当前仓位不动（Hold）

# 引入全局配置
if global_config.DATA_SOURCE != 'akshare':
    print("警告: 建议将全局 DATA_SOURCE 设置为 'akshare' 以获取更准确的指数估值数据")
