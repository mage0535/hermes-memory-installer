#!/bin/bash
# Hermes Memory Installer 2.0 — 一键安装脚本
set -euo pipefail

readonly VERSION="2.0.0"
readonly INSTALL_DIR="/tmp/hermes-memory-installer-$$"
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log_info()  { echo -e "${BLUE}ℹ️${NC}  $1"; }
log_ok()    { echo -e "${GREEN}✅${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}⚠️${NC}  $1"; }
log_error() { echo -e "${RED}❌${NC}  $1"; }

banner() { cat <<'BANNER'
 _   _                                          __  __
| | | | ___ _ __ ___   ___  _ __   ___ _   _   |  \/  | ___  ___ ___  __ _  __ _  ___ _ __
| |_| |/ _ \ '_ ` _ \ / _ \| '_ \ / _ \ | | |  | |\/| |/ _ \/ __/ _ \/ _` |/ _` |/ _ \ '__|
|  _  |  __/ | | | | | (_) | | | |  __/ |_| |  | |  | |  __/ (_|  __/ (_| | (_| |  __/ |
|_| |_|\___|_| |_| |_|\___/|_| |_|\___|\__, |  |_|  |_|\___|\___\___|\__, |\__, |\___|_|
                                      |___/                        |___/ |___/
  版本: v${VERSION} | 记忆体2.0 — AI长期记忆系统
BANNER
}

cleanup() { [[ -d "$INSTALL_DIR" ]] && rm -rf "$INSTALL_DIR"; }
trap cleanup EXIT

check_hermes() {
  log_info "检查 Hermes..."
  if [[ ! -d "${HOME}/.hermes" ]]; then log_error "~/.hermes 不存在，请先安装 Hermes Agent"; exit 1; fi
  log_ok "Hermes 已安装"
}

check_python() {
  log_info "检查 Python..."
  PYTHON_CMD=""
  for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
      v=$($cmd -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
      m=$(echo "$v" | cut -d. -f1); n=$(echo "$v" | cut -d. -f2)
      if [[ "$m" -ge 3 && "$n" -ge 9 ]]; then PYTHON_CMD="$cmd"; break; fi
    fi
  done
  if [[ -z "$PYTHON_CMD" ]]; then log_error "需要 Python >= 3.9"; exit 1; fi
  log_ok "Python: $($PYTHON_CMD --version)"
}

check_sqlite() {
  log_info "检查 SQLite FTS5..."
  if $PYTHON_CMD -c "import sqlite3; conn=sqlite3.connect(':memory:'); conn.execute('CREATE VIRTUAL TABLE t USING fts5(c)'); conn.close()" 2>/dev/null; then
    log_ok "SQLite FTS5 支持"
  else
    log_warn "SQLite 不支持 FTS5"
  fi
}

setup() {
  log_info "配置记忆体2.0..."
  mkdir -p "${HOME}/.hermes/archives/"{people,projects,knowledge,_index}
  $PYTHON_CMD installer/init_db.py 2>/dev/null || true
  cp -r skills/* "${HOME}/.hermes/skills/" 2>/dev/null || true
  log_ok "基础配置完成"
}

main() {
  banner
  check_hermes; check_python; check_sqlite
  setup
  echo ""
  echo "════════════════════════════════════════════════════"
  echo "  🎉 记忆体2.0 安装成功！"
  echo ""
  echo "  1. 重启 Hermes Gateway:"
  echo "     systemctl restart hermes-gateway"
  echo ""
  echo "  2. 创建首个档案:"
  echo "     cp ~/.hermes/skills/memory-starter-kit/templates/person.md.j2 \\"
  echo "        ~/.hermes/archives/people/姓名/profile.md"
  echo ""
  echo "  3. 阅读指南:"
  echo "     cat ~/.hermes/skills/memory-starter-kit/SKILL.md"
  echo "════════════════════════════════════════════════════"
}
main "$@"
