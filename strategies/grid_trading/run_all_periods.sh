#!/bin/bash

# 运行四个周期的网格交易回测

echo "========================================="
echo "开始运行四个周期的网格交易回测..."
echo "========================================="

# 1. 长周期 (2021-01-01 至 2025-12-01)
echo ""
echo "1/4 运行长周期回测 (2021-01-01 至 2025-12-01)..."
sed -i '' "s/START_DATE = '.*'/START_DATE = '20210101'/" config.py
sed -i '' "s/END_DATE = '.*'/END_DATE = '20251201'/" config.py
python main.py > /dev/null 2>&1
echo "✓ 长周期回测完成"

# 2. 熊市周期 (2023-02-01 至 2024-02-01)
echo ""
echo "2/4 运行熊市周期回测 (2023-02-01 至 2024-02-01)..."
sed -i '' "s/START_DATE = '.*'/START_DATE = '20230201'/" config.py
sed -i '' "s/END_DATE = '.*'/END_DATE = '20240201'/" config.py
python main.py > /dev/null 2>&1
echo "✓ 熊市周期回测完成"

# 3. 牛市周期 (2024-11-01 至 2025-12-01)
echo ""
echo "3/4 运行牛市周期回测 (2024-11-01 至 2025-12-01)..."
sed -i '' "s/START_DATE = '.*'/START_DATE = '20241101'/" config.py
sed -i '' "s/END_DATE = '.*'/END_DATE = '20251201'/" config.py
python main.py > /dev/null 2>&1
echo "✓ 牛市周期回测完成"

# 4. 震荡周期 (2021-01-01 至 2022-01-01)
echo ""
echo "4/4 运行震荡周期回测 (2021-01-01 至 2022-01-01)..."
sed -i '' "s/START_DATE = '.*'/START_DATE = '20210101'/" config.py
sed -i '' "s/END_DATE = '.*'/END_DATE = '20220101'/" config.py
python main.py > /dev/null 2>&1
echo "✓ 震荡周期回测完成"

# 恢复默认配置（长周期）
sed -i '' "s/START_DATE = '.*'/START_DATE = '20210101'/" config.py
sed -i '' "s/END_DATE = '.*'/END_DATE = '20251201'/" config.py

echo ""
echo "========================================="
echo "所有回测完成！"
echo "========================================="
echo ""
echo "查看最新结果："
echo "ls -lt results/ | head -5"
ls -lt results/ | head -5
