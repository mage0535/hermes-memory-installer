#!/bin/bash
# Hermes Memory Installer 2.2.0 — 一键安装脚本（含 gbrain+Postgres 可选部署）
set -euo pipefail

readonly VERSION="2.2.0"
INSTALL_DIR="/tmp/hermes-memory-installer-$$"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

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
  版本: v${VERSION} | 记忆体2.2.0 — AI长期记忆系统（含 gbrain 知识图谱 + 多语言嵌入引擎）
BANNER
}

detect_hermes_home() {
    if [ -d "$HOME/.hermes" ]; then
        HERMES_HOME="$HOME/.hermes"
    elif [ -d "/root/.hermes" ]; then
        HERMES_HOME="/root/.hermes"
    else
        warn "Could not auto-detect .hermes directory."
        read -p "  Path (default: $HOME/.hermes): " custom_path
        HERMES_HOME="${custom_path:-$HOME/.hermes}"
    fi
    mkdir -p "$HERMES_HOME"
    export HERMES_HOME
    if [ ! -d "$HERMES_HOME" ]; then
        err "Cannot access .hermes at: $HERMES_HOME"
        exit 1
    fi
    ok "Hermes directory: $HERMES_HOME"
    if [ "$HERMES_HOME" != "/root/.hermes" ]; then
        for f in scripts/*.sh scripts/*.py; do
            [ -f "$f" ] && grep -q "/root/.hermes" "$f" 2>/dev/null && sed -i "s|/root/.hermes|$HERMES_HOME|g" "$f" 2>/dev/null || true
        done
        ok "Paths adjusted to $HERMES_HOME"
    fi
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

# ═══════════════════════════════════════════════════════════
#  嵌入引擎模型选择
# ═══════════════════════════════════════════════════════════

# 检测是否由 AI 助手自动化运行
detect_ai_assistant() {
    # 检查 stdin 是否为 TTY
    if [[ ! -t 0 ]]; then
        return 0  # 非交互式 → AI 助手
    fi
    # 检查环境变量
    if [[ -n "${AI_ASSISTED:-}" ]] || [[ -n "${LLM_INSTALL:-}" ]]; then
        return 0
    fi
    return 1  # 正常用户
}

select_embedding_model() {
    echo ""
    echo "════════════════════════════════════════════════════"
    echo "  📊 选择嵌入引擎模型"
    echo "════════════════════════════════════════════════════"
    echo ""
    echo "  不同模型支持的语言、精度和资源消耗差异很大。"
    echo "  如果您不确定，推荐选择 1 (默认)。"
    echo ""

    # AI 助手提醒
    if detect_ai_assistant; then
        echo "  ┌─────────────────────────────────────────────────┐"
        echo "  │ ⚠️  AI 助手检测：您正通过 AI 助手进行安装     │"
        echo "  │                                                 │"
        echo "  │  请在继续之前向用户确认以下内容：               │"
        echo "  │  1. 用户需要哪种语言的检索支持？               │"
        echo "  │  2. 服务器可用磁盘和内存空间？                 │"
        echo "  │  3. 选择对应的模型编号                         │"
        echo "  │                                                 │"
        echo "  │  确认后设置环境变量继续:                        │"
        echo "  │  export EMBEDDING_MODEL=<模型ID>                │"
        echo "  │  然后重新运行此脚本                            │"
        echo "  │                                                 │"
        echo "  │  如用户已明确指定模型，按 Enter 继续            │"
        echo "  └─────────────────────────────────────────────────┘"
        echo ""
        if [[ -z "${EMBEDDING_MODEL:-}" ]]; then
            read -p "  按 Enter 键确认已与用户沟通模型选择，或 Ctrl+C 取消: " _dummy
        fi
    fi

    echo "  1) intfloat/multilingual-e5-small     ⭐ 推荐"
    echo "     384维 | 100+语言 | ~470MB | 适合全球用户"
    echo ""
    echo "  2) BAAI/bge-small-zh-v1.5             轻量中文"
    echo "     512维 | 中文优化 | ~96MB | 仅中英文"
    echo ""
    echo "  3) paraphrase-multilingual-MiniLM-L12-v2"
    echo "     384维 | 50+语言 | ~471MB | 社区成熟"
    echo ""
    echo "  4) Alibaba-NLP/gte-multilingual-base"
    echo "     768维 | 75+语言 | ~610MB | 中文精度高"
    echo ""
    echo "  5) sentence-transformers/LaBSE"
    echo "     768维 | 109语言 | ~471MB | 跨语言对齐"
    echo ""
    echo "  6) BAAI/bge-m3"
    echo "     1024维 | 100+语言 | ~2GB | 最强精度"
    echo ""
    echo "  7) 自定义（输入模型ID）"
    echo ""

    local choice
    read -p "  请选择 [1-7] (默认: 1): " choice
    choice="${choice:-1}"

    case "$choice" in
        1) EMBEDDING_MODEL="intfloat/multilingual-e5-small" ;;
        2) EMBEDDING_MODEL="BAAI/bge-small-zh-v1.5" ;;
        3) EMBEDDING_MODEL="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" ;;
        4) EMBEDDING_MODEL="Alibaba-NLP/gte-multilingual-base" ;;
        5) EMBEDDING_MODEL="sentence-transformers/LaBSE" ;;
        6) EMBEDDING_MODEL="BAAI/bge-m3" ;;
        7) read -p "  输入模型 HuggingFace ID: " EMBEDDING_MODEL ;;
        *) warn "无效选择，使用默认值"; EMBEDDING_MODEL="intfloat/multilingual-e5-small" ;;
    esac

    export EMBEDDING_MODEL
    ok "嵌入引擎模型: ${EMBEDDING_MODEL}"
}

install_memory_base() {
    info "安装记忆体基础组件..."
    mkdir -p "${HERMES_HOME}/archives/"_{people,projects,knowledge,_index}
    mkdir -p "${HERMES_HOME}/scripts"

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
    local src_skills="${SCRIPT_DIR}/skills"
    if [[ -d "$src_skills" ]]; then
        for skill in memory-starter-kit memory-archivist memory-proactive; do
            if [[ -d "$src_skills/$skill" && ! -d "${HERMES_HOME}/skills/$skill" ]]; then
                cp -r "$src_skills/$skill" "${HOME}/.hermes/skills/"
                ok "Skill 已安装: $skill"
            fi
        done
    fi

    # 安装脚本
    local src_scripts="${SCRIPT_DIR}/scripts"
    if [[ -d "$src_scripts" ]]; then
        cp "$src_scripts"/*.py "$src_scripts"/*.sh "${HERMES_HOME}/scripts/" 2>/dev/null || true
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
        hermes cron create "0 3 * * *" \
            --name "session-gbrain-archive" \
            --prompt "Run archive_sessions.py to archive old sessions to gbrain" \
            --script scripts/archive_sessions.py \
            --deliver origin 2>/dev/null || true
        hermes cron create "0 4 * * *" \
            --name "gbrain-daily-maintenance" \
            --prompt "Run gbrain maintenance" \
            --script scripts/gbrain_maintain.sh \
            --deliver origin 2>/dev/null || true
        hermes cron create "every 120m" \
            --name "Session→Gbrain增量索引" \
            --prompt "Incremental session to gbrain indexing" \
            --script scripts/archive_sessions.py \
            --deliver origin 2>/dev/null || true
        if [[ "${ENABLE_MEMORY_CONSOLIDATION_CRON:-1}" != "0" ]]; then
            if ! hermes cron list 2>/dev/null | grep -q "memory-consolidation-6h"; then
                hermes cron create "every 6h" \
                    --name "memory-consolidation-6h" \
                    --prompt "Scan recent conversation transcripts (last 6 hours). Extract durable facts not already in memory or fact_store. Save genuinely new facts only (no duplicates). Skip task progress, PR numbers, and commit SHAs. Keep only facts likely useful in 30 days, then check MEMORY.md capacity and prune stale entries if needed." \
                    --deliver origin 2>/dev/null || true
                ok "Optional cron created: memory-consolidation-6h"
            else
                info "Optional cron already exists: memory-consolidation-6h"
            fi
        fi
        ok "Hermes cron 任务已创建"
    else
        info "使用系统 cron..."
        (crontab -l 2>/dev/null || true) > /tmp/cron.tmp
        echo "# Memory 2.0 automation" >> /tmp/cron.tmp
        echo "0 3 * * * cd ${HERMES_HOME}/scripts && python3 archive_sessions.py --days 7 --batch 15" >> /tmp/cron.tmp
        echo "0 4 * * * bash ${HERMES_HOME}/scripts/gbrain_maintain.sh" >> /tmp/cron.tmp
        echo "0 */12 * * * cd ${HERMES_HOME}/scripts && python3 auto_session_summary.py" >> /tmp/cron.tmp
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
    [[ -f "${HERMES_HOME}/pool.db" ]] && { ok "pool.db"; ((ok_count++)); } || warn "pool.db 缺失"
    [[ -d "${HERMES_HOME}/skills/memory-starter-kit" ]] && { ok "memory-starter-kit"; ((ok_count++)); } || warn "memory-starter-kit 缺失"
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
    echo "  🎉 记忆体 ${VERSION} 安装成功！"
    echo ""
    echo "  已安装组件:"
    echo "  ✅ 记忆体基础 (pool.db, skills, scripts)"
    [[ -d "${HOME}/.hermes/archives" ]] && echo "  ✅ 档案目录 (people/projects/knowledge)"
    command -v gbrain &>/dev/null && echo "  ✅ gbrain 知识图谱引擎"
    echo ""
    echo "  嵌入引擎模型: ${EMBEDDING_MODEL}"
    echo ""
    echo "  下一步操作:"
    echo "  1. 重启 Gateway: systemctl restart hermes-gateway"
    echo "  2. 创建第一个档案:"
    echo "     cp ~/.hermes/skills/memory-starter-kit/templates/person.md.j2 \\"
    echo "        ${HERMES_HOME}/archives/people/姓名/profile.md"
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
    detect_hermes_home
    check_env
    select_embedding_model

    # 备份
    if [[ -f "${HERMES_HOME}/config.yaml" ]]; then
        cp "${HERMES_HOME}/config.yaml" "${HOME}/.hermes/config.yaml.pre-memory-$(date +%Y%m%d)"
    fi

    install_memory_base
    install_gbrain
    setup_automation
    verify
    show_summary
}

main "$@"
