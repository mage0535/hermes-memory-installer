"""Config patcher for Memory 2.0.

Patches Hermes config.yaml with memory skill entries and defaults.
Auto-detects the correct .hermes path via $HOME (not hard-coded /root/).
"""
import os
import yaml
from pathlib import Path

# Default memory entries to inject into config.yaml
DEFAULT_MEMORY_ENTRIES = {
    "memory_char_limit": 2200,
    "user_char_limit": 1375,
}

DEFAULT_SKILLS = [
    "memory-starter-kit",
    "memory-archivist",
    "memory-proactive",
]

DEFAULT_MCP = {
    "gbrain": {
        "command": "$HOME/.bun/bin/bun",
        "args": ["$HOME/.bun/bin/gbrain", "serve"],
        "timeout": 120,
        "connect_timeout": 60,
    }
}


def patch(config_path=None):
    """Apply Memory 2.0 config patches."""
    if config_path is None:
        home = Path.home()
        config_path = home / ".hermes" / "config.yaml"
    
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        return False
    
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}
    
    changed = False
    
    # Inject memory limits
    for key, val in DEFAULT_MEMORY_ENTRIES.items():
        if key not in config or config[key] != val:
            config[key] = val
            changed = True
            print(f"  Set {key} = {val}")
    
    # Inject skills
    skills = config.get("skills", [])
    for skill in DEFAULT_SKILLS:
        if skill not in skills:
            skills.append(skill)
            changed = True
            print(f"  Added skill: {skill}")
    config["skills"] = skills
    
    # Inject gbrain MCP config
    mcp = config.get("mcp_servers", {})
    if "gbrain" not in mcp:
        home = Path.home()
        mcp["gbrain"] = {
            "command": str(home / ".bun" / "bin" / "bun"),
            "args": [str(home / ".bun" / "bin" / "gbrain"), "serve"],
            "timeout": 120,
            "connect_timeout": 60,
        }
        changed = True
        print(f"  Added gbrain MCP config")
    config["mcp_servers"] = mcp
    
    if changed:
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        print(f"Config patched: {config_path}")
    else:
        print("No changes needed")
    
    return changed


if __name__ == "__main__":
    patch()
