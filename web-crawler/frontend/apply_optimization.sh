#!/bin/bash

# TrendRadar Dashboard 优化应用脚本
# 使用方法: bash apply_optimization.sh

echo "=========================================="
echo "TrendRadar Dashboard 优化应用工具"
echo "=========================================="
echo ""

# 设置颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 项目路径
PROJECT_PATH="/Users/jerryganst/Desktop/TrendRadar/frontend"
PAGES_PATH="$PROJECT_PATH/src/pages"
COMPONENTS_PATH="$PROJECT_PATH/src/components"

echo "📁 项目路径: $PROJECT_PATH"
echo ""

# 检查路径是否存在
if [ ! -d "$PROJECT_PATH" ]; then
    echo -e "${RED}❌ 错误: 项目路径不存在!${NC}"
    exit 1
fi

# 1. 备份原文件
echo "🔄 步骤 1: 备份原文件..."
timestamp=$(date +%Y%m%d_%H%M%S)
backup_dir="$PROJECT_PATH/backups/$timestamp"
mkdir -p "$backup_dir"

if [ -f "$PAGES_PATH/Dashboard.jsx" ]; then
    cp "$PAGES_PATH/Dashboard.jsx" "$backup_dir/Dashboard.jsx.backup"
    echo -e "${GREEN}✓${NC} Dashboard.jsx 已备份"
fi

if [ -f "$COMPONENTS_PATH/CommodityChart.jsx" ]; then
    cp "$COMPONENTS_PATH/CommodityChart.jsx" "$backup_dir/CommodityChart.jsx.backup"
    echo -e "${GREEN}✓${NC} CommodityChart.jsx 已备份"
fi

echo -e "${GREEN}✓${NC} 备份完成: $backup_dir"
echo ""

# 2. 应用优化版本
echo "🚀 步骤 2: 应用优化版本..."

if [ -f "$PAGES_PATH/Dashboard_Optimized.jsx" ]; then
    cp "$PAGES_PATH/Dashboard_Optimized.jsx" "$PAGES_PATH/Dashboard.jsx"
    echo -e "${GREEN}✓${NC} Dashboard.jsx 已更新"
else
    echo -e "${RED}❌ 错误: Dashboard_Optimized.jsx 不存在!${NC}"
    exit 1
fi

if [ -f "$COMPONENTS_PATH/CommodityChart_Optimized.jsx" ]; then
    cp "$COMPONENTS_PATH/CommodityChart_Optimized.jsx" "$COMPONENTS_PATH/CommodityChart.jsx"
    echo -e "${GREEN}✓${NC} CommodityChart.jsx 已更新"
else
    echo -e "${RED}❌ 错误: CommodityChart_Optimized.jsx 不存在!${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓${NC} 优化应用完成!"
echo ""

# 3. 提示重启服务器
echo "📋 接下来的步骤:"
echo ""
echo "1. 重启开发服务器:"
echo -e "   ${YELLOW}cd $PROJECT_PATH${NC}"
echo -e "   ${YELLOW}npm run dev${NC}"
echo ""
echo "2. 在浏览器中打开应用并验证:"
echo "   - 商品选择器功能"
echo "   - 搜索和筛选"
echo "   - 图表显示"
echo "   - 响应式布局"
echo ""
echo "3. 如需回滚到原版本:"
echo -e "   ${YELLOW}bash restore_backup.sh $timestamp${NC}"
echo ""
echo "=========================================="
echo "完成! 🎉"
echo "=========================================="
