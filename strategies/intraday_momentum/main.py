import time
from datetime import datetime
import pandas as pd
import sys
import os
import logging

# 将项目根目录添加到 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from strategies.intraday_momentum.config import Config
from strategies.intraday_momentum.data_provider import DataProvider
from strategies.intraday_momentum.strategy import StrategyEngine, TradeManager

def setup_logging():
    if not os.path.exists(Config.LOG_DIR):
        os.makedirs(Config.LOG_DIR)
        
    date_str = datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(Config.LOG_DIR, f"{Config.LOG_FILE_PREFIX}_{date_str}.log")
    
    # 同时输出到文件和控制台
    # 如果已经有handler则不重复添加
    logger = logging.getLogger()
    if not logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
    return log_file

def is_after_time(time_str):
    now = datetime.now().time()
    target = datetime.strptime(time_str, "%H:%M:%S").time()
    return now >= target

def print_summary(trade_manager, market_data_df):
    """
    打印账户详细摘要
    """
    # 提取当前价格字典
    current_prices = {}
    if not market_data_df.empty:
        # 假设 df 包含所有持仓股票的最新数据（如果全市场获取的话通常包含）
        # 即使只获取了部分，也能更新部分
        for idx, row in market_data_df.iterrows():
            current_prices[row['symbol']] = row['current_price']
            
    summary = trade_manager.get_account_summary(current_prices)
    
    logging.info("-" * 60)
    logging.info(f"【账户统计】 总资产: {summary['total_assets']:.2f} | 初始: {trade_manager.total_capital:.0f}")
    
    pnl_symbol = "+" if summary['total_pnl'] >= 0 else ""
    logging.info(f"           总盈亏: {pnl_symbol}{summary['total_pnl']:.2f} ({pnl_symbol}{summary['total_pnl_pct']*100:.2f}%)")
    logging.info(f"           市值: {summary['market_value']:.2f} | 现金: {summary['available_capital']:.2f}")
    
    if summary['positions']:
        logging.info("【持仓详情】")
        logging.info(f"{'代码':<8} {'名称':<8} {'数量':<6} {'现价':<8} {'成本':<8} {'盈亏%':<8} {'盈亏额':<8} {'状态'}")
        logging.info("-" * 60)
        for p in summary['positions']:
            status_text = ""
            if p['break_vwap_time']:
                duration = datetime.now() - p['break_vwap_time']
                status_text = f"⚠ 破位{int(duration.total_seconds()/60)}分"
            elif p['profit_pct'] < -0.05:
                status_text = "⚠ 亏损警戒"
            
            # 拼接状态描述
            full_status = f"[{p.get('status_desc', '')}] {status_text}"
                
            p_pnl_sym = "+" if p['profit'] >= 0 else ""
            logging.info(f"{p['symbol']:<8} {p['name']:<8} {p['volume']:<6} {p['current_price']:<8.2f} {p['avg_cost']:<8.2f} {p_pnl_sym}{p['profit_pct']*100:>6.2f}% {p_pnl_sym}{p['profit']:>8.2f} {full_status}")
    else:
        logging.info("【持仓详情】 无持仓")
    logging.info("-" * 60)

def main():
    log_file = setup_logging()
    logging.info("=== 日内动量突破策略 (Intraday Momentum) 启动 ===")
    logging.info(f"日志文件: {log_file}")
    logging.info(f"配置: 总资金={Config.TOTAL_CAPITAL}, 量比阈值={Config.BUY_VOLUME_RATIO_THRESHOLD}")
    
    trade_manager = TradeManager()
    engine = StrategyEngine(trade_manager)
    
    has_checked_auction = False
    last_summary_time = 0
    SUMMARY_INTERVAL = 30 # 每30秒打印一次详细统计，避免刷屏
    
    try:
        while True:
            now_str = datetime.now().strftime("%H:%M:%S")
            
            # --- 1. 集合竞价检查 ---
            if not has_checked_auction and "09:24:50" <= now_str <= "09:25:05":
                logging.info(f"[{now_str}] 执行集合竞价卖出检查...")
                df = DataProvider.get_realtime_quotes()
                if not df.empty:
                    engine.check_and_execute_sell(df, is_auction_time=True)
                has_checked_auction = True
            
            # --- 2. 盘中运行 ---
            if is_after_time(Config.TIME_MARKET_OPEN_CHECK) and not is_after_time(Config.TIME_MARKET_CLOSE):
                start_time = time.time()
                
                df = DataProvider.get_realtime_quotes()
                
                if not df.empty:
                    # 交易逻辑
                    engine.check_and_execute_sell(df, is_auction_time=False)
                    engine.check_and_execute_buy(df)
                    
                    # 统计输出控制 (每30秒一次)
                    if time.time() - last_summary_time >= SUMMARY_INTERVAL:
                        print_summary(trade_manager, df)
                        last_summary_time = time.time()
                        
                        # 简略的心跳日志
                        logging.info(f"[{now_str}] 运行中... 持仓数: {len(trade_manager.positions)}")
                
                elapsed = time.time() - start_time
                sleep_time = max(0, Config.DATA_POLL_INTERVAL - elapsed)
                time.sleep(sleep_time)
                
            else:
                if is_after_time(Config.TIME_MARKET_CLOSE):
                    logging.info("今日交易结束。")
                    # 打印最终统计
                    df = DataProvider.get_realtime_quotes()
                    print_summary(trade_manager, df)
                    break
                
                # 等待开盘
                print(f"[{now_str}] 等待开盘中 (将在 {Config.TIME_MARKET_OPEN_CHECK} 启动)...", end='\r')
                time.sleep(1)

    except KeyboardInterrupt:
        logging.info("\n策略已停止。")

if __name__ == "__main__":
    main()
