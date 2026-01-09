from datetime import datetime, timedelta
import pandas as pd
from strategies.intraday_momentum.config import Config

class TradeManager:
    def __init__(self, initial_capital=Config.TOTAL_CAPITAL):
        self.total_capital = initial_capital
        self.available_capital = initial_capital
        
        # 持仓清单: { symbol: { 'avg_cost': float, 'volume': int, 'name': str, 'break_vwap_time': datetime } }
        self.positions = {} 
        
        # 存量持仓将在 load_sell_watch_positions 中加载（需要行情数据）
        self._sell_watch_symbols = getattr(Config, 'SELL_WATCH_SYMBOLS', [])
        
        # 卖出信号计时器 (跌破均线时间)
        # 结构: { symbol: first_break_timestamp }
        # 注意：为了逻辑解耦，我们将计时器放在 Position 结构里维护，或者单独维护。
        # 这里选择放在 positions 字典内部维护，方便管理
    
    def load_sell_watch_positions(self, market_data_df):
        """
        根据 SELL_WATCH_SYMBOLS 列表，从行情数据中获取昨收价和名称，初始化卖出监控持仓
        """
        if not self._sell_watch_symbols:
            return
            
        yesterday = datetime.now().date() - timedelta(days=1)
        loaded_count = 0
        
        for symbol in self._sell_watch_symbols:
            if symbol in self.positions:
                continue  # 已经加载过
                
            # 从行情数据中查找该股票
            stock_row = market_data_df[market_data_df['symbol'] == symbol]
            if stock_row.empty:
                print(f"[WARN] 卖出监控股票 {symbol} 未找到行情数据，跳过")
                continue
            
            row = stock_row.iloc[0]
            pre_close = row.get('pre_close', 0.0)
            name = row.get('name', symbol)
            
            self.positions[symbol] = {
                'avg_cost': pre_close,  # 使用昨收价作为成本
                'volume': 100,          # 默认100股，仅用于监控，不影响卖出逻辑
                'name': name,
                'break_vwap_time': None,
                'buy_date': yesterday   # 设为昨天，确保可卖 (T+1)
            }
            loaded_count += 1
            print(f"[INFO] 加载卖出监控: {name}({symbol}), 昨收={pre_close:.2f}")
        
        if loaded_count > 0:
            print(f"[INFO] 共加载 {loaded_count} 只卖出监控股票")
        
    def execute_buy(self, symbol, name, price, money_to_spend):
        """
        模拟买入执行
        """
        if money_to_spend > self.available_capital:
            # print(f"资金不足，无法买入 {name}({symbol})")
            return False
            
        # 计算手数 (向下取整到100)
        hands = int(money_to_spend / price / 100)
        if hands == 0:
            return False
            
        volume = hands * 100
        cost = volume * price
        
        self.available_capital -= cost
        
        if symbol not in self.positions:
            self.positions[symbol] = {
                'avg_cost': price,
                'volume': volume,
                'name': name,
                'break_vwap_time': None, # 首次跌破均线时间
                'buy_date': datetime.now().date() # 记录买入日期用于 T+1 检查
            }
        else:
            # 加仓逻辑（简化为更新成本）
            # 注意：如果是加仓，混合了旧仓位和新仓位。为了简化 T+1，这里严格一点：
            # 只要今天有买入，这部分新增的量 T+1 才能卖。
            # 但为了简化模型，假设加仓后更新 buy_date 可能会导致旧仓位也被锁住（保守策略）
            # 或者我们需要分批记录。鉴于本策略主要是单次买入，我们暂更新 buy_date 为最新，严格 T+1。
            old = self.positions[symbol]
            new_cost = (old['avg_cost'] * old['volume'] + cost) / (old['volume'] + volume)
            old['volume'] += volume
            old['avg_cost'] = new_cost
            old['buy_date'] = datetime.now().date() # 加仓部分导致整体锁定（保守风控）
            
        print(f"[BUY] {datetime.now().strftime('%H:%M:%S')} 买入 {name}({symbol}): 价格={price}, 数量={volume}, 金额={cost:.2f}")
        return True

    def execute_sell(self, symbol, price, reason=""):
        """
        模拟卖出执行
        """
        if symbol not in self.positions:
            return False
            
        pos = self.positions[symbol]
        revenue = pos['volume'] * price
        pnl = revenue - (pos['avg_cost'] * pos['volume'])
        
        self.available_capital += revenue
        del self.positions[symbol]
        
        print(f"[SELL] {datetime.now().strftime('%H:%M:%S')} 卖出 {pos['name']}({symbol}): 价格={price}, 盈亏={pnl:.2f}, 原因={reason}")
        return True

    def get_account_summary(self, current_prices):
        """
        计算账户当前状态
        current_prices: dict, {symbol: current_price}
        Returns: dict
        """
        market_value = 0.0
        details = []
        today = datetime.now().date()
        
        for symbol, pos in self.positions.items():
            curr_price = current_prices.get(symbol, pos['avg_cost']) # 如果取不到现价，暂按成本价算
            mv = pos['volume'] * curr_price
            market_value += mv
            
            # 单个持仓盈亏
            profit = (curr_price - pos['avg_cost']) * pos['volume']
            profit_pct = (curr_price - pos['avg_cost']) / pos['avg_cost']
            
            # 可卖状态
            is_collectible = (pos['buy_date'] < today)
            status_desc = "T+1锁定" if not is_collectible else "可卖"
            
            details.append({
                'symbol': symbol,
                'name': pos['name'],
                'volume': pos['volume'],
                'avg_cost': pos['avg_cost'],
                'current_price': curr_price,
                'profit': profit,
                'profit_pct': profit_pct,
                'break_vwap_time': pos.get('break_vwap_time'),
                'status_desc': status_desc
            })
            
        total_assets = self.available_capital + market_value
        total_pnl = total_assets - self.total_capital
        total_pnl_pct = total_pnl / self.total_capital
        
        return {
            'total_assets': total_assets,
            'available_capital': self.available_capital,
            'market_value': market_value,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'positions': details
        }

