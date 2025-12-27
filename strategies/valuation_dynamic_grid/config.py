# strategies/valuation_pyramid/config.py
from config import global_config

# 标的代码
STOCK_CODE = '000300.SH' # 沪深300

# 回测时间
START_DATE = '20210101'
END_DATE = '20251218'

# 策略参数
class ValuationParams:
    # 投资总额
    total_initial_cash = 100000.0
    
    # 指标类型: 'pe' (市盈率) 或 'pb' (市净率)
    metric = 'pe'  # 宽基指数建议看PE
    
    # 历史数据回溯年限 (仅当不使用固定参考区间时生效)
    lookback_years = 10
    
    # === 仓位映射配置 (核心修改) ===
    # 为了实现"低位吸筹后死拿，直到高位才卖"，我们采用非线性凸函数映射
    # Target = 1 - (Normalized_Percentile) ^ k
    # k 越大，中间区域持仓越重 (滞后卖出)
    
    # 凸性持仓强度 (Convex Hold Strength)
    # k=1: 线性 (50%分位时50%仓位)
    # k=3: 强持有 (50%分位时87%仓位，80%分位时才降到50%仓位)
    convex_hold_k = 3.0
    
    # 依然保留极端截断
    full_pos_quantile = 0.1   # 低于此分位强制 100%
    empty_pos_quantile = 0.9  # 高于此分位强制 0%
    
    # 中间区域 (0.2 ~ 0.8) 线性过渡
    
    # 动态非对称网格参数
    # 如果开启，策略将使用这段固定时间的估值分布来计算分位点，而不是滚动回溯
    use_fixed_reference = False
    reference_start_date = '20160101'
    reference_end_date = '20210101'
    
    # === 金字塔双线逻辑参数 ===
    
    # === 动态非对称网格参数 ===
    # 最小阈值：在最有利位置时的网格密度 (如极低估时买入敏感度)
    min_threshold = 0.04  # 1%
    # 最大阈值：在最不利位置时的网格密度 (如极低估时卖出敏感度)
    max_threshold = 0.16  # 8%
    
    # 无需定义 buy_tiers 和 sell_tiers，逻辑由线性公式 + 动态阈值接管
    
    # 中间地带 (30% ~ 70%):
    # 既不触发买入规则(min_target=0)，也不触发卖出规则(max_target=1.0)
    # 逻辑结果 -> 维持当前仓位不动（Hold）

# 引入全局配置
if global_config.DATA_SOURCE != 'akshare':
    print("警告: 建议将全局 DATA_SOURCE 设置为 'akshare' 以获取更准确的指数估值数据")
