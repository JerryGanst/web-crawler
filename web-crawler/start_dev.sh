#!/bin/bash

# ============================================
# TrendRadar 開發環境啟動腳本
# 同時啟動後端 API (8000) 和前端 Dev Server (5173)
# ============================================

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# 獲取項目根目錄
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo -e "${BOLD}╔════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     TrendRadar 開發環境啟動            ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════╝${NC}"
echo ""

# 清理函數
cleanup() {
    echo ""
    echo -e "${YELLOW}正在關閉所有服務...${NC}"
    
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null
        echo -e "  ✅ 後端服務已停止"
    fi
    
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null
        echo -e "  ✅ 前端服務已停止"
    fi
    
    # 清理可能殘留的進程
    lsof -ti:8000 | xargs kill -9 2>/dev/null
    lsof -ti:5173 | xargs kill -9 2>/dev/null
    
    exit 0
}

# 捕獲退出信號
trap cleanup SIGINT SIGTERM

# ============================================
# 1. 啟動後端 API 服務 (8000)
# ============================================
echo -e "${BLUE}[1/2] 啟動後端 API 服務...${NC}"

# 清理可能占用的端口
lsof -ti:8000 | xargs kill -9 2>/dev/null

cd "${PROJECT_ROOT}"
python3 server.py > /tmp/trendradar_backend.log 2>&1 &
BACKEND_PID=$!

# 等待後端啟動
sleep 3

if kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "  ${GREEN}✅ 後端服務啟動成功 (PID: $BACKEND_PID)${NC}"
    echo -e "     http://localhost:8000"
else
    echo -e "  ${RED}❌ 後端服務啟動失敗${NC}"
    echo -e "     查看日誌: tail -f /tmp/trendradar_backend.log"
    exit 1
fi

# ============================================
# 2. 啟動前端開發服務器 (5173)
# ============================================
echo -e "${BLUE}[2/2] 啟動前端開發服務器...${NC}"

# 清理可能占用的端口
lsof -ti:5173 | xargs kill -9 2>/dev/null

cd "${PROJECT_ROOT}/frontend"

# 檢查 node_modules 是否存在
if [ ! -d "node_modules" ]; then
    echo -e "  ${YELLOW}⚠️  首次運行，安裝依賴中...${NC}"
    npm install
fi

npm run dev > /tmp/trendradar_frontend.log 2>&1 &
FRONTEND_PID=$!

# 等待前端啟動
sleep 3

if kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "  ${GREEN}✅ 前端服務啟動成功 (PID: $FRONTEND_PID)${NC}"
    echo -e "     http://localhost:5173"
else
    echo -e "  ${RED}❌ 前端服務啟動失敗${NC}"
    echo -e "     查看日誌: tail -f /tmp/trendradar_frontend.log"
    cleanup
    exit 1
fi

# ============================================
# 顯示訪問信息
# ============================================
echo ""
echo -e "${BOLD}╔════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║           🚀 開發環境已就緒！          ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "  🌐 ${BOLD}訪問地址:${NC}"
echo -e "     前端: ${GREEN}http://localhost:5173${NC}"
echo -e "     API:  ${GREEN}http://localhost:8000${NC}"
echo -e "     文檔: ${GREEN}http://localhost:8000/docs${NC}"
echo ""
echo -e "  📝 ${BOLD}日誌文件:${NC}"
echo -e "     後端: ${BLUE}/tmp/trendradar_backend.log${NC}"
echo -e "     前端: ${BLUE}/tmp/trendradar_frontend.log${NC}"
echo ""
echo -e "  ${YELLOW}按 Ctrl+C 停止所有服務${NC}"
echo ""

# 保持腳本運行
wait
