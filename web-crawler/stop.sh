#!/bin/bash

# ============================================
# Commodity Radar 停止脚本
# ============================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${YELLOW}🛑 正在停止 Commodity Radar 服务...${NC}"
echo ""

# 停止后端 (默认端口 8000)
BACKEND_PORT=${1:-8000}
BACKEND_PIDS=$(lsof -ti:$BACKEND_PORT 2>/dev/null)
if [ -n "$BACKEND_PIDS" ]; then
    echo "$BACKEND_PIDS" | xargs kill -9 2>/dev/null
    echo -e "  ${GREEN}✅ 后端服务已停止 (端口 $BACKEND_PORT)${NC}"
else
    echo -e "  ${YELLOW}⚠️ 后端服务未运行${NC}"
fi

# 停止前端 (默认端口 5173)
FRONTEND_PORT=${2:-5173}
FRONTEND_PIDS=$(lsof -ti:$FRONTEND_PORT 2>/dev/null)
if [ -n "$FRONTEND_PIDS" ]; then
    echo "$FRONTEND_PIDS" | xargs kill -9 2>/dev/null
    echo -e "  ${GREEN}✅ 前端服务已停止 (端口 $FRONTEND_PORT)${NC}"
else
    echo -e "  ${YELLOW}⚠️ 前端服务未运行${NC}"
fi

# 停止可能的 uvicorn 进程
pkill -f "uvicorn server:app" 2>/dev/null && echo -e "  ${GREEN}✅ uvicorn 进程已停止${NC}"

# 停止可能的 vite 进程
pkill -f "vite" 2>/dev/null && echo -e "  ${GREEN}✅ vite 进程已停止${NC}"

echo ""
echo -e "${GREEN}✅ 所有服务已停止${NC}"
echo ""
