#!/bin/bash

# ============================================
# Commodity Radar 状态检查脚本
# ============================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  ${BOLD}🛰️  Commodity Radar 服务状态${NC}                              ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# 检查后端
echo -e "${BOLD}📡 服务状态:${NC}"
if lsof -i:8000 &>/dev/null; then
    echo -e "  ${GREEN}✅ 后端 API${NC}     http://localhost:8000    ${GREEN}运行中${NC}"
else
    echo -e "  ${RED}❌ 后端 API${NC}     http://localhost:8000    ${RED}未运行${NC}"
fi

if lsof -i:5173 &>/dev/null; then
    echo -e "  ${GREEN}✅ 前端界面${NC}     http://localhost:5173    ${GREEN}运行中${NC}"
else
    echo -e "  ${RED}❌ 前端界面${NC}     http://localhost:5173    ${RED}未运行${NC}"
fi

echo ""
echo -e "${BOLD}🗄️ 数据库状态:${NC}"

# Redis
python3 -c "
import redis
try:
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.ping()
    print('  \033[0;32m✅ Redis\033[0m        localhost:6379        \033[0;32m连接正常\033[0m')
except:
    print('  \033[0;31m❌ Redis\033[0m        localhost:6379        \033[0;31m无法连接\033[0m')
" 2>/dev/null

# MongoDB
python3 -c "
from pymongo import MongoClient
try:
    client = MongoClient('mongodb://root:362514@localhost:27017/?authSource=admin', serverSelectionTimeoutMS=2000)
    client.admin.command('ping')
    print('  \033[0;32m✅ MongoDB\033[0m      localhost:27017       \033[0;32m连接正常\033[0m')
except:
    print('  \033[0;31m❌ MongoDB\033[0m      localhost:27017       \033[0;31m无法连接\033[0m')
" 2>/dev/null

# MySQL
python3 -c "
import pymysql
try:
    conn = pymysql.connect(host='localhost', port=3306, user='root', password='trendradar123', database='trendradar')
    conn.close()
    print('  \033[0;32m✅ MySQL\033[0m        localhost:3306        \033[0;32m连接正常\033[0m')
except:
    print('  \033[0;31m❌ MySQL\033[0m        localhost:3306        \033[0;31m无法连接\033[0m')
" 2>/dev/null

echo ""
echo -e "${BOLD}🐳 Docker 容器:${NC}"
docker ps --format "  {{.Names}}\t{{.Status}}" 2>/dev/null | grep -E "mysql|mongo|redis" || echo -e "  ${YELLOW}⚠️ 没有相关容器运行${NC}"

echo ""
echo -e "${BOLD}📋 快捷命令:${NC}"
echo -e "  启动服务:  ${BLUE}./start.sh${NC}"
echo -e "  停止服务:  ${BLUE}./stop.sh${NC}"
echo -e "  查看日志:  ${BLUE}tail -f /tmp/commodity_backend.log${NC}"
echo ""
