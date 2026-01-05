import requests
import pandas as pd
import time
import json
from datetime import datetime

# 配置部分
# 注意: 集思录数据通常对游客有延迟，或者只显示部分数据。
# 想要实时或完整数据，通常需要登录后的 Cookie。
# 在浏览器 F12 网络面板中找到请求，复制 Cookie 填入下方。
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.jisilu.cn/data/lof/",
    # "Cookie": "kbzw__Session=...; kbzw__user_login=...;" # 填入您的 Cookie
}

def fetch_jisilu_lof_data(lof_type="stock"):
    """
    爬取集思录 LOF 数据
    :param lof_type: 'stock' (股票LOF), 'index' (指数LOF), 'qdii' (QDII LOF)
    """
    
    # URL 映射 (集思录的数据接口URL，可能会随时间变化)
    urls = {
        "stock": "https://www.jisilu.cn/data/lof/stock_lof_list/",
        "index": "https://www.jisilu.cn/data/lof/index_lof_list/", 
        "qdii": "https://www.jisilu.cn/data/qdii/qdii_list/"
    }
    
    if lof_type not in urls:
        print(f"未知类型: {lof_type}")
        return None

    url = urls[lof_type]
    
    # 构造请求参数 (添加时间戳防止缓存)
    params = {
        "___jsl=LST___t": int(time.time() * 1000)
    }

    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 正在请求 {lof_type} LOF 数据...")
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # 集思录返回的 JSON 结构通常是 {'rows': [{'id':..., 'cell': {...}}, ...]}
            if 'rows' in data:
                rows = [item['cell'] for item in data['rows']]
                df = pd.DataFrame(rows)
                return df
            else:
                print("数据格式解析失败，未找到 'rows' 字段")
                # 打印部分内容调试
                print(data)
                return None
        else:
            print(f"请求失败: 状态码 {response.status_code}")
            return None

    except Exception as e:
        print(f"发生错误: {e}")
        return None

def main():
    # 示例: 获取 QDII LOF 数据 (通常这是套利最关注的)
    df_qdii = fetch_jisilu_lof_data("qdii")
    
    if df_qdii is not None and not df_qdii.empty:
        # 筛选关键列 (列名可能需要根据实际返回调整，以下是常见列名)
        # discount_rt: 溢价率
        # fund_nm: 基金名称
        # fund_id: 基金代码
        # price: 现价
        # nav: 净值
        # apply_limit: 申购限额
        
        # 打印列名以便确认
        # print("所有列名:", df_qdii.columns.tolist())
        
        cols = ['fund_id', 'fund_nm', 'price', 'fund_nav', 'discount_rt', 'apply_limit']
        # 确保列存在
        available_cols = [c for c in cols if c in df_qdii.columns]
        
        print("\n=== QDII LOF 溢价套利监控 (Top 10) ===")
        # 转换类型以便排序 (处理可能的非数字字符)
        df_qdii['discount_rt'] = pd.to_numeric(df_qdii['discount_rt'], errors='coerce')
        
        # 按溢价率降序
        df_sorted = df_qdii.sort_values(by='discount_rt', ascending=False)
        
        print(df_sorted[available_cols].head(10).to_string(index=False))
        
        # 保存到 CSV
        filename = f"strategies/lof_arbitrage/lof_qdii_{datetime.now().strftime('%Y%m%d')}.csv"
        df_sorted.to_csv(filename, index=False)
        print(f"\n数据已保存到: {filename}")

if __name__ == "__main__":
    main()
