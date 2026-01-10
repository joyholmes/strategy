#!/usr/bin/env python3
"""
集思录 LOF 数据爬取脚本
- 支持抓取 stock (股票型) 和 index (指数型) LOF 数据
- 数据可保存到 CSV 或推送到后端 API
"""

import requests
import pandas as pd
import time
import json
from datetime import datetime

# ============ 配置部分 ============
# 后端 API 地址
API_BASE_URL = "http://123.57.105.173:3000/api"

# 请求头 (如需登录态，填入 Cookie)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.jisilu.cn/data/lof/",
    # "Cookie": "kbzw__Session=...; kbzw__user_login=...;"  # 填入您的 Cookie
}

# 数据源 URL
URLS = {
    "stock": "https://www.jisilu.cn/data/lof/stock_lof_list/",
    "index": "https://www.jisilu.cn/data/lof/index_lof_list/",
}


def fetch_jisilu_lof_data(lof_type="stock"):
    """
    爬取集思录 LOF 数据
    :param lof_type: 'stock' (股票LOF) 或 'index' (指数LOF)
    :return: DataFrame or None
    """
    if lof_type not in URLS:
        print(f"❌ 未知类型: {lof_type}")
        return None

    url = URLS[lof_type]
    params = {"___jsl=LST___t": int(time.time() * 1000)}

    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 正在请求 {lof_type} LOF 数据...")
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)

        if response.status_code == 200:
            data = response.json()
            if 'rows' in data:
                rows = [item['cell'] for item in data['rows']]
                df = pd.DataFrame(rows)
                print(f"✅ 获取 {len(df)} 条 {lof_type} 记录")
                return df
            else:
                print(f"❌ 数据格式异常，未找到 'rows' 字段")
                return None
        else:
            print(f"❌ 请求失败: HTTP {response.status_code}")
            return None

    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return None


def safe_float(value, default=None):
    """
    安全转换为 float，处理 '-' 或空值
    """
    if value is None or value == '' or value == '-':
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def transform_to_api_format(df, lof_type):
    """
    将集思录数据转换为后端 API 格式
    :param df: 原始 DataFrame
    :param lof_type: 'stock' 或 'index'
    :return: List[dict]
    """
    records = []
    now = datetime.now().isoformat()

    for _, row in df.iterrows():
        try:
            # 解析溢价率
            premium_rate = safe_float(row.get('discount_rt'), 0)
            
            record = {
                "stockCode": str(row.get('fund_id', '')),
                "fundName": str(row.get('fund_nm', '')),
                "lofType": lof_type,
                "price": safe_float(row.get('price'), 0),
                "netValue": safe_float(row.get('fund_nav'), 0),
                "estimateValue": safe_float(row.get('estimate_value')),
                "premiumRate": premium_rate,
                "volume": safe_float(row.get('volume')),
                "amount": safe_float(row.get('amount')),
                "turnoverRate": safe_float(row.get('turnover_rt')),
                "increaseRate": safe_float(row.get('increase_rt')),
                "indexCode": str(row.get('index_id', '')) if row.get('index_id') and row.get('index_id') != '-' else None,
                "indexName": str(row.get('index_nm', '')) if row.get('index_nm') and row.get('index_nm') != '-' else None,
                "indexIncreaseRate": safe_float(row.get('index_increase_rt')),
                "applyFee": str(row.get('apply_fee', '')) if row.get('apply_fee') and row.get('apply_fee') != '-' else None,
                "applyStatus": str(row.get('apply_status', '')) if row.get('apply_status') and row.get('apply_status') != '-' else None,
                "redeemFee": str(row.get('redeem_fee', '')) if row.get('redeem_fee') and row.get('redeem_fee') != '-' else None,
                "redeemStatus": str(row.get('redeem_status', '')) if row.get('redeem_status') and row.get('redeem_status') != '-' else None,
                "limitAmount": extract_limit_amount(row.get('apply_status', '')),
                "isTractorAllowed": False,  # 需要手动标记
                "issuerName": str(row.get('issuer_nm', '')) if row.get('issuer_nm') and row.get('issuer_nm') != '-' else None,
                "source": "jisilu",
                "dataTime": now,
                "priceTime": str(row.get('last_time', '')) if row.get('last_time') else None,
            }
            records.append(record)
        except Exception as e:
            print(f"⚠️ 转换记录失败 ({row.get('fund_id', 'unknown')}): {e}")
            continue

    return records


