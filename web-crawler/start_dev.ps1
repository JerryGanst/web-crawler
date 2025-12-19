# TrendRadar Windows 启动脚本
# 自动启动后端 API 和前端开发服务器

$ErrorActionPreference = "Stop"

# 配置 Python 路径 (根据环境自动检测到的路径)
$PYTHON_PATH = "C:\Users\10353965\AppData\Local\Programs\Python\Python39\python.exe"

# 检查 Python 是否存在
if (-not (Test-Path $PYTHON_PATH)) {
    Write-Host "错误: 未找到 Python，请检查路径: $PYTHON_PATH" -ForegroundColor Red
    exit 1
}

$PROJECT_ROOT = Resolve-Path "."
$BACKEND_DIR = Join-Path $PROJECT_ROOT "web-crawler"
$FRONTEND_DIR = Join-Path $BACKEND_DIR "frontend"

Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     TrendRadar 开发环境启动 (Windows)  ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# 1. 启动后端
Write-Host "[1/2] 启动后端 API 服务 (Port 8000)..." -ForegroundColor Yellow
$BackendProcess = Start-Process -FilePath $PYTHON_PATH -ArgumentList "server.py" -WorkingDirectory $BACKEND_DIR -PassThru -NoNewWindow
Write-Host "  ✅ 后端服务已在后台启动 (PID: $($BackendProcess.Id))" -ForegroundColor Green
Write-Host "     http://localhost:8000"

# 等待几秒确保后端初始化
Start-Sleep -Seconds 3

# 2. 启动前端
Write-Host "[2/2] 启动前端开发服务器 (Port 5173)..." -ForegroundColor Yellow
Set-Location $FRONTEND_DIR

# 检查 node_modules
if (-not (Test-Path "node_modules")) {
    Write-Host "  ⚠️  首次运行，安装依赖中..." -ForegroundColor Yellow
    npm install
}

Write-Host "正在启动前端..." -ForegroundColor Cyan
npm run dev
