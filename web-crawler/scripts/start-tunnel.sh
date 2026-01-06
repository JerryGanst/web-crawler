#!/bin/bash
# 启动公网穿透服务

# 默认端口，可通过参数指定
PORT=${1:-5173}

echo "🚀 启动 TrendRadar 公网穿透 (端口: $PORT)..."

# 检查后端服务
if ! curl -s http://localhost:$PORT/api/status > /dev/null 2>&1; then
    echo "⚠️ 后端服务未运行在端口 $PORT"
    echo "   请先运行: ./start.sh $PORT"
    exit 1
fi

# 停止旧的穿透进程
pkill -f "lt --port" 2>/dev/null
pkill -f "cloudflared tunnel" 2>/dev/null

# 尝试使用 cloudflared（更稳定）
if command -v cloudflared &> /dev/null; then
    echo "📡 使用 Cloudflare Tunnel..."
    cloudflared tunnel --url http://localhost:$PORT 2>&1 | tee /tmp/tunnel.log &
    sleep 5
    # 从日志中提取 URL
    TUNNEL_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/tunnel.log | head -1)
    if [ -n "$TUNNEL_URL" ]; then
        echo ""
        echo "✅ 公网地址: $TUNNEL_URL"
        echo ""
        # 自动更新配置
        cd "$(dirname "$0")"
        sed -i '' "s|public_url:.*|public_url: \"$TUNNEL_URL\"|" config/config.yaml
        echo "✅ 已自动更新 config/config.yaml"
        echo ""
        echo "🔗 报告下载链接示例: $TUNNEL_URL/api/reports/xxx.md"
        echo ""
        echo "按 Ctrl+C 停止穿透服务"
        wait
    fi
else
    # 使用 localtunnel
    echo "📡 使用 LocalTunnel..."
    lt --port $PORT --subdomain trendradar-$(whoami) 2>&1 | while read line; do
        echo "$line"
        if [[ "$line" == *"your url is:"* ]]; then
            URL=$(echo "$line" | grep -o 'https://[^ ]*')
            echo ""
            echo "✅ 公网地址: $URL"
            echo "📋 请将此地址更新到 config/config.yaml 的 app.public_url"
        fi
    done
fi
