#!/bin/bash

# ============================================
# TrendRadar 一键启动脚本
# ============================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# 默认端口
PORT=${1:-5173}

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo -e "${BOLD}╔════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     TrendRadar 一键启动                ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "📍 项目目录: ${BLUE}${PROJECT_ROOT}${NC}"
echo -e "🌐 服务端口: ${GREEN}${PORT}${NC}"
echo ""

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}正在关闭服务...${NC}"
    
    # 杀掉后台进程
    if [ ! -z "$API_PID" ]; then
        kill $API_PID 2>/dev/null
        echo -e "  ✅ API 服务已停止"
    fi
    
    
    exit 0
}

# 捕获退出信号
trap cleanup SIGINT SIGTERM

# ============================================
# 1. 检查并激活 Python 虚拟环境
# ============================================
echo -e "${BLUE}[1/3] 检查 Python 环境...${NC}"

if [ -d "${PROJECT_ROOT}/.venv" ]; then
    source "${PROJECT_ROOT}/.venv/bin/activate"
    echo -e "  ${GREEN}✅ 虚拟环境已激活${NC}"
else
    echo -e "  ${YELLOW}⚠️  未找到虚拟环境，尝试创建...${NC}"
    if command -v uv &> /dev/null; then
        uv sync
    else
        python3 -m venv .venv
        source "${PROJECT_ROOT}/.venv/bin/activate"
        pip install -r requirements.txt
    fi
fi

# ============================================
# 2. 初始化数据库
# ============================================
echo -e "${BLUE}[2/3] 初始化数据库...${NC}"

# 确保 data 目录存在
mkdir -p "${PROJECT_ROOT}/data"
mkdir -p "${PROJECT_ROOT}/output"
mkdir -p "${PROJECT_ROOT}/reports"

# 运行数据库初始化
python -c "
from database import get_db
db = get_db()
print('  ✅ 数据库初始化完成')
" 2>/dev/null || echo -e "  ${YELLOW}⚠️  数据库初始化跳过（可能已存在）${NC}"

# ============================================
# 3. 启动 API 后端服务
# ============================================
echo -e "${BLUE}[3/3] 启动服务 (端口 ${PORT})...${NC}"

# 先杀掉可能占用端口的进程
lsof -ti:${PORT} | xargs kill -9 2>/dev/null

# 启动服务（包含API和静态文件）
python -c "
import uvicorn
uvicorn.run('server:app', host='0.0.0.0', port=${PORT}, reload=True, log_level='info')
" &
API_PID=$!

# 等待服务启动
echo -e "  等待服务启动..."
sleep 3

# 检查是否启动成功
if curl -s "http://localhost:${PORT}/api/status" > /dev/null 2>&1; then
    echo -e "  ${GREEN}✅ 服务启动成功${NC}"
else
    echo -e "  ${YELLOW}⚠️  服务可能还在启动中...${NC}"
fi

# ============================================
# 显示访问信息
# ============================================
echo ""
echo -e "${BOLD}╔════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║           🚀 服务已启动！              ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "  🌐 ${BOLD}访问地址:${NC}"
echo -e "     ${GREEN}http://localhost:${PORT}${NC} (热点雷达)"
echo -e "     ${GREEN}http://localhost:${PORT}/docs${NC} (API 文档)"
echo ""
echo -e "  ${YELLOW}按 Ctrl+C 停止所有服务${NC}"
echo ""

# 保持脚本运行
wait
