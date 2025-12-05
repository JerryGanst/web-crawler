#!/bin/bash

# TrendRadar Dashboard 备份回滚脚本
# 使用方法: bash restore_backup.sh [backup_timestamp]

echo "=========================================="
echo "TrendRadar Dashboard 备份回滚工具"
echo "=========================================="
echo ""

# 设置颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 项目路径
PROJECT_PATH="/Users/jerryganst/Desktop/TrendRadar/frontend"
PAGES_PATH="$PROJECT_PATH/src/pages"
COMPONENTS_PATH="$PROJECT_PATH/src/components"
BACKUP_BASE="$PROJECT_PATH/backups"

# 检查参数
if [ $# -eq 0 ]; then
    echo -e "${YELLOW}可用的备份:${NC}"
    echo ""
    if [ -d "$BACKUP_BASE" ]; then
        ls -1 "$BACKUP_BASE"
        echo ""
        echo "使用方法: bash restore_backup.sh [backup_timestamp]"
        echo "例如: bash restore_backup.sh 20251204_143000"
    else
        echo -e "${RED}没有找到备份文件夹${NC}"
    fi
    exit 0
fi

backup_timestamp=$1
backup_dir="$BACKUP_BASE/$backup_timestamp"

# 检查备份是否存在
if [ ! -d "$backup_dir" ]; then
    echo -e "${RED}❌ 错误: 备份不存在: $backup_dir${NC}"
    exit 1
fi

echo "📁 备份路径: $backup_dir"
echo ""

# 确认操作
echo -e "${YELLOW}⚠️  警告: 这将覆盖当前文件!${NC}"
read -p "确认回滚? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "操作已取消"
    exit 0
fi

echo ""
echo "🔄 开始回滚..."

# 回滚Dashboard
if [ -f "$backup_dir/Dashboard.jsx.backup" ]; then
    cp "$backup_dir/Dashboard.jsx.backup" "$PAGES_PATH/Dashboard.jsx"
    echo -e "${GREEN}✓${NC} Dashboard.jsx 已回滚"
else
    echo -e "${YELLOW}⚠${NC}  Dashboard.jsx 备份不存在"
fi

# 回滚CommodityChart
if [ -f "$backup_dir/CommodityChart.jsx.backup" ]; then
    cp "$backup_dir/CommodityChart.jsx.backup" "$COMPONENTS_PATH/CommodityChart.jsx"
    echo -e "${GREEN}✓${NC} CommodityChart.jsx 已回滚"
else
    echo -e "${YELLOW}⚠${NC}  CommodityChart.jsx 备份不存在"
fi

echo ""
echo -e "${GREEN}✓${NC} 回滚完成!"
echo ""
echo "请重启开发服务器以应用更改:"
echo -e "   ${YELLOW}cd $PROJECT_PATH${NC}"
echo -e "   ${YELLOW}npm run dev${NC}"
echo ""
echo "=========================================="