def extract_limit_amount(apply_status):
    """
    从申购状态中提取限额信息
    如: "限100" -> "限100", "开放申购" -> None
    """
    if not apply_status:
        return None
    if '限' in str(apply_status):
        return str(apply_status)
    return None


def push_to_api(records, batch_size=100):
    """
    批量推送数据到后端 API
    :param records: 数据列表
    :param batch_size: 每批数量
    """
    if not records:
        print("⚠️ 没有数据需要推送")
        return

    url = f"{API_BASE_URL}/premium-rates/batch"
    headers = {"Content-Type": "application/json"}

    total = len(records)
    success_count = 0

    for i in range(0, total, batch_size):
        batch = records[i:i + batch_size]
        try:
            response = requests.post(url, headers=headers, json=batch, timeout=30)
            if response.status_code in (200, 201):
                result = response.json()
                success_count += len(batch)
                print(f"✅ 推送成功: {i + 1}-{min(i + batch_size, total)}/{total}")
            else:
                print(f"❌ 推送失败 (HTTP {response.status_code}): {response.text[:200]}")
        except Exception as e:
            print(f"❌ 推送出错: {e}")

    print(f"\n📊 推送完成: 成功 {success_count}/{total} 条")


def save_to_csv(df, lof_type):
    """保存到 CSV 文件"""
    filename = f"lof_{lof_type}_{datetime.now().strftime('%Y%m%d')}.csv"
    df.to_csv(filename, index=False)
    print(f"💾 数据已保存到: {filename}")
    return filename


def main(push_api=True, save_csv=False):
    """
    主函数: 获取所有类型的 LOF 数据
    :param push_api: 是否推送到 API (默认: True)
    :param save_csv: 是否保存 CSV (默认: False)
    """
    all_records = []

    for lof_type in ["stock", "index"]:
        print(f"\n{'='*50}")
        print(f"📈 获取 {lof_type.upper()} LOF 数据")
        print('='*50)

        df = fetch_jisilu_lof_data(lof_type)

        if df is not None and not df.empty:
            # 保存 CSV (需要显式启用)
            if save_csv:
                save_to_csv(df, lof_type)

            # 转换格式
            records = transform_to_api_format(df, lof_type)
            all_records.extend(records)

            # 打印 Top 10 溢价
            if 'discount_rt' in df.columns:
                df['discount_rt'] = pd.to_numeric(df['discount_rt'], errors='coerce')
                df_sorted = df.sort_values(by='discount_rt', ascending=False)
                print(f"\n🔥 {lof_type.upper()} LOF 溢价排行 (Top 10):")
                cols = ['fund_id', 'fund_nm', 'price', 'fund_nav', 'discount_rt']
                available_cols = [c for c in cols if c in df.columns]
                print(df_sorted[available_cols].head(10).to_string(index=False))
        else:
            print(f"⚠️ 未获取到 {lof_type} 数据")

        time.sleep(1)  # 请求间隔

    # 推送到 API
    if push_api and all_records:
        print(f"\n{'='*50}")
        print(f"🚀 推送 {len(all_records)} 条数据到 API")
        print('='*50)
        push_to_api(all_records)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='集思录 LOF 数据爬取')
    parser.add_argument('--no-push', action='store_true', help='不推送到 API')
    parser.add_argument('--csv', action='store_true', help='同时保存 CSV 文件')
    args = parser.parse_args()
    
    main(push_api=not args.no_push, save_csv=args.csv)
