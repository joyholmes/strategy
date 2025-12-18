import tushare as ts
import akshare as ak
import baostock as bs
import pandas as pd
from datetime import datetime
from config.global_config import TUSHARE_TOKEN, DATA_SOURCE
import os

def _fetch_from_tushare(stock_code, start_date, end_date):
    """Fetch data from Tushare, trying Index, Fund, and Stock functions."""
    ts.set_token(TUSHARE_TOKEN)
    pro = ts.pro_api()
    df = pd.DataFrame()

    # First, try to fetch as an Index
    try:
        df = pro.index_daily(ts_code=stock_code, start_date=start_date, end_date=end_date)
    except Exception:
        pass # Ignore and proceed

    # If fetching as index fails, try as a Fund/ETF
    if df.empty:
        try:
            df = pro.fund_daily(ts_code=stock_code, start_date=start_date, end_date=end_date)
        except Exception:
            pass  # Ignore permission errors and proceed

    # If all else fails, try as a stock
    if df.empty:
        df = pro.daily(ts_code=stock_code, start_date=start_date, end_date=end_date)

    if df.empty:
        raise ValueError(f"Failed to fetch data from Tushare for code {stock_code}. Please check if the code and date range are correct, and ensure your TUSHARE_TOKEN is valid.")

    df.index = pd.to_datetime(df.trade_date)
    df = df.sort_index()
    df['volume'] = df['vol']
    return df

def _fetch_from_akshare(stock_code, start_date, end_date):
    """Fetch data from Akshare, trying Index, ETF, and Stock functions."""
    # Temporarily disable system proxies to avoid connection errors
    os.environ['HTTP_PROXY'] = ''
    os.environ['HTTPS_PROXY'] = ''

    ak_stock_code = stock_code.split('.')[0]
    start_date_ak = ''.join(start_date.split('-'))
    end_date_ak = ''.join(end_date.split('-'))
    df = pd.DataFrame()

    # First, try to fetch as an Index
    try:
        # Akshare index codes might need 'sh' or 'sz' prefix for some functions, but index_zh_a_hist does not.
        # Let's assume the numeric part is sufficient.
        df = ak.index_zh_a_hist(symbol=ak_stock_code, period="daily", start_date=start_date_ak, end_date=end_date_ak)
    except Exception:
        pass # Ignore and proceed

    # If fetching as index fails, try as an ETF
    if df.empty:
        try:
            df = ak.fund_etf_hist_em(symbol=ak_stock_code, period="daily", start_date=start_date_ak, end_date=end_date_ak, adjust="qfq")
        except Exception:
            pass # Ignore and proceed

    # If all else fails, try as a stock
    if df.empty:
        df = ak.stock_zh_a_hist(symbol=ak_stock_code, period="daily", start_date=start_date_ak, end_date=end_date_ak, adjust="qfq")

    if df.empty:
        raise ValueError(f"Failed to fetch data from Akshare for code {ak_stock_code}. Please check if the stock code and date range are correct.")

    df = df.rename(columns={'日期': 'trade_date', '开盘': 'open', '最高': 'high', '最低': 'low', '收盘': 'close', '成交量': 'volume'})
    df.index = pd.to_datetime(df.trade_date)
    df = df.sort_index()

    # 尝试获取估值数据 (仅针对指数)
    # 乐咕接口需要中文名，这里做简单映射
    index_map = {
        '000300': '沪深300',
        '399006': '创业板指',
        '000905': '中证500',
        '000016': '上证50',
    }
    
    if ak_stock_code in index_map:
        try:
            name = index_map[ak_stock_code]
            
            # 获取PE (滚动市盈率)
            pe_df = ak.stock_index_pe_lg(symbol=name)
            pe_df['trade_date'] = pd.to_datetime(pe_df['日期'])
            pe_df = pe_df.set_index('trade_date')
            
            # 获取PB (市净率)
            pb_df = ak.stock_index_pb_lg(symbol=name)
            pb_df['trade_date'] = pd.to_datetime(pb_df['日期'])
            pb_df = pb_df.set_index('trade_date')
            
            # 合并数据 (利用索引自动对齐)
            # 注意：估值数据可能比K线数据长或短，pandas会自动处理
            if '滚动市盈率' in pe_df.columns:
                df['pe'] = pe_df['滚动市盈率']
            if '市净率' in pb_df.columns:
                df['pb'] = pb_df['市净率']
                
        except Exception as e:
            print(f"Warning: Failed to fetch Akshare valuation data for {name}: {e}")

    return df

