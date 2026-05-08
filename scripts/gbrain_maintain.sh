#!/usr/bin/env bash
# gbrain 每日维护脚本
# 功能: 提取链接、提取时间轴、健康检查、重新索引
set -uo pipefail

PATH="$HOME/.bun/bin:$PATH"
GBRAIN="gbrain"
LOG_FILE="/tmp/gbrain_maintain.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] gbrain 维护开始" | tee -a "$LOG_FILE"

# 1. 提取链接
echo "🔗 提取链接..." | tee -a "$LOG_FILE"
timeout 120 ${GBRAIN} extract links --source db 2>&1 | tee -a "$LOG_FILE" || echo "⚠️ 链接提取超时（跳过）" | tee -a "$LOG_FILE"

# 2. 提取时间轴
echo "📅 提取时间轴..." | tee -a "$LOG_FILE"
timeout 120 ${GBRAIN} extract timeline --source db 2>&1 | tee -a "$LOG_FILE" || echo "⚠️ 时间轴提取超时（跳过）" | tee -a "$LOG_FILE"

# 3. 重新索引嵌入
echo "🔃 重新索引嵌入..." | tee -a "$LOG_FILE"
timeout 300 ${GBRAIN} embed --reindex 2>&1 | tee -a "$LOG_FILE" || echo "⚠️ 嵌入索引超时（跳过）" | tee -a "$LOG_FILE"

# 4. 健康检查
echo "🏥 健康检查..." | tee -a "$LOG_FILE"
${GBRAIN} doctor --fast 2>&1 | tee -a "$LOG_FILE" || echo "⚠️ 健康检查异常" | tee -a "$LOG_FILE"

# 5. 孤儿页面统计
echo "📊 孤儿页面统计..." | tee -a "$LOG_FILE"
${GBRAIN} orphans 2>&1 | tail -5 | tee -a "$LOG_FILE" || true

echo "✅ gbrain 维护完成" | tee -a "$LOG_FILE"
