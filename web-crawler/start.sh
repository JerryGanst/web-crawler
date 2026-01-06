#!/bin/bash

# ============================================
# TrendRadar 一键启动脚本
# 同时启动后端 API 与前端 Dev Server
# ============================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

usage() {
    echo "用法:"
    echo "  ./start.sh                    # 默认：后端 8000 + 前端 5173"
    echo "  ./start.sh <backend_port>     # 仅启动后端（兼容旧用法）"
    echo "  ./start.sh <backend> <front>  # 同时启动后端与前端"
    echo "  ./start.sh -b 8000 -f 5173    # 同上（可选参数）"
    echo "  ./start.sh --no-frontend      # 仅启动后端"
    echo ""
}

validate_port() {
    local p="$1"
    if [[ ! "$p" =~ ^[0-9]+$ ]] || [ "$p" -lt 1 ] || [ "$p" -gt 65535 ]; then
        echo -e "${RED}❌ 无效端口: $p${NC}"
        exit 1
    fi
}

# 默认端口
BACKEND_PORT=8000
FRONTEND_PORT=5173
START_FRONTEND=true

POSITIONALS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -b|--backend-port)
            BACKEND_PORT="$2"; shift 2 ;;
        -f|--frontend-port)
            FRONTEND_PORT="$2"; START_FRONTEND=true; shift 2 ;;
        --no-frontend)
            START_FRONTEND=false; shift ;;
        -h|--help)
            usage; exit 0 ;;
        *)
            POSITIONALS+=("$1"); shift ;;
    esac
done

if [ "${#POSITIONALS[@]}" -ge 1 ]; then
    BACKEND_PORT="${POSITIONALS[0]}"
fi
if [ "${#POSITIONALS[@]}" -ge 2 ]; then
    FRONTEND_PORT="${POSITIONALS[1]}"
    START_FRONTEND=true
elif [ "${#POSITIONALS[@]}" -eq 1 ] && [ "$BACKEND_PORT" = "$FRONTEND_PORT" ]; then
    # 仅指定一个端口且等于前端默认端口：沿用旧逻辑，仅启后端
    START_FRONTEND=false
fi

validate_port "$BACKEND_PORT"
validate_port "$FRONTEND_PORT"

if [ "$BACKEND_PORT" -eq "$FRONTEND_PORT" ] && [ "$START_FRONTEND" = true ]; then
    echo -e "${RED}❌ 后端端口与前端端口冲突: $BACKEND_PORT${NC}"
    echo -e "   请使用不同端口，例如: ./start.sh $BACKEND_PORT 5173"
    exit 1
fi

echo -e "${BOLD}╔════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     TrendRadar 一键启动                ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "📍 项目目录: ${BLUE}${PROJECT_ROOT}${NC}"
echo -e "🧩 后端端口: ${GREEN}${BACKEND_PORT}${NC}"
if [ "$START_FRONTEND" = true ]; then
    echo -e "🎨 前端端口: ${GREEN}${FRONTEND_PORT}${NC}"
else
    echo -e "🎨 前端启动: ${YELLOW}已跳过${NC}"
