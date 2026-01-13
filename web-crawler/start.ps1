# ============================================
# Commodity Radar Windows 启动脚本
# ============================================

$ErrorActionPreference = "Stop"
$PROJECT_ROOT = $PSScriptRoot
$BACKEND_PORT = if ($args[0]) { $args[0] } else { 8000 }
$FRONTEND_PORT = if ($args[1]) { $args[1] } else { 5173 }

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  🛰️  Commodity Radar                                      ║" -ForegroundColor Cyan
Write-Host "║     多平台热搜聚合 + AI 智能分析                          ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# 检查 Python
Write-Host "[1/4] 检查环境..." -ForegroundColor Blue
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Python 未安装" -ForegroundColor Red
    exit 1
}
Write-Host "  ✅ $pythonVersion" -ForegroundColor Green

$nodeVersion = node --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Node.js 未安装" -ForegroundColor Red
    exit 1
}
Write-Host "  ✅ Node.js $nodeVersion" -ForegroundColor Green

# 检查数据库
Write-Host "[2/4] 检查数据库..." -ForegroundColor Blue
try {
    python -c "import redis; r = redis.Redis(host='localhost', port=6379); r.ping(); print('  ✅ Redis 连接正常')"
} catch {
    Write-Host "  ⚠️ Redis 未连接" -ForegroundColor Yellow
}

try {
    python -c "from pymongo import MongoClient; MongoClient('mongodb://root:362514@localhost:27017/?authSource=admin', serverSelectionTimeoutMS=2000).admin.command('ping'); print('  ✅ MongoDB 连接正常')"
} catch {
    Write-Host "  ⚠️ MongoDB 未连接" -ForegroundColor Yellow
}

# 启动后端
Write-Host "[3/4] 启动后端 API..." -ForegroundColor Blue
Set-Location $PROJECT_ROOT
$backendJob = Start-Job -ScriptBlock {
    param($root, $port)
    Set-Location $root
    python server.py
} -ArgumentList $PROJECT_ROOT, $BACKEND_PORT

Start-Sleep -Seconds 3
Write-Host "  ✅ 后端已启动 (Job ID: $($backendJob.Id))" -ForegroundColor Green

# 启动前端
Write-Host "[4/4] 启动前端..." -ForegroundColor Blue
Set-Location "$PROJECT_ROOT\frontend"

if (-not (Test-Path "node_modules")) {
    Write-Host "  安装依赖中..." -ForegroundColor Yellow
    npm install --silent
}

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  🚀 服务启动中...                                         ║" -ForegroundColor Cyan
Write-Host "╠══════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║  前端: http://localhost:$FRONTEND_PORT                           ║" -ForegroundColor Cyan
Write-Host "║  API:  http://localhost:$BACKEND_PORT                            ║" -ForegroundColor Cyan
Write-Host "║  文档: http://localhost:$BACKEND_PORT/docs                       ║" -ForegroundColor Cyan
Write-Host "║                                                            ║" -ForegroundColor Cyan
Write-Host "║  💬 点击右下角悬浮球开启 AI 助手                          ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  按 Ctrl+C 停止前端，后台任务需手动关闭" -ForegroundColor Yellow
Write-Host ""

npm run dev -- --port $FRONTEND_PORT
