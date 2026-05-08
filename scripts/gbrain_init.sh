#!/usr/bin/env bash
# gbrain + Postgres 完整初始化脚本
# 用法: bash scripts/gbrain_init.sh [--pglite|--postgres] [--embed]
set -euo pipefail

MODE="${1:---pglite}"
INSTALL_EMBED="${2:-}"
GBRAIN_DIR="${GBRAIN_DIR:-$HOME/gbrain}"
BUN_BIN="${BUN_BIN:-$HOME/.bun/bin/bun}"
GBRAIN_BIN="${GBRAIN_BIN:-$HOME/.bun/bin/gbrain}"
LOG_FILE="/tmp/gbrain_init.log"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[+]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
err()   { echo -e "${RED}[-]${NC} $*"; }

check_bun() {
  if ! command -v bun &>/dev/null && [[ ! -f "$BUN_BIN" ]]; then
    info "安装 Bun..."
    curl -fsSL https://bun.sh/install | bash
    export PATH="$HOME/.bun/bin:$PATH"
  fi
  info "Bun: $(bun --version 2>/dev/null || echo ok)"
}

install_gbrain() {
  if [[ -d "$GBRAIN_DIR" ]]; then
    info "gbrain 已安装于 $GBRAIN_DIR"
    return
  fi
  info "克隆 gbrain..."
  git clone https://github.com/garrytan/gbrain.git "$GBRAIN_DIR"
  cd "$GBRAIN_DIR"
  info "安装依赖..."
  bun install
  info "gbrain 安装完成"
}

setup_postgres() {
  if [[ "$MODE" != "--postgres" ]]; then
    info "使用 PGLite（零配置），跳过 Postgres 安装"
    return
  fi
  info "配置 PostgreSQL..."
  if ! command -v psql &>/dev/null; then
    apt-get update -qq && apt-get install -y -qq postgresql postgresql-contrib
  fi
  if ! pg_isready -q 2>/dev/null; then
    pg_ctlcluster $(pg_lsclusters -h | head -1 | awk '{print $1" "$2}') start 2>/dev/null || systemctl start postgresql
    sleep 2
  fi
  if ! sudo -u postgres psql -t -c "SELECT 1 FROM pg_roles WHERE rolname='gbrain'" | grep -q 1; then
    sudo -u postgres psql -c "CREATE USER gbrain WITH PASSWORD 'gbrain_local_only';"
    sudo -u postgres psql -c "CREATE DATABASE gbrain OWNER gbrain;"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE gbrain TO gbrain;"
  fi
  sudo -u postgres psql -d gbrain -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || true
  info "PostgreSQL 就绪: postgresql://gbrain:gbrain_local_only@127.0.0.1:5432/gbrain"
}

init_gbrain_brain() {
  cd "$GBRAIN_DIR"
  if gbrain config &>/dev/null; then
    info "gbrain 已初始化，跳过"
    return
  fi
  if [[ "$MODE" == "--postgres" ]]; then
    DATABASE_URL="postgresql://gbrain:gbrain_local_only@127.0.0.1:5432/gbrain" gbrain init --url "$DATABASE_URL"
  else
    gbrain init  # PGLite, zero-config
  fi
  info "gbrain 知识图谱初始化完成"
}

setup_mcp() {
  if grep -q "gbrain" "$HOME/.hermes/config.yaml" 2>/dev/null; then
    info "gbrain MCP 已配置"
    return
  fi
  info "添加 gbrain MCP 到 Gateway..."
  python3 -c "
import yaml
from pathlib import Path
c = Path.home() / '.hermes' / 'config.yaml'
d = yaml.safe_load(c.read_text()) or {}
d.setdefault('mcp_servers', {})['gbrain'] = {
    'command': str(Path.home() / '.bun' / 'bin' / 'bun'),
    'args': [str(Path.home() / '.bun' / 'bin' / 'gbrain'), 'serve'],
    'timeout': 120, 'connect_timeout': 60
}
c.write_text(yaml.dump(d, default_flow_style=False, allow_unicode=True))
print('OK')
"
}

verify() {
  echo ""
  info "验证..."
  gbrain doctor --fast 2>/dev/null && info "✅ 健康检查通过" || warn "⚠️ 健康检查异常"
}