def _fetch_from_baostock(stock_code, start_date, end_date):
    """Fetch data from Baostock."""
    lg = bs.login()
    if lg.error_code != '0':
        raise ConnectionError(f"Baostock login failed: {lg.error_msg}")

    # Convert stock code format (e.g., 600030.SH -> sh.600030)
    parts = stock_code.split('.')
    bs_stock_code = f"{parts[1].lower()}.{parts[0]}"
    
    # Format dates
    start_date_bs = datetime.strptime(start_date, '%Y%m%d').strftime('%Y-%m-%d')
    end_date_bs = datetime.strptime(end_date, '%Y%m%d').strftime('%Y-%m-%d')

    # Try to fetch additional valuation metrics
    # Note: Index data in Baostock usually doesn't have peTTM/pbMRQ, will return empty for those fields
    rs = bs.query_history_k_data_plus(
        bs_stock_code,
        "date,open,high,low,close,volume,peTTM,pbMRQ",
        start_date=start_date_bs,
        end_date=end_date_bs,
        frequency="d",
        adjustflag="2"  # qfq: 前复权
    )
    
    if rs.error_code != '0':
        bs.logout()
        raise ValueError(f"Failed to fetch data from Baostock for code {bs_stock_code}: {rs.error_msg}")

    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())
    
    df = pd.DataFrame(data_list, columns=rs.fields)
    bs.logout()

    if df.empty:
        raise ValueError(f"No data returned from Baostock for code {bs_stock_code}.")

    # Convert data types
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Handle PE/PB if they exist (they might be empty strings or zeros)
    if 'peTTM' in df.columns:
        df['pe'] = pd.to_numeric(df['peTTM'], errors='coerce')
    if 'pbMRQ' in df.columns:
        df['pb'] = pd.to_numeric(df['pbMRQ'], errors='coerce')
    
    df.index = pd.to_datetime(df.date)
    df = df.sort_index()
    return df


def fetch_data(stock_code, start_date, end_date):
    """
    Fetch stock data from the selected data source in config.
    """
    if DATA_SOURCE == 'tushare':
        df = _fetch_from_tushare(stock_code, start_date, end_date)
    elif DATA_SOURCE == 'akshare':
        df = _fetch_from_akshare(stock_code, start_date, end_date)
    elif DATA_SOURCE == 'baostock':
        df = _fetch_from_baostock(stock_code, start_date, end_date)
    else:
        raise ValueError(f"Unsupported data source: {DATA_SOURCE}. Please choose 'tushare', 'akshare', or 'baostock' in config.py.")

    # Prepare data for backtrader
    df['openinterest'] = 0
    
    # Ensure pe/pb columns exist, fill with NaN if missing
    if 'pe' not in df.columns:
        df['pe'] = float('nan')
    if 'pb' not in df.columns:
        df['pb'] = float('nan')
        
    return pd.DataFrame(df, columns=['open', 'high', 'low', 'close', 'volume', 'openinterest', 'pe', 'pb'])

if __name__ == '__main__':
    # Example usage
    # Set DATA_SOURCE in config.py to 'akshare' to test this
    if DATA_SOURCE == 'akshare':
        data = fetch_data('000001', '20230101', '20231231')
        print("Fetched from Akshare:")
        print(data.head())
    else:
        data = fetch_data('000001.SZ', '20230101', '20231231')
        print("Fetched from Tushare:")
        print(data.head())