fi
echo ""

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}正在关闭所有服务...${NC}"

    if [ -n "${BACKEND_PID:-}" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
        echo -e "  ✅ 后端服务已停止"
    fi

    if [ -n "${FRONTEND_PID:-}" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
        echo -e "  ✅ 前端服务已停止"
    fi

    lsof -ti:"$BACKEND_PORT" | xargs kill -9 2>/dev/null || true
    if [ "$START_FRONTEND" = true ]; then
        lsof -ti:"$FRONTEND_PORT" | xargs kill -9 2>/dev/null || true
    fi

    exit 0
}

trap cleanup SIGINT SIGTERM

# ============================================
# 1. 检查并激活 Python 虚拟环境
# ============================================
echo -e "${BLUE}[1/5] 检查 Python 环境...${NC}"

cd "$PROJECT_ROOT"

if [ -d ".venv" ]; then
    source ".venv/bin/activate"
    echo -e "  ${GREEN}✅ 虚拟环境已激活${NC}"
else
    echo -e "  ${YELLOW}⚠️  未找到虚拟环境，尝试创建...${NC}"
    if command -v uv &> /dev/null; then
        uv sync
        if [ -d ".venv" ]; then
            source ".venv/bin/activate"
        fi
    else
        python3 -m venv .venv
        source ".venv/bin/activate"
        python3 -m pip install --upgrade pip
        pip install -e .
    fi
fi

# ============================================
# 2. 初始化数据库
# ============================================
echo -e "${BLUE}[2/5] 初始化数据库...${NC}"

mkdir -p "$PROJECT_ROOT/data" "$PROJECT_ROOT/output" "$PROJECT_ROOT/reports"

python - <<'PY' 2>/dev/null || echo -e "  ${YELLOW}⚠️  数据库初始化跳过（可能已存在）${NC}"
from database import get_db
get_db()
print("  ✅ 数据库初始化完成")
PY

# ============================================
# 3. 启动后端 API 服务
# ============================================
echo -e "${BLUE}[3/5] 启动后端 API (端口 ${BACKEND_PORT})...${NC}"

lsof -ti:"$BACKEND_PORT" | xargs kill -9 2>/dev/null || true

python -m uvicorn server:app \
    --host 0.0.0.0 \
    --port "$BACKEND_PORT" \
    --reload \
    --reload-dir "$PROJECT_ROOT" \
    --reload-exclude ".venv/*" \
    --reload-exclude "*/site-packages/*" \
    --reload-exclude "*/pip/*" \
    > /tmp/trendradar_backend.log 2>&1 &
BACKEND_PID=$!

sleep 3

if curl -s "http://localhost:${BACKEND_PORT}/api/status" > /dev/null 2>&1; then
    echo -e "  ${GREEN}✅ 后端启动成功 (PID: $BACKEND_PID)${NC}"
else
    echo -e "  ${YELLOW}⚠️  后端可能还在启动中... 日志: /tmp/trendradar_backend.log${NC}"
fi

# ============================================
# 4. 启动前端 Dev Server
# ============================================
if [ "$START_FRONTEND" = true ]; then
    echo -e "${BLUE}[4/5] 启动前端 Dev Server (端口 ${FRONTEND_PORT})...${NC}"

    lsof -ti:"$FRONTEND_PORT" | xargs kill -9 2>/dev/null || true

    cd "$PROJECT_ROOT/frontend"
    if [ ! -d "node_modules" ]; then
        echo -e "  ${YELLOW}⚠️  首次运行，安装前端依赖中...${NC}"
        npm install
    fi

    npm run dev -- --port "$FRONTEND_PORT" > /tmp/trendradar_frontend.log 2>&1 &
    FRONTEND_PID=$!

    sleep 3
    if kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo -e "  ${GREEN}✅ 前端启动成功 (PID: $FRONTEND_PID)${NC}"
    else
        echo -e "  ${RED}❌ 前端启动失败${NC}"
        echo -e "     查看日志: tail -f /tmp/trendradar_frontend.log"
        cleanup
    fi
else
    echo -e "${BLUE}[4/5] 前端 Dev Server 已跳过${NC}"
fi

# ============================================
# 5. 执行首次爬虫
# ============================================
echo -e "${BLUE}[5/5] 执行首次爬虫...${NC}"

cd "$PROJECT_ROOT"
(python - <<'PY'
import sys
sys.path.insert(0, '.')
from crawler import crawl_all_platforms
from database import save_news_batch

try:
    news_list = crawl_all_platforms()
    if news_list:
        save_news_batch(news_list)
        print(f"  ✅ 爬虫完成，获取 {len(news_list)} 条新闻")
    else:
        print("  ⚠️  爬虫完成，但未获取到新闻")
except Exception as e:
    print(f"  ⚠️  爬虫执行失败: {e}")
PY
) || echo -e "  ${YELLOW}⚠️  爬虫执行跳过${NC}"

# ============================================
# 显示访问信息
# ============================================
echo ""
echo -e "${BOLD}╔════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║           🚀 服务已启动！              ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "  🌐 ${BOLD}访问地址:${NC}"
if [ "$START_FRONTEND" = true ]; then
    echo -e "     前端: ${GREEN}http://localhost:${FRONTEND_PORT}${NC}"
fi
echo -e "     API:  ${GREEN}http://localhost:${BACKEND_PORT}${NC}"
echo -e "     文档: ${GREEN}http://localhost:${BACKEND_PORT}/docs${NC}"
echo ""
echo -e "  📝 ${BOLD}日志文件:${NC}"
echo -e "     后端: ${BLUE}/tmp/trendradar_backend.log${NC}"
if [ "$START_FRONTEND" = true ]; then
    echo -e "     前端: ${BLUE}/tmp/trendradar_frontend.log${NC}"
fi
echo ""
echo -e "  ${YELLOW}按 Ctrl+C 停止所有服务${NC}"
echo ""

wait
