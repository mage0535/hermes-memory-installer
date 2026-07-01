import os


def consolidate():
    value = os.getenv("MTM_ENABLED", "false").lower()
    if value not in {"true", "1", "yes", "false", "0", "no"}:
        raise ValueError("invalid boolean for MTM_ENABLED")
    if value in {"true", "1", "yes"}:
        raise NotImplementedError("requires a separately approved design")
    return {"status": "disabled", "dry_run": True}


if __name__ == "__main__":
    print(consolidate())
