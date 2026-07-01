import os


def _enabled(name):
    value = os.getenv(name, "false").lower()
    if value in {"true", "1", "yes"}: return True
    if value in {"false", "0", "no"}: return False
    raise ValueError(f"invalid boolean for {name}")


def temporal_retrieve(query):
    if _enabled("TEMPORAL_TRUTH_ENABLED"):
        raise NotImplementedError("requires a separately approved design")
    return query