class StrategyEngine:
    def __init__(self, trade_manager):
        self.tm = trade_manager

    def check_and_execute_buy(self, market_data_df):
        """
        检查买入条件并执行
        """
        if market_data_df.empty:
            return

        # 1. 基础筛选条件 (Vectorized)
        candidates = market_data_df[
            (market_data_df['volume_ratio'] > Config.BUY_VOLUME_RATIO_THRESHOLD) &
            (market_data_df['current_price'] > market_data_df['open_price']) &
            (market_data_df['current_price'] > market_data_df['vwap']) &
            (market_data_df['low_drop_pct'] >= Config.BUY_MAX_DROP_FROM_PRE_CLOSE) &
            (market_data_df['rise_from_low_pct'] <= Config.BUY_MAX_RISE_FROM_LOW)
        ].copy()
        
        if candidates.empty:
            return

        # 排除已持仓的股票
        holding_symbols = set(self.tm.positions.keys())
        candidates = candidates[~candidates['symbol'].isin(holding_symbols)]
        
        if candidates.empty:
            return

        # 2. 多股选择逻辑
        # 按当前涨幅 (pct_chg) 由高到低排序
        candidates = candidates.sort_values(by='pct_chg', ascending=False)
        
        # 3. 资金分配逻辑
        # 若有 2 只或以上股票符合条件...
        num_candidates = len(candidates)
        
        for idx, row in candidates.iterrows():
            symbol = row['symbol']
            price = row['current_price']
            
            # 检查是否有可用资金
            if self.tm.available_capital < 1000: # 至少够点零钱
                break
                
            # 资金分配计算
            # 规则：若资金 > 5万，按照涨幅由高到低顺序买入。
            # 隐含：如果资金不足5万，可能只能买一只。
            # 这里的逻辑解释为：如果是多个标的，我们循环尝试买入，每只上限5万。
            
            money_to_alloc = min(Config.SINGLE_STOCK_MAX_CAPITAL, self.tm.available_capital)
            
            # 如果是"若有2只以上...选择涨幅最大的"
            # 其实排序后，第一个就是涨幅最大的。
            # 简单的贪心策略：loop through sorted candidates and buy.
            
            self.tm.execute_buy(symbol, row['name'], price, money_to_alloc)


    def check_and_execute_sell(self, market_data_df, is_auction_time=False):
        """
        检查卖出条件并执行
        """
        if not self.tm.positions:
            return

        # 获取持仓股票的最新数据
        holding_symbols = list(self.tm.positions.keys())
        current_data = market_data_df[market_data_df['symbol'].isin(holding_symbols)]
        
        today = datetime.now().date()
        
        for idx, row in current_data.iterrows():
            symbol = row['symbol']
            price = row['current_price']
            open_price = row['open_price']
            vwap = row['vwap']
            pre_close = row['pre_close']
            
            pos = self.tm.positions[symbol]
            
            # --- 0. T+1 检查 ---
            # 如果是今天买入的，禁止卖出
            if pos['buy_date'] >= today:
                continue
            
            # --- 场景1: 9:24:59 集合竞价卖出 ---
            if is_auction_time:
                # 集合竞价跌幅 >= 2% (即 drop <= -0.02)
                # 使用 open_price 近似集合竞价价格
                auction_drop = (open_price - pre_close) / pre_close
                if auction_drop <= Config.SELL_AUCTION_DROP_THRESHOLD:
                    self.tm.execute_sell(symbol, price, reason=f"集合竞价大跌 {auction_drop*100:.2f}%")
                continue # 竞价只检查这一个条件
            
            # --- 场景2: 9:35:01 后盘中卖出 ---
            
            # 条件1: 跌破开盘价
            if price < open_price:
                self.tm.execute_sell(symbol, price, reason="跌破开盘价")
                continue
                
            # 条件2: 跌破分时均线5分钟
            if price < vwap:
                if pos['break_vwap_time'] is None:
                    # 首次跌破，记录时间
                    pos['break_vwap_time'] = datetime.now()
                    # print(f"DEBUG: {symbol} 跌破均线，开始计时")
                else:
                    # 已经跌破，检查时长
                    duration = datetime.now() - pos['break_vwap_time']
                    if duration.total_seconds() >= Config.SELL_BELOW_VWAP_MINUTES * 60:
                        self.tm.execute_sell(symbol, price, reason=f"跌破均线超过{Config.SELL_BELOW_VWAP_MINUTES}分钟")
            else:
                # 价格在均线之上，重置计时器
                if pos['break_vwap_time'] is not None:
                    pos['break_vwap_time'] = None
                    # print(f"DEBUG: {symbol} 重回均线，计时重置")

