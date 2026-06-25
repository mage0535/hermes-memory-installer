#!/usr/bin/env python3
"""
Memory Reflection Pipeline
- Weekly: use Hindsight.reflect() to synthesize insights
- Archive reflection to gbrain via tool CLI
- Calls Hindsight reflect to auto-generate persona/scene summaries
"""
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", os.environ.get("AGENT_HOME", "~/.agent"))).expanduser()
sys.path.insert(0, str(HERMES_HOME / "hermes-agent"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(HERMES_HOME / "logs" / "memory_reflect.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("memory_reflect")


def _call_gbrain(slug: str, content: str) -> bool:
    """Archive to gbrain via gbrain CLI tool."""
    try:
        # Write content to temp file and use gbrain put
        tmp = Path(f"/tmp/gbrain_{slug}.md")
        tmp.write_text(content)
        
        result = subprocess.run(
            ["gbrain", "put", slug, str(tmp)],
            capture_output=True, text=True, timeout=30
        )
        tmp.unlink(missing_ok=True)
        
        if result.returncode == 0:
            logger.info(f"gbrain archive '{slug}' OK")
            return True
        else:
            logger.warning(f"gbrain archive failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        logger.warning(f"gbrain archive error: {e}")
        return False


def reflect():
    """Run Hindsight reflect and archive results."""
    try:
        from hindsight_client import Hindsight
    except ModuleNotFoundError as exc:
        logger.error("Hermes-only dependency missing: %s", exc)
        return False
    
    h = Hindsight(base_url="http://localhost:8890", api_key=None, timeout=120)
    
    logger.info("Running Hindsight reflect...")
    try:
        result = h.reflect(
            bank_id="hermes",
            query="What patterns, preferences, and key facts should I remember about this user?"
        )
        reflection_text = str(result.text) if hasattr(result, 'text') else str(result)
        logger.info(f"Reflection generated ({len(reflection_text)} chars)")
        
        # Archive to gbrain
        today = datetime.now().strftime('%Y%m%d')
        page_content = f"""---
type: report
tags: [memory, reflect, auto, {today}]
---

# Memory Reflection - {today}

Auto-generated from Hindsight reflect.

{reflection_text}

---
_Source: Hindsight.reflect() | bank=hermes_
"""
        _call_gbrain(f"memory-reflect-{today}", page_content)
        
    except Exception as e:
        logger.error(f"Reflect failed: {e}")
        return False
    
    h.close()
    return True


if __name__ == "__main__":
    success = reflect()
    sys.exit(0 if success else 1)
