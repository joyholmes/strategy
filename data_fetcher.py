import tushare as ts
import akshare as ak
import pandas as pd
from datetime import datetime
from config import TUSHARE_TOKEN, DATA_SOURCE
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
    return df

def fetch_data(stock_code, start_date, end_date):
    """
    Fetch stock data from the selected data source in config.
    """
    if DATA_SOURCE == 'tushare':
        df = _fetch_from_tushare(stock_code, start_date, end_date)
    elif DATA_SOURCE == 'akshare':
        df = _fetch_from_akshare(stock_code, start_date, end_date)
    else:
        raise ValueError(f"Unsupported data source: {DATA_SOURCE}. Please choose 'tushare' or 'akshare' in config.py.")

    # Prepare data for backtrader
    df['openinterest'] = 0
    return pd.DataFrame(df, columns=['open', 'high', 'low', 'close', 'volume', 'openinterest'])

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
