from config import global_config

# 默认回测标的
# 注意: Baostock数据源仅提供个股的PE/PB数据，不提供指数估值数据
# 如果回测指数(如000300.SH)，请切换到Tushare或Akshare，或者使用个股代码(如600036.SH)进行测试
STOCK_CODE = '600036.SH' # 招商银行 (示例个股)
START_DATE = '20200101'
END_DATE = '20251201'

class ValuationParams:
    # 总体资金
    total_initial_cash = 100000.0
    
    # 估值类型: 'pe' (市盈率) 或 'pb' (市净率)
    metric = 'pe'
    
    # 历史分位点计算周期 (年)
    lookback_years = 5
    
    # 估值分位点与目标仓位映射表
    # 格式: (分位点上限, 目标仓位)
    # 意味着: 如果 percentile <= 上限, 则 target = 目标仓位
    # 必须从小到大排列
    position_tiers = [
        (0.20, 1.0),  # Top 20%低估 -> 100%仓位
        (0.40, 0.7),  # 20%-40% -> 70%仓位
        (0.60, 0.5),  # 40%-60% -> 50%仓位
        (0.80, 0.2),  # 60%-80% -> 20%仓位
        (1.00, 0.0),  # >80% -> 0%仓位
    ]

# 引入全局配置
COMMISSION = global_config.COMMISSION
ENABLE_BENCHMARK = global_config.ENABLE_BENCHMARK
