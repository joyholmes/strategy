# 仓位管理策略配置

# 回测设置
STOCK_CODE = '000300.SH'
START_DATE = '20210101'
END_DATE = '20251201'
INITIAL_CASH = 100000.0

# 从全局配置导入
from config.global_config import COMMISSION, ENABLE_BENCHMARK

# 仓位管理策略参数
class PositionManagementParams:
    # 总初始资金
    total_initial_cash = 100000.0
    
    # GDP年化增长率
    gdp_rate = 0.07
    
    # 周期配置
    # 每个周期包含: id(周期编号), ratio(仓位比例), vix_threshold(波动率阈值)
    cycles = [
        {
            'id': 'Cycle_1',
            'ratio': 0.10,
            'initial_cash': 100000.0 * 0.10,  # 10,000
            'vix_threshold': 0.02  # 2%
        },
        {
            'id': 'Cycle_2',
            'ratio': 0.20,
            'initial_cash': 100000.0 * 0.20,  # 20,000
            'vix_threshold': 0.04  # 4%
        },
        {
            'id': 'Cycle_3',
            'ratio': 0.30,
            'initial_cash': 100000.0 * 0.30,  # 30,000
            'vix_threshold': 0.08  # 8%
        },
        {
            'id': 'Cycle_4',
            'ratio': 0.40,
            'initial_cash': 100000.0 * 0.40,  # 40,000
            'vix_threshold': 0.16  # 16%
        },
    ]
