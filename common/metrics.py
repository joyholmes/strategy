"""
通用投资指标计算模块
包含IRR、夏普比率等专业投资指标的计算
"""
import numpy as np


def calculate_irr(cash_flows_with_dates, final_value, final_date):
    """
    计算IRR（内部收益率）
    
    参数:
        cash_flows_with_dates: [(日期, 现金流), ...] 负数表示流出（投资），正数表示流入（收回）
        final_value: 期末市值
        final_date: 期末日期
    
    返回:
        年化IRR（百分比）
    """
    if not cash_flows_with_dates:
        return 0.0
    
    # 添加期末现金流（卖出所有持仓）
    all_cash_flows = cash_flows_with_dates + [(final_date, final_value)]
    
    # 按日期排序
    all_cash_flows.sort(key=lambda x: x[0])
    
    # 提取日期和现金流
    dates = [cf[0] for cf in all_cash_flows]
    flows = [cf[1] for cf in all_cash_flows]
    
    # 计算以天为单位的时间间隔
    start_date = dates[0]
    days_from_start = [(d - start_date).days for d in dates]
    
    # 使用牛顿法求解IRR
    # NPV = sum(cash_flow / (1 + r)^t) = 0
    def npv(rate, cash_flows, days):
        return sum(cf / (1 + rate) ** (day / 365.0) for cf, day in zip(cash_flows, days))
    
    # 牛顿法迭代
    rate = 0.1  # 初始猜测10%
    tolerance = 1e-6
    max_iterations = 100
    
    for _ in range(max_iterations):
        npv_value = npv(rate, flows, days_from_start)
        if abs(npv_value) < tolerance:
            break
        
        # 计算导数
        dnpv = sum(-cf * (day / 365.0) / (1 + rate) ** (day / 365.0 + 1) 
                   for cf, day in zip(flows, days_from_start))
        
        if abs(dnpv) < 1e-10:
            break
            
        rate = rate - npv_value / dnpv
    
    return rate * 100  # 转换为百分比


def calculate_sharpe_ratio(returns, risk_free_rate=0.03):
    """
    计算夏普比率
    
    参数:
        returns: 收益率序列
        risk_free_rate: 无风险利率（年化）
    
    返回:
        夏普比率
    """
    if len(returns) == 0:
        return 0.0
    
    excess_returns = returns - risk_free_rate / 252  # 假设252个交易日
    return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)


def calculate_max_drawdown(values):
    """
    计算最大回撤
    
    参数:
        values: 市值序列
    
    返回:
        最大回撤（百分比）
    """
    if len(values) == 0:
        return 0.0
    
    peak = values[0]
    max_dd = 0.0
    
    for value in values:
        if value > peak:
            peak = value
        dd = (peak - value) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    
    return max_dd * 100


def calculate_calmar_ratio(annual_return, max_drawdown):
    """
    计算卡玛比率
    
    参数:
        annual_return: 年化收益率
        max_drawdown: 最大回撤
    
    返回:
        卡玛比率
    """
    if max_drawdown == 0:
        return 0.0
    return annual_return / max_drawdown