setup_embedding_server() {
    info "设置多语言嵌入服务器 (BAAI/bge-small-zh-v1.5, 512d, 中英双语)..."
    
    if ! python3 -c "import sentence_transformers" 2>/dev/null; then
        info "安装 sentence-transformers..."
        pip3 install sentence-transformers 2>/dev/null || pip3 install --break-system-packages sentence-transformers
    fi
    
    mkdir -p "$HOME/gbrain"
    if [ -f "scripts/embedding_server.py" ]; then
        cp scripts/embedding_server.py "$HOME/gbrain/embedding_server.py"
    fi
    chmod +x "$HOME/gbrain/embedding_server.py"
    
    if systemctl --version &>/dev/null; then
        cat > /tmp/hermes-embedding.service << UNIT
[Unit]
Description=Hermes Multi-language Embedding Server (BAAI/bge-small-zh-v1.5)
After=network.target
[Service]
Type=simple
Environment=EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
ExecStart=python3 "$HOME"/gbrain/embedding_server.py
Restart=on-failure
RestartSec=10
[Install]
WantedBy=multi-user.target
UNIT
        sudo mv /tmp/hermes-embedding.service /etc/systemd/system/hermes-embedding.service
        sudo systemctl daemon-reload
        sudo systemctl enable hermes-embedding
        sudo systemctl start hermes-embedding
        ok "嵌入服务器已启动 (systemd)"
    else
        nohup python3 "$HOME/gbrain/embedding_server.py" > /tmp/embedding_server.log 2>&1 &
        ok "嵌入服务器已后台启动 (PID: $!)"
    fi
    
    sleep 3
    if curl -s -X POST http://127.0.0.1:8766/v1/embeddings         -H "Content-Type: application/json"         -d '{"input":["test"],"model":"BAAI/bge-small-zh-v1.5"}' | grep -q embedding; then
        ok "嵌入服务器验证成功 (port 8766, 512d multilingual)"
    else
        warn "嵌入服务器响应异常，检查 /tmp/embedding_server.log"
    fi
}

echo "═══════════════════════════════════════════════"
echo "  gbrain + Postgres 初始化脚本"
echo "  模式: $MODE"

setup_embedding_server() {
    info "设置多语言嵌入服务器 (BAAI/bge-small-zh-v1.5, 512d, 中英双语)..."
    
    if ! python3 -c "import sentence_transformers" 2>/dev/null; then
        info "安装 sentence-transformers..."
        pip3 install sentence-transformers 2>/dev/null || pip3 install --break-system-packages sentence-transformers
    fi
    
    mkdir -p "$HOME/gbrain"
    if [ -f "scripts/embedding_server.py" ]; then
        cp scripts/embedding_server.py "$HOME/gbrain/embedding_server.py"
    fi
    chmod +x "$HOME/gbrain/embedding_server.py"
    
    if systemctl --version &>/dev/null; then
        cat > /tmp/hermes-embedding.service << UNIT
[Unit]
Description=Hermes Multi-language Embedding Server (BAAI/bge-small-zh-v1.5)
After=network.target
[Service]
Type=simple
Environment=EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
ExecStart=python3 "$HOME"/gbrain/embedding_server.py
Restart=on-failure
RestartSec=10
[Install]
WantedBy=multi-user.target
UNIT
        sudo mv /tmp/hermes-embedding.service /etc/systemd/system/hermes-embedding.service
        sudo systemctl daemon-reload
        sudo systemctl enable hermes-embedding
        sudo systemctl start hermes-embedding
        ok "嵌入服务器已启动 (systemd)"
    else
        nohup python3 "$HOME/gbrain/embedding_server.py" > /tmp/embedding_server.log 2>&1 &
        ok "嵌入服务器已后台启动 (PID: $!)"
    fi
    
    sleep 3
    if curl -s -X POST http://127.0.0.1:8766/v1/embeddings         -H "Content-Type: application/json"         -d '{"input":["test"],"model":"BAAI/bge-small-zh-v1.5"}' | grep -q embedding; then
        ok "嵌入服务器验证成功 (port 8766, 512d multilingual)"
    else
        warn "嵌入服务器响应异常，检查 /tmp/embedding_server.log"
    fi
}

echo "═══════════════════════════════════════════════"
check_bun
install_gbrain
setup_postgres
init_gbrain_brain
setup_mcp
verify

if [[ "$MODE" != "--embed" && "$INSTALL_EMBED" == "--embed" ]]; then
    setup_embedding_server
fi

echo ""
echo "✅ 完成！重启 Gateway 加载 gbrain MCP:"
echo "   systemctl restart hermes-gateway"
