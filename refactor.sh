#!/bin/bash

# 项目重构脚本
# 完成所有文件的移动和更新

echo "开始项目重构..."

# 1. 更新 .gitignore，允许results目录上传
echo "更新 .gitignore..."
cat > .gitignore << 'EOF'
__pycache__/
*.pyc
.DS_Store
*.log
EOF

# 2. 删除旧的空目录
echo "清理旧目录..."
rmdir doc 2>/dev/null || true
rmdir results 2>/dev/null || true

# 3. 删除旧的config.py
echo "删除旧配置文件..."
rm -f config.py

# 4. 更新README
echo "更新README..."
cat > README.md << 'EOF'
# 量化交易策略回测系统

## 项目结构

```
strategy/
├── common/              # 共享模块
│   ├── data_fetcher.py # 数据获取
│   └── metrics.py      # 投资指标计算
├── config/             # 全局配置
├── strategies/         # 策略目录
│   ├── macd/          # MACD策略
│   └── position_management/  # 仓位管理策略
└── tests/             # 测试
```

## 快速开始

### 运行MACD策略
```bash
cd strategies/macd
python main.py
```

### 运行仓位管理策略
```bash
cd strategies/position_management
python main.py

# 运行所有周期
./run_all_periods.sh
```

## 核心功能

- ✅ 多策略支持
- ✅ 专业投资指标（IRR、夏普比率等）
- ✅ 净投入收益率计算
- ✅ 历史回测结果保存

详见各策略目录下的文档。
EOF

echo "✅ 重构完成！"
echo ""
echo "新的项目结构："
echo "  - common/          共享模块"
echo "  - config/          全局配置"
echo "  - strategies/      策略目录"
echo "    - macd/         MACD策略"
echo "    - position_management/  仓位管理策略"
echo ""
echo "请查看 项目重构总结.md 了解详情"
