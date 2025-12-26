# TrendRadar Windows Startup Script
# Automatically start Backend API and Frontend Dev Server

$ErrorActionPreference = "Stop"

# Configure Python Path (Hardcoded for this environment)
$PYTHON_PATH = "C:\Users\10353965\AppData\Local\Programs\Python\Python39\python.exe"

# Check if Python exists
if (-not (Test-Path $PYTHON_PATH)) {
    Write-Host "Error: Python not found at: $PYTHON_PATH" -ForegroundColor Red
    exit 1
}

$PROJECT_ROOT = Resolve-Path "."
$BACKEND_DIR = $PROJECT_ROOT
$FRONTEND_DIR = Join-Path $BACKEND_DIR "frontend"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "     TrendRadar Dev Start (Windows)       " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Start Backend
Write-Host "[1/2] Starting Backend API Service (Port 8000)..." -ForegroundColor Yellow
$BackendProcess = Start-Process -FilePath $PYTHON_PATH -ArgumentList "server.py" -WorkingDirectory $BACKEND_DIR -PassThru -NoNewWindow
Write-Host "  Backend service started in background (PID: $($BackendProcess.Id))" -ForegroundColor Green
Write-Host "     http://localhost:8000"

# Wait a few seconds for backend initialization
Start-Sleep -Seconds 3

# 2. Start Frontend
Write-Host "[2/2] Starting Frontend Dev Server (Port 5173)..." -ForegroundColor Yellow
Set-Location $FRONTEND_DIR

# Check node_modules
if (-not (Test-Path "node_modules")) {
    Write-Host "  First run detected, installing dependencies..." -ForegroundColor Yellow
    npm install
}

Write-Host "Starting Frontend..." -ForegroundColor Cyan
npm run dev
