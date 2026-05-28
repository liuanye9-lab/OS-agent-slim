#!/bin/bash
# 一键启动 Dashboard
HOST="${1:-127.0.0.1}"
PORT="${2:-8000}"
echo "启动 StableAgent OS Dashboard..."
echo "Dashboard: http://$HOST:$PORT/dashboard/v2"
echo "Connect:   http://$HOST:$PORT/connect"
open "http://$HOST:$PORT/dashboard/v2" 2>/dev/null || xdg-open "http://$HOST:$PORT/dashboard/v2" 2>/dev/null || echo "请手动打开: http://$HOST:$PORT/dashboard/v2"
