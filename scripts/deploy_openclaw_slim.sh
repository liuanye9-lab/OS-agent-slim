#!/usr/bin/env bash
# deploy_openclaw_slim.sh — StableAgent OS Slim Cloud Edition 部署脚本
# 适用于阿里云 ECS (2核2G, OpenClaw)
set -euo pipefail

INSTALL_DIR="/opt/os-agent"
SERVICE_NAME="stableagent-openclaw"
PORT=18789

echo "=========================================="
echo "StableAgent OS Slim Cloud Edition 部署"
echo "=========================================="

# 1. 检查 Python 3.11+
echo "[1/7] 检查 Python 版本..."
PYTHON_CMD=""
for cmd in python3.11 python3.12 python3.13 python3; do
    if command -v "$cmd" &>/dev/null; then
        PY_VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        PY_MAJOR=$("$cmd" -c "import sys; print(sys.version_info.major)")
        PY_MINOR=$("$cmd" -c "import sys; print(sys.version_info.minor)")
        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
            PYTHON_CMD="$cmd"
            echo "  找到 Python: $cmd ($PY_VER)"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "错误: 需要 Python 3.11+，请先安装。"
    echo "  Ubuntu/Debian: apt install python3.11 python3.11-venv"
    echo "  CentOS/RHEL:   yum install python3.11"
    exit 1
fi

# 2. 创建安装目录
echo "[2/7] 创建安装目录: $INSTALL_DIR"
if [ ! -d "$INSTALL_DIR" ]; then
    mkdir -p "$INSTALL_DIR"
fi

# 3. 复制项目文件
echo "[3/7] 复制项目文件..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

rsync -av --exclude='.venv' --exclude='__pycache__' --exclude='.git' \
    --exclude='node_modules' --exclude='.stableagent-capsule' \
    --exclude='data/' --exclude='logs/' \
    "$PROJECT_DIR/" "$INSTALL_DIR/"

# 4. 创建虚拟环境
echo "[4/7] 创建虚拟环境..."
if [ ! -d "$INSTALL_DIR/.venv" ]; then
    "$PYTHON_CMD" -m venv "$INSTALL_DIR/.venv"
fi
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements-slim.txt"

# 5. 初始化 capsule
echo "[5/7] 初始化 Agent Capsule..."
cd "$INSTALL_DIR"
PYTHONPATH="$INSTALL_DIR" "$INSTALL_DIR/.venv/bin/python" -m stable_agent.cli capsule init || true

# 6. 创建 .env.slim
echo "[6/7] 创建配置文件..."
if [ ! -f "$INSTALL_DIR/.env.slim" ]; then
    cat > "$INSTALL_DIR/.env.slim" << 'ENVEOF'
# StableAgent OS Slim Cloud Edition 配置
STABLEAGENT_PROFILE=slim
STABLEAGENT_PORT=18789
STABLEAGENT_BIND_HOST=127.0.0.1
STABLEAGENT_MAX_EVENTS=1000
STABLEAGENT_MAX_TASK_LOGS=200
STABLEAGENT_WORKER_TIMEOUT=60
# 取消注释以启用 API Token 认证:
# STABLEAGENT_CLOUD_TOKEN=your-random-token-here
ENVEOF
    echo "  已创建 .env.slim (请根据需要修改)"
else
    echo "  .env.slim 已存在，跳过"
fi

# 7. 创建 systemd service
echo "[7/7] 创建 systemd service..."
cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=StableAgent OS Slim Cloud Center
After=network.target

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env.slim
Environment=PYTHONPATH=${INSTALL_DIR}
Environment=STABLEAGENT_PROFILE=slim
ExecStart=${INSTALL_DIR}/.venv/bin/python -m stable_agent.cli serve --host 127.0.0.1 --port ${PORT} --profile slim
Restart=always
RestartSec=5
MemoryMax=1200M
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo ""
echo "=========================================="
echo "部署完成！"
echo "=========================================="
echo ""
echo "启动服务:"
echo "  systemctl start ${SERVICE_NAME}"
echo "  systemctl status ${SERVICE_NAME}"
echo ""
echo "查看日志:"
echo "  journalctl -u ${SERVICE_NAME} -f"
echo ""
echo "SSH Tunnel (本地访问):"
echo "  ssh -fN -i \"your-key.pem\" \\"
echo "    -o IdentitiesOnly=yes \\"
echo "    -o ExitOnForwardFailure=yes \\"
echo "    -L ${PORT}:127.0.0.1:${PORT} \\"
echo "    root@YOUR_SERVER_IP"
echo ""
echo "本地浏览器访问:"
echo "  http://127.0.0.1:${PORT}/slim"
echo ""
echo "健康检查:"
echo "  curl http://127.0.0.1:${PORT}/api/cloud/health"
echo ""
