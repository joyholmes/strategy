import akshare as ak
import pandas as pd
import time
from strategies.intraday_momentum.config import Config

class DataProvider:
    @staticmethod
    def get_realtime_quotes():
        """
        获取全市场实时行情快照，并计算策略所需衍生字段。
        """
        try:
            # 获取实时数据
            df = ak.stock_zh_a_spot_em()
            
            # 为了方便处理，重命名关键字段
            # 注意：AkShare字段名可能会变动，这里基于典型返回值映射
            # 常见列名: 序号, 代码, 名称, 最新价, 涨跌幅, 涨跌额, 成交量, 成交额, 振幅, 最高, 最低, 今开, 昨收, 量比, 换手率, 市盈率-动态, 市净率
            rename_map = {
                '代码': 'symbol',
                '名称': 'name',
                '最新价': 'current_price',
                '今开': 'open_price',
                '最高': 'high_price',
                '最低': 'low_price',
                '昨收': 'pre_close',
                '成交量': 'volume',
                '成交额': 'amount',
                '量比': 'volume_ratio',
                '涨跌幅': 'pct_chg'
            }
            
            # 检查列是否存在，避免报错
            existing_cols = [c for c in rename_map.keys() if c in df.columns]
            df = df[existing_cols].copy()
            df.rename(columns=rename_map, inplace=True)
            
            # 数据清洗：剔除无效数据
            df = df.dropna(subset=['current_price', 'open_price', 'pre_close'])
            # 剔除停牌或无交易数据 (成交量=0 or 最新价='-')
            df = df[df['volume'] > 0]
            
            # 类型转换
            numeric_cols = ['current_price', 'open_price', 'high_price', 'low_price', 'pre_close', 'volume', 'amount', 'volume_ratio']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # --- 衍生指标计算 ---
            
            # 1. 计算 VWAP (分时均价) = 成交额 / 成交量
            # 注意：成交额单位通常是元，成交量单位通常是手(100股)，AkShare返回的单位需确认
            # stock_zh_a_spot_em: 成交额为元，成交量为手。因此 vwap = amount / (volume * 100)
            if 'amount' in df.columns and 'volume' in df.columns:
                df['vwap'] = df['amount'] / (df['volume'] * 100)
            
            # 2. 最低价跌幅 (Low / PreClose - 1)
            df['low_drop_pct'] = (df['low_price'] - df['pre_close']) / df['pre_close']
            
            # 3. 现价相对最低价涨幅 ((Current - Low) / Low)
            df['rise_from_low_pct'] = (df['current_price'] - df['low_price']) / df['low_price']
            
            # 4. 集合竞价跌幅 (用于早盘检查，Open / PreClose - 1)
            # 在9:25-9:30之间，LatestPrice通常等于OpenPrice
            df['auction_drop_pct'] = (df['open_price'] - df['pre_close']) / df['pre_close']

            return df
            
        except Exception as e:
            print(f"[Error] 获取行情数据失败: {e}")
            return pd.DataFrame()

if __name__ == "__main__":
    # Test
    print("Fetching data...")
    df = DataProvider.get_realtime_quotes()
    if not df.empty:
        print(f"Got {len(df)} rows.")
        print(df[['symbol', 'name', 'current_price', 'vwap', 'volume_ratio']].head())
    else:
        print("Empty dataframe.")
