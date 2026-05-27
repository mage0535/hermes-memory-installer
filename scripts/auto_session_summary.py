#!/usr/bin/env python3
"""auto-session-summary cron 任务直接执行脚本

每次运行最多处理 2 个会话，每会话 45s 硬超时（子进程隔离）。
剩余的留待下次 4h 轮次继续。
"""
import sys
import os
import subprocess
import logging
from pathlib import Path

sys.path.insert(0, '/root/.hermes/hermes-agent')

from dotenv import dotenv_values
env_vals = dotenv_values('/root/.hermes/.env')
for k, v in env_vals.items():
    if k.endswith('_API_KEY') or k.endswith('_BASE_URL'):
        os.environ[k] = v

from hermes_state import SessionDB

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

BATCH_LIMIT = 2
PER_SESSION_TIMEOUT = 45
WORKER_SCRIPT = '/root/.hermes/scripts/_summary_worker.py'

# Summary filter config
MIN_MESSAGES = 3
MIN_TOKENS = 100
TRIVIAL_PATTERNS = ['ok', 'thanks', '好的', '谢谢', '收到', '嗯', '好', '行', '知道了', '明白', '👍', 'okay', 'ok']

def should_summarize(session_id, message_count, total_tokens, title=''):
    """过滤 trivial 会话，节省 token 消耗"""
    if message_count < MIN_MESSAGES:
        logger.debug(f'  跳过 {session_id}: 消息数 {message_count} < {MIN_MESSAGES}')
        return False
    if total_tokens < MIN_TOKENS:
        logger.debug(f'  跳过 {session_id}: tokens {total_tokens} < {MIN_TOKENS}')
        return False
    if title and title.strip().lower() in TRIVIAL_PATTERNS:
        logger.debug(f'  跳过 {session_id}: trivial title')
        return False
    return True


def main():
    db_path = '/root/.hermes/state.db'
    db = SessionDB(Path(db_path))
    conn = db._conn
    cur = conn.cursor()
    cur.execute("""
        SELECT s.id, s.message_count, 
               COALESCE(s.input_tokens, 0) + COALESCE(s.output_tokens, 0) as total_tokens,
               COALESCE(s.title, '') as title
        FROM sessions s
        WHERE s.ended_at IS NOT NULL
          AND s.summary IS NULL
          AND s.id NOT LIKE 'cron_%%'
          AND s.message_count >= ?
          AND (COALESCE(s.input_tokens, 0) + COALESCE(s.output_tokens, 0)) >= ?
        ORDER BY s.ended_at DESC
        LIMIT ?
    """, (MIN_MESSAGES, MIN_TOKENS, BATCH_LIMIT))
    candidates = cur.fetchall()
    sessions = [row[0] for row in candidates if should_summarize(row[0], row[1], row[2], row[3] or '')]

    if not sessions:
        logger.info("[SILENT] 没有需要摘要的会话")
        print("[SILENT]")
        return

    dotenv_path = str(Path('/root/.hermes/.env').resolve())

    success = 0
    fail = 0
    for sid in sessions:
        logger.info(f"处理 {sid}...")
        try:
            cp = subprocess.run(
                [sys.executable, WORKER_SCRIPT, sid, dotenv_path],
                capture_output=True, text=True,
                timeout=PER_SESSION_TIMEOUT,
            )
            if cp.returncode == 0:
                logger.info(f"  ✓ {sid}")
                success += 1
            else:
                logger.warning(f"  ✗ {sid} (exit={cp.returncode}): {cp.stderr.strip()[-200:]}")
                fail += 1
        except subprocess.TimeoutExpired:
            logger.warning(f"  ✗ {sid} 超时 ({PER_SESSION_TIMEOUT}s)")
            fail += 1

    cur.execute("""
        SELECT COUNT(*) FROM sessions 
        WHERE ended_at IS NOT NULL AND summary IS NULL 
          AND id NOT LIKE 'cron_%%'
          AND message_count >= ?
          AND (COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)) >= ?
    """, (MIN_MESSAGES, MIN_TOKENS))
    remaining = cur.fetchone()[0]
    total_pending_before = len(candidates)
    logger.info(f"本轮: {success}成功/{fail}失败, 筛选前 {total_pending_before} 候选, 剩余待摘要: {remaining}")

    if remaining > 0:
        print(f"Remaining: {remaining} sessions need summary (will process next run)")


if __name__ == '__main__':
    main()
