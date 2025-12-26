import time
from datetime import datetime
import pandas as pd
import sys
import os

# 将项目根目录添加到 sys.path，以便可以解析 'strategies' 包
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from strategies.intraday_momentum.config import Config
from strategies.intraday_momentum.data_provider import DataProvider
from strategies.intraday_momentum.strategy import StrategyEngine, TradeManager

def is_time_in_range(start_str, end_str):
    now = datetime.now().time()
    start = datetime.strptime(start_str, "%H:%M:%S").time()
    end = datetime.strptime(end_str, "%H:%M:%S").time()
    return start <= now <= end

def is_after_time(time_str):
    now = datetime.now().time()
    target = datetime.strptime(time_str, "%H:%M:%S").time()
    return now >= target

def main():
    print("=== 日内动量突破策略 (Intraday Momentum) 启动 ===")
    print(f"配置: 总资金={Config.TOTAL_CAPITAL}, 量比阈值={Config.BUY_VOLUME_RATIO_THRESHOLD}")
    
    trade_manager = TradeManager()
    engine = StrategyEngine(trade_manager)
    
    # 状态标记，防止重复触发集合竞价检查
    has_checked_auction = False
    
    try:
        while True:
            now_str = datetime.now().strftime("%H:%M:%S")
            
            # --- 1. 集合竞价检查 (09:24:59) ---
            # 为了容错，我们在 09:24:50 - 09:25:05 之间检测，且只执行一次
            if not has_checked_auction and "09:24:50" <= now_str <= "09:25:05":
                print(f"[{now_str}] 执行集合竞价卖出检查...")
                df = DataProvider.get_realtime_quotes()
                if not df.empty:
                    engine.check_and_execute_sell(df, is_auction_time=True)
                has_checked_auction = True
            
            # --- 2. 盘中运行 (09:35:01 后) ---
            if is_after_time(Config.TIME_MARKET_OPEN_CHECK) and not is_after_time(Config.TIME_MARKET_CLOSE):
                start_time = time.time()
                
                # 获取数据
                df = DataProvider.get_realtime_quotes()
                
                if not df.empty:
                    # 检查卖出 (止损/止盈)
                    engine.check_and_execute_sell(df, is_auction_time=False)
                    
                    # 检查买入
                    engine.check_and_execute_buy(df)
                    
                    # 简单的状态打印
                    if trade_manager.positions:
                        print(f"[{now_str}] 当前持仓: {len(trade_manager.positions)} 只, 可用资金: {trade_manager.available_capital:.2f}")
                
                # 控制轮询频率
                elapsed = time.time() - start_time
                sleep_time = max(0, Config.DATA_POLL_INTERVAL - elapsed)
                time.sleep(sleep_time)
                
            else:
                # 非交易时间，休眠
                if is_after_time(Config.TIME_MARKET_CLOSE):
                    print("今日交易结束。")
                    break
                
                # 还没到时间，小睡一会
                # print(f"[{now_str}] 等待开盘...", end='\r')
                time.sleep(1)

    except KeyboardInterrupt:
        print("\n策略已停止。")

if __name__ == "__main__":
    main()
