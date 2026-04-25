#!/bin/bash
#
# Hermes Memory Installer - 一键安装脚本
# 使用: curl -fsSL https://your-domain.com/install.sh | bash
#     或 bash install.sh
#

set -euo pipefail

readonly VERSION="0.1.0"
readonly REPO_URL="https://github.com/yourname/hermes-memory-installer"
readonly INSTALL_DIR="/tmp/hermes-memory-installer-$$"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}ℹ️${NC}  $1"; }
log_ok()    { echo -e "${GREEN}✅${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}⚠️${NC}  $1"; }
log_error() { echo -e "${RED}❌${NC}  $1"; }

banner() {
    cat <<'EOF'
 _   _                                          __  __
| | | | ___ _ __ ___   ___  _ __   ___ _   _   |  \/  | ___  ___ ___  __ _  __ _  ___ _ __
| |_| |/ _ \ '_ ` _ \ / _ \| '_ \ / _ \ | | |  | |\/| |/ _ \/ __/ _ \/ _` |/ _` |/ _ \ '__|
|  _  |  __/ | | | | | (_) | | | |  __/ |_| |  | |  | |  __/ (_|  __/ (_| | (_| |  __/ |
|_| |_|\___|_| |_| |_|\___/|_| |_|\___|\__, |  |_|  |_|\___|\___\___|\__, |\__, |\___|_|
                                      |___/                        |___/ |___/
EOF
    echo ""
    echo "  版本: v${VERSION} | 一键搭建 Hermes 综合记忆管理体系"
    echo ""
}

cleanup() {
    if [[ -d "${INSTALL_DIR}" ]]; then
        rm -rf "${INSTALL_DIR}"
    fi
}
trap cleanup EXIT

check_hermes() {
    log_info "检查 Hermes 安装..."
    if [[ ! -d "${HOME}/.hermes" ]]; then
        log_error "未找到 ~/.hermes 目录，请先安装 Hermes Agent"
        exit 1
    fi
    log_ok "Hermes 已安装"
}

check_python() {
    log_info "检查 Python 版本..."
    PYTHON_CMD=""
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            version=$($cmd -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            major=$(echo "$version" | cut -d. -f1)
            minor=$(echo "$version" | cut -d. -f2)
            if [[ "$major" -ge 3 && "$minor" -ge 9 ]]; then
                PYTHON_CMD="$cmd"
                break
            fi
        fi
    done

    if [[ -z "$PYTHON_CMD" ]]; then
        log_error "需要 Python >= 3.9，当前环境不满足"
        exit 1
    fi
    log_ok "Python 版本: $($PYTHON_CMD --version)"
}

check_sqlite() {
    log_info "检查 SQLite FTS5 支持..."
    if ! $PYTHON_CMD -c "import sqlite3; conn = sqlite3.connect(':memory:'); conn.execute('CREATE VIRTUAL TABLE test USING fts5(content)'); conn.close()" 2>/dev/null; then
        log_warn "SQLite 不支持 FTS5，部分功能可能受限"
        read -p "是否继续安装? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        log_ok "SQLite FTS5 支持检测通过"
    fi
}

backup_config() {
    log_info "备份现有配置..."
    local config="${HOME}/.hermes/config.yaml"
    if [[ -f "$config" ]]; then
        local backup="${config}.pre-memory-$(date +%Y%m%d-%H%M%S)"
        cp "$config" "$backup"
        log_ok "已备份至: ${backup}"
    fi
}

download_installer() {
    log_info "下载安装包..."

    # 检测是否在当前目录下直接运行
    if [[ -f "$(dirname "$0")/installer/install.py" ]]; then
        INSTALLER_DIR="$(dirname "$0")"
        log_ok "检测到本地安装包"
        return
    fi

    # 尝试从 GitHub 下载
    mkdir -p "$INSTALL_DIR"
    local download_url="${REPO_URL}/archive/refs/tags/v${VERSION}.tar.gz"

    if command -v curl &>/dev/null; then
        curl -fsSL "$download_url" -o "${INSTALL_DIR}/installer.tar.gz" 2>/dev/null || true
    elif command -v wget &>/dev/null; then
        wget -q "$download_url" -O "${INSTALL_DIR}/installer.tar.gz" 2>/dev/null || true
    fi

    if [[ -f "${INSTALL_DIR}/installer.tar.gz" ]]; then
        tar -xzf "${INSTALL_DIR}/installer.tar.gz" -C "$INSTALL_DIR" --strip-components=1
        INSTALLER_DIR="$INSTALL_DIR"
        log_ok "安装包下载完成"
    else
        log_warn "无法下载远程安装包，将使用内置简化版"
        create_minimal_installer
    fi
}

create_minimal_installer() {
    # 离线模式：创建最小可运行环境
    mkdir -p "$INSTALL_DIR"
    INSTALLER_DIR="$INSTALL_DIR"

    # 创建基础目录
    mkdir -p "${HOME}/.hermes/archives/"{people,projects,knowledge,_index}

    # 创建简化的 pool.db
    $PYTHON_CMD -c "
import sqlite3, os
db = os.path.expanduser('~/.hermes/pool.db')
conn = sqlite3.connect(db)
conn.executescript('''
CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY, session_id TEXT, timestamp REAL DEFAULT (julianday(\"now\")), role TEXT, content TEXT, topic_tags TEXT, archived INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, start_time REAL DEFAULT (julianday(\"now\")), title TEXT, summary TEXT, archived INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS archives (id INTEGER PRIMARY KEY, path TEXT UNIQUE, type TEXT, title TEXT, summary TEXT, tags TEXT, last_read REAL, priority INTEGER DEFAULT 0);
CREATE VIRTUAL TABLE IF NOT EXISTS archives_fts USING fts5(title, summary, tags, content=archives, content_rowid=id);
CREATE TRIGGER IF NOT EXISTS archives_ai AFTER INSERT ON archives BEGIN INSERT INTO archives_fts(rowid, title, summary, tags) VALUES (new.id, new.title, new.summary, new.tags); END;
CREATE INDEX IF NOT EXISTS idx_archives_type ON archives(type, priority DESC);
''')
conn.commit()
conn.close()
print('✅ pool.db 初始化完成')
"

    log_ok "最小环境初始化完成"
}

run_installer() {
    log_info "执行安装程序..."

    if [[ -f "${INSTALLER_DIR}/installer/install.py" ]]; then
        $PYTHON_CMD "${INSTALLER_DIR}/installer/install.py"
    else
        # 简化模式：手动安装核心组件
        install_skills_minimal
    fi
}

install_skills_minimal() {
    log_info "安装 Skill 套件..."

    local skills_dir="${HOME}/.hermes/skills"
    mkdir -p "$skills_dir"

    # 如果本地有 skills 目录，复制过去
    if [[ -d "${INSTALLER_DIR}/skills" ]]; then
        for skill in memory-starter-kit memory-archivist; do
            local src="${INSTALLER_DIR}/skills/${skill}"
            local dst="${skills_dir}/${skill}"
            if [[ -d "$src" && ! -d "$dst" ]]; then
                cp -r "$src" "$dst"
                log_ok "安装 Skill: ${skill}"
            fi
        done
    fi

    # 如果本地有模板，复制过去
    if [[ -d "${INSTALLER_DIR}/templates" ]]; then
        local tpl_dir="${skills_dir}/memory-starter-kit/templates"
        mkdir -p "$tpl_dir"
        cp -r "${INSTALLER_DIR}/templates/"*.j2 "$tpl_dir/" 2>/dev/null || true
    fi
}

patch_config() {
    log_info "修改 Hermes 配置..."

    local config="${HOME}/.hermes/config.yaml"
    if [[ ! -f "$config" ]]; then
        log_warn "未找到 config.yaml，请手动添加 skills"
        return
    fi

    # 使用 Python 安全修改配置
    $PYTHON_CMD -c "
import sys, os
config_path = os.path.expanduser('~/.hermes/config.yaml')

try:
    from ruamel.yaml import YAML
    yaml = YAML()
    yaml.preserve_quotes = True
    with open(config_path, 'r') as f:
        data = yaml.load(f) or {}
except ImportError:
    import yaml
    with open(config_path, 'r') as f:
        data = yaml.safe_load(f) or {}

if 'skills' not in data or not isinstance(data['skills'], list):
    data['skills'] = []

existing = set(data['skills'])
new_skills = ['memory-starter-kit', 'memory-archivist']
added = []
for s in new_skills:
    if s not in existing:
        data['skills'].append(s)
        added.append(s)

try:
    from ruamel.yaml import YAML
    yaml = YAML()
    yaml.default_flow_style = False
    with open(config_path, 'w') as f:
        yaml.dump(data, f)
except ImportError:
    import yaml
    with open(config_path, 'w') as f:
        yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)

if added:
    joined = ', '.join(added)
    print(f'✅ 已添加 Skills: {joined}')
else:
    print('✅ Skills 已存在')
"
}

verify_installation() {
    log_info "验证安装..."
    local all_ok=true

    local checks=(
        "${HOME}/.hermes/archives"
        "${HOME}/.hermes/pool.db"
        "${HOME}/.hermes/skills/memory-starter-kit"
    )

    for path in "${checks[@]}"; do
        if [[ -e "$path" ]]; then
            log_ok "$(basename "$path") 已创建"
        else
            log_error "$(basename "$path") 未找到"
            all_ok=false
        fi
    done

    if $all_ok; then
        return 0
    else
        return 1
    fi
}

print_next_steps() {
    echo ""
    echo "═════════════════════════════════════════════════════════════════════"
    echo "  ${GREEN}🎉 安装成功！${NC}"
    echo ""
    echo "  下一步:"
    echo "  1. 重启 Hermes Gateway 使配置生效"
    echo "  2. 创建第一个档案:"
    echo "     cp ~/.hermes/skills/memory-starter-kit/templates/person.md.j2 \\"
    echo "        ~/.hermes/archives/people/你的名字/profile.md"
    echo "  3. 查看使用指南:"
    echo "     cat ~/.hermes/skills/memory-starter-kit/SKILL.md"
    echo ""
    echo "  高级功能（可选）:"
    echo "  • 安装 memory-proactive (自动上下文路由):"
    echo "    cp -r skills/memory-proactive ~/.hermes/skills/"
    echo "  • 配置自动归档 cronjob:"
    echo "    cat ~/.hermes/skills/memory-archivist/SKILL.md"
    echo ""
    echo "═════════════════════════════════════════════════════════════════════"
}

main() {
    banner

    # 解析参数
    DRY_RUN=false
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --version|-v)
                echo "v${VERSION}"
                exit 0
                ;;
            --help|-h)
                echo "使用: $0 [--dry-run] [--version] [--help]"
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                exit 1
                ;;
        esac
    done

    if $DRY_RUN; then
        log_warn "演示模式: 仅检测，不会修改系统"
    fi

    check_hermes
    check_python
    check_sqlite
    backup_config
    download_installer

    if ! $DRY_RUN; then
        run_installer
        patch_config
    else
        log_info "[演示] 跳过实际安装"
    fi

    verify_installation
    print_next_steps
}

main "$@"
