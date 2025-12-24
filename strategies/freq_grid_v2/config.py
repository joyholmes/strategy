"""
Freq Grid Strategy V2 - 配置文件

优化点：
1. 更清晰的参数分类
2. 支持多种触发模式
3. 区域转换阈值可配置
"""

class StrategyConfig:
    """策略核心参数配置"""
    
    # ========== 资金与账户 ==========
    total_initial_cash = 1_000_000  # 初始账户资金
    
    # ========== 核心策略参数 ==========
    # Ao: 初始建仓基准价 (首次买入时的价格)
    # Af: 预期最低价 (金字塔底部，基于历史最大回撤估算)
    # Bo: 初始仓位金额 (首次建仓投入)
    # Bf: 规划最大投资金额 (资金使用上限)
    
    Ao = 35.30       # 初始基准价 (如沪深300约3530点)
    Af = 25.00       # 预期最低价 (如沪深300约2500点, 最大回撤约30%)
    Bo = 200_000     # 初始仓位 20万 (20%)
    Bf = 800_000     # 最大投资 80万 (80%)
    
    # ========== 触发阈值设置 ==========
    threshold_mode = 'fixed'  # 'fixed' 或 'dynamic'
    fixed_threshold = 0.04    # 固定阈值 4%
    
    # 动态阈值参数 (ATR based)
    atr_period = 20
    atr_multiplier = 1.0
    dynamic_min = 0.02
    dynamic_max = 0.08
    
    # ========== 区域转换阈值 ==========
    # 区域边界收益率
    zone_b_entry = -0.30     # 进入区域B: i < -30%
    zone_c_entry = -0.30     # 进入区域C: i >= -30%
    zone_c_exit = -0.005     # 离开区域C: i >= -0.5%
    zone_d_entry = 0.005     # 进入区域D: i >= 0.5%
    zone_d_exit = -0.005     # 离开区域D: i < -0.5%
    
    # 资金回收阈值
    zone_e_entry_ratio = 0.15  # 进入区域E: 累计减仓 > 15% * Ba
    zone_f_entry_ratio = 0.99  # 进入区域F: 累计减仓 >= 99% * Ba
    
    # ========== 状态转换缓冲 ==========
    buffer_days = 1  # 区域转换需维持的周期数
    
    # ========== 区域操作参数 ==========
    # 区域A减仓比例
    zone_a_sell_ratio = 0.02  # 每次减仓2%
    
    # 区域C阶梯减仓比例 (第1次, 第2次, 第3次及以后)
    zone_c_sell_ratios = [0.005, 0.010, 0.020]
    zone_c_buy_ratio = 0.005  # 加仓比例

    # 区域D阶梯减仓比例
    zone_d_sell_ratios = [0.010, 0.015, 0.020]
    zone_d_buy_ratio = 0.010

    # 区域E阶梯减仓比例
    zone_e_sell_ratios = [0.020, 0.040, 0.060]
    zone_e_buy_ratio = 0.010
    zone_e_buy_threshold_multiplier = 2.5  # 区域E加仓阈值 = 基础阈值 * 2.5
    
    # 区域F操作参数
    zone_f_threshold = 0.03   # 区域F触发阈值 3%
    zone_f_trade_ratio = 0.01 # 每次买卖1%
    
    # ========== 区域F重建仓增强模块 ==========
    enable_reentry = False           # 是否启用重新建仓
    reentry_min_profit_ratio = 1.0   # 启动监测: 累计减仓 >= 100% * Ba
    reentry_min_position_ratio = 0.5 # 启动监测: 当前市值 >= 50% * Ba
    reentry_callback_warn = 0.20     # 预警层级: 回调20%
    reentry_callback_suggest = 0.30  # 建议层级: 回调30%
    reentry_callback_strong = 0.40   # 强烈建议: 回调40%
    reentry_cooldown_days = 30       # 冷却期
    reentry_max_times = 2            # 最大重建仓次数
    
    # ========== 回测配置 ==========
    stock_code = "000300.SH"     # 标的代码
    start_date = "20150101"
    end_date = "20251201"
    
    # 交易成本
    commission = 0.0003          # 佣金 0.03%
    slippage = 0.0               # 滑点 (可选)
    min_trade_unit = 100         # 最小交易单位 (股)


class ReportConfig:
    """报告输出配置"""
    save_details = True          # 保存每日明细
    save_operations = True       # 保存操作记录
    generate_plot = True         # 生成可视化图表
    
    # 预警阈值
    yield_warn_levels = [-0.20, -0.30, -0.40]  # 收益率预警
    bf_usage_warn_levels = [0.50, 0.70, 0.90]  # 资金使用预警
