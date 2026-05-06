#!/bin/bash
# Hermes Memory Installer 2.0 — 一键安装脚本（含 gbrain+Postgres 可选部署）
set -euo pipefail

readonly VERSION="2.0.0"
INSTALL_DIR="/tmp/hermes-memory-installer-$$"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}ℹ️${NC}  $1"; }
ok()    { echo -e "${GREEN}✅${NC}  $1"; }
warn()  { echo -e "${YELLOW}⚠️${NC}  $1"; }
err()   { echo -e "${RED}❌${NC}  $1"; }

cleanup() { [[ -d "$INSTALL_DIR" ]] && rm -rf "$INSTALL_DIR"; }
trap cleanup EXIT

banner() {
    cat <<'BANNER'
 _   _                                          __  __
| | | | ___ _ __ ___   ___  _ __   ___ _   _   |  \/  | ___  ___ ___  __ _  __ _  ___ _ __
| |_| |/ _ \ '_ ` _ \ / _ \| '_ \ / _ \ | | |  | |\/| |/ _ \/ __/ _ \/ _` |/ _` |/ _ \ '__|
|  _  |  __/ | | | | | (_) | | | |  __/ |_| |  | |  | |  __/ (_|  __/ (_| | (_| |  __/ |
|_| |_|\___|_| |_| |_|\___/|_| |_|\___|\__, |  |_|  |_|\___|\___\___|\__, |\__, |\___|_|
                                      |___/                        |___/ |___/
  版本: v${VERSION} | 记忆体2.0 — AI长期记忆系统（含 gbrain 知识图谱）
BANNER
}

check_env() {
    info "检查环境..."
    if [[ ! -d "${HOME}/.hermes" ]]; then err "~/.hermes 不存在，请先安装 Hermes Agent"; exit 1; fi
    ok "Hermes Agent 已安装"

    PYTHON_CMD=""
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            v=$($cmd -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            m=$(echo "$v" | cut -d. -f1); n=$(echo "$v" | cut -d. -f2)
            if [[ "$m" -ge 3 && "$n" -ge 9 ]]; then PYTHON_CMD="$cmd"; break; fi
        fi
    done
    if [[ -z "$PYTHON_CMD" ]]; then err "需要 Python >= 3.9"; exit 1; fi
    ok "Python: $($PYTHON_CMD --version)"

    if $PYTHON_CMD -c "import sqlite3; conn=sqlite3.connect(':memory:'); conn.execute('CREATE VIRTUAL TABLE t USING fts5(c)'); conn.close()" 2>/dev/null; then
        ok "SQLite FTS5 支持"
    else
        warn "SQLite 不支持 FTS5（部分功能受限）"
    fi
}

install_memory_base() {
    info "安装记忆体基础组件..."
    mkdir -p "${HOME}/.hermes/archives/"{people,projects,knowledge,_index}
    mkdir -p "${HOME}/.hermes/scripts"

    # 初始化 pool.db
    $PYTHON_CMD -c "
import sqlite3, os
db = os.path.expanduser('~/.hermes/pool.db')
conn = sqlite3.connect(db)
conn.executescript('''
CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY, session_id TEXT, timestamp REAL, role TEXT, content TEXT, topic_tags TEXT, archived INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, start_time REAL, title TEXT, summary TEXT, archived INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS archives (id INTEGER PRIMARY KEY, path TEXT UNIQUE, type TEXT, title TEXT, summary TEXT, tags TEXT, last_read REAL, priority INTEGER DEFAULT 0);
CREATE VIRTUAL TABLE IF NOT EXISTS archives_fts USING fts5(title, summary, tags, content=archives, content_rowid=id);
CREATE TRIGGER IF NOT EXISTS archives_ai AFTER INSERT ON archives BEGIN INSERT INTO archives_fts(rowid, title, summary, tags) VALUES (new.id, new.title, new.summary, new.tags); END;
CREATE INDEX IF NOT EXISTS idx_archives_type ON archives(type, priority DESC);
''')
conn.commit(); conn.close()
"
    ok "pool.db 已初始化（FTS5 全文索引）"

    # 安装 Skills
    local src_skills="/tmp/memory-repo/skills"
    if [[ -d "$src_skills" ]]; then
        for skill in memory-starter-kit memory-archivist memory-proactive; do
            if [[ -d "$src_skills/$skill" && ! -d "${HOME}/.hermes/skills/$skill" ]]; then
                cp -r "$src_skills/$skill" "${HOME}/.hermes/skills/"
                ok "Skill 已安装: $skill"
            fi
        done
    fi

    # 安装脚本
    local src_scripts="/tmp/memory-repo/scripts"
    if [[ -d "$src_scripts" ]]; then
        cp "$src_scripts"/*.py "$src_scripts"/*.sh "${HOME}/.hermes/scripts/" 2>/dev/null || true
        ok "自动化脚本已安装"
    fi

    # 配置 config.yaml
    $PYTHON_CMD -c "
import yaml, os
config_path = os.path.expanduser('~/.hermes/config.yaml')
with open(config_path) as f: data = yaml.safe_load(f) or {}
data.setdefault('skills', [])
for s in ['memory-starter-kit', 'memory-archivist']:
    if s not in data['skills']: data['skills'].append(s)
with open(config_path, 'w') as f: yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
"
    ok "config.yaml 已更新"
}

install_gbrain() {
    echo ""
    info "是否安装 gbrain 知识图谱引擎？（推荐，增强检索能力）"
    echo "  1) 安装 gbrain + PGLite（零配置，推荐）"
    echo "  2) 安装 gbrain + PostgreSQL（生产级）"
    echo "  3) 跳过"
    read -p "请选择 [1/2/3] (默认: 1): " choice
    choice="${choice:-1}"

    case "$choice" in
        1)
            info "安装 gbrain + PGLite..."
            bash scripts/gbrain_init.sh --pglite
            ;;
        2)
            info "安装 gbrain + PostgreSQL..."
            bash scripts/gbrain_init.sh --postgres
            ;;
        *)
            warn "跳过 gbrain 安装。可后续运行: bash scripts/gbrain_init.sh"
            return
            ;;
    esac
}

setup_automation() {
    echo ""
    info "配置自动化定时任务..."

    # 检测 Hermes cron 或系统 cron
    if command -v hermes &>/dev/null && hermes cron list &>/dev/null; then
        info "使用 Hermes 内置 cron..."
        # 每日归档
        hermes cron create "0 3 * * *" \
            --name "session-gbrain-archive" \
            --prompt "Run archive_sessions.py to archive old sessions to gbrain" \
            --script scripts/archive_sessions.py \
            --deliver origin 2>/dev/null || true
        # 每日 gbrain 维护
        hermes cron create "0 4 * * *" \
            --name "gbrain-daily-maintenance" \
            --prompt "Run gbrain maintenance" \
            --script scripts/gbrain_maintain.sh \
            --deliver origin 2>/dev/null || true
        # 每 2h 增量索引
        hermes cron create "every 120m" \
            --name "Session→Gbrain增量索引" \
            --prompt "Incremental session to gbrain indexing" \
            --script scripts/archive_sessions.py \
            --deliver origin 2>/dev/null || true
        ok "Hermes cron 任务已创建"
    else
        info "使用系统 cron..."
        (crontab -l 2>/dev/null || true) > /tmp/cron.tmp
        echo "# Memory 2.0 automation" >> /tmp/cron.tmp
        echo "0 3 * * * cd ${HOME}/.hermes/scripts && python3 archive_sessions.py --days 7 --batch 15" >> /tmp/cron.tmp
        echo "0 4 * * * bash ${HOME}/.hermes/scripts/gbrain_maintain.sh" >> /tmp/cron.tmp
        echo "0 */12 * * * cd ${HOME}/.hermes/scripts && python3 auto_session_summary.py" >> /tmp/cron.tmp
        crontab /tmp/cron.tmp
        rm /tmp/cron.tmp
        ok "系统 cron 任务已创建"
    fi
}

verify() {
    echo ""
    info "验证安装..."
    local ok_count=0; local total=4

    [[ -d "${HOME}/.hermes/archives" ]] && { ok "archive 目录"; ((ok_count++)); } || warn "archive 目录缺失"
    [[ -f "${HOME}/.hermes/pool.db" ]] && { ok "pool.db"; ((ok_count++)); } || warn "pool.db 缺失"
    [[ -d "${HOME}/.hermes/skills/memory-starter-kit" ]] && { ok "memory-starter-kit"; ((ok_count++)); } || warn "memory-starter-kit 缺失"
    if command -v gbrain &>/dev/null; then
        gbrain doctor --fast &>/dev/null && { ok "gbrain 健康"; ((ok_count++)); } || warn "gbrain 异常"
    else
        warn "gbrain 未安装（可选组件）"
    fi
    echo ""
    ok "${ok_count}/${total} 检查通过"
}

show_summary() {
    echo ""
    echo "════════════════════════════════════════════════════"
    echo "  🎉 记忆体2.0 安装成功！"
    echo ""
    echo "  已安装组件:"
    echo "  ✅ 记忆体基础 (pool.db, skills, scripts)"
    [[ -d "${HOME}/.hermes/archives" ]] && echo "  ✅ 档案目录 (people/projects/knowledge)"
    command -v gbrain &>/dev/null && echo "  ✅ gbrain 知识图谱引擎"
    echo ""
    echo "  下一步操作:"
    echo "  1. 重启 Gateway: systemctl restart hermes-gateway"
    echo "  2. 创建第一个档案:"
    echo "     cp ~/.hermes/skills/memory-starter-kit/templates/person.md.j2 \\"
    echo "        ~/.hermes/archives/people/姓名/profile.md"
    echo "  3. 查看完整指南: cat ~/.hermes/skills/memory-starter-kit/SKILL.md"
    echo "  4. 手动运行归档: python3 ~/.hermes/scripts/archive_sessions.py"
    echo ""
    echo "  自动化任务:"
    echo "  • 每日 3:00   — 会话归档到 gbrain (archive_sessions.py)"
    echo "  • 每日 4:00   — gbrain 维护 (gbrain_maintain.sh)"
    echo "  • 每 12 小时  — 自动生成会话摘要 (auto_session_summary.py)"
    echo ""
    command -v gbrain &>/dev/null && echo "  gbrain 知识图谱已就绪，含 $(gbrain list -n 1 2>/dev/null | wc -l)+ 页面"
    echo "════════════════════════════════════════════════════"
}

main() {
    banner
    check_env

    # 备份
    if [[ -f "${HOME}/.hermes/config.yaml" ]]; then
        cp "${HOME}/.hermes/config.yaml" "${HOME}/.hermes/config.yaml.pre-memory-$(date +%Y%m%d)"
    fi

    install_memory_base
    install_gbrain
    setup_automation
    verify
    show_summary
}

main "$@"
