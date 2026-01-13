#!/bin/bash

# ============================================
# Commodity Radar 一键启动脚本
# 后端 API + 前端 + AI 聊天引擎
# ============================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT=${1:-8000}
FRONTEND_PORT=${2:-5173}

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 正在关闭所有服务...${NC}"
    [ -n "$BACKEND_PID" ] && kill $BACKEND_PID 2>/dev/null && echo -e "  ✅ 后端已停止"
    [ -n "$FRONTEND_PID" ] && kill $FRONTEND_PID 2>/dev/null && echo -e "  ✅ 前端已停止"
    lsof -ti:$BACKEND_PORT | xargs kill -9 2>/dev/null
    lsof -ti:$FRONTEND_PORT | xargs kill -9 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

# 显示 Banner
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  ${BOLD}🛰️  Commodity Radar${NC}                                      ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}     多平台热搜聚合 + AI 智能分析                          ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# 检查依赖
echo -e "${BLUE}[1/4]${NC} 检查环境..."
cd "$PROJECT_ROOT"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 未安装${NC}"
    exit 1
fi
echo -e "  ✅ Python3: $(python3 --version)"

if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js 未安装${NC}"
    exit 1
fi
echo -e "  ✅ Node.js: $(node --version)"

# 检查数据库连接
echo -e "${BLUE}[2/4]${NC} 检查数据库..."
python3 -c "
import redis
r = redis.Redis(host='localhost', port=6379, db=0)
r.ping()
print('  ✅ Redis 连接正常')
" 2>/dev/null || echo -e "  ${YELLOW}⚠️ Redis 未连接${NC}"

python3 -c "
from pymongo import MongoClient
client = MongoClient('mongodb://root:362514@localhost:27017/?authSource=admin', serverSelectionTimeoutMS=2000)
client.admin.command('ping')
print('  ✅ MongoDB 连接正常')
" 2>/dev/null || echo -e "  ${YELLOW}⚠️ MongoDB 未连接${NC}"

# 启动后端
echo -e "${BLUE}[3/4]${NC} 启动后端 API..."
lsof -ti:$BACKEND_PORT | xargs kill -9 2>/dev/null

python3 server.py > /tmp/commodity_backend.log 2>&1 &
BACKEND_PID=$!
sleep 3

if kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "  ${GREEN}✅ 后端启动成功${NC} (PID: $BACKEND_PID)"
else
    echo -e "  ${RED}❌ 后端启动失败${NC}"
    echo -e "     查看日志: tail -f /tmp/commodity_backend.log"
    exit 1
fi

# 启动前端
echo -e "${BLUE}[4/4]${NC} 启动前端..."
lsof -ti:$FRONTEND_PORT | xargs kill -9 2>/dev/null

cd "$PROJECT_ROOT/frontend"
[ ! -d "node_modules" ] && npm install --silent
npm run dev -- --port $FRONTEND_PORT > /tmp/commodity_frontend.log 2>&1 &
FRONTEND_PID=$!
sleep 2

if kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "  ${GREEN}✅ 前端启动成功${NC} (PID: $FRONTEND_PID)"
else
    echo -e "  ${RED}❌ 前端启动失败${NC}"
fi

# 显示访问信息
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  ${GREEN}🚀 服务已启动！${NC}                                          ${CYAN}║${NC}"
echo -e "${CYAN}╠══════════════════════════════════════════════════════════╣${NC}"
echo -e "${CYAN}║${NC}                                                            ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  ${BOLD}访问地址:${NC}                                                ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}    🌐 前端界面:  ${GREEN}http://localhost:$FRONTEND_PORT${NC}                 ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}    🔌 API 接口:  ${GREEN}http://localhost:$BACKEND_PORT${NC}                  ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}    📖 API 文档:  ${GREEN}http://localhost:$BACKEND_PORT/docs${NC}             ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}                                                            ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  ${BOLD}AI 聊天功能:${NC}                                              ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}    💬 点击右下角悬浮球开启 AI 助手                          ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}    🤖 支持自然语言查询新闻/分析趋势                         ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}                                                            ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  ${BOLD}日志位置:${NC}                                                ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}    后端: /tmp/commodity_backend.log                        ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}    前端: /tmp/commodity_frontend.log                       ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}                                                            ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${YELLOW}按 Ctrl+C 停止所有服务${NC}"
echo ""

wait
