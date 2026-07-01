from __future__ import annotations

import argparse
import json
import os

from .policy import sanitize_provenance


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="governance")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--sanitize-provenance", action="store_true", default=True)
    parser.add_argument("--no-sanitize-provenance", dest="sanitize_provenance", action="store_false")
    parser.add_argument("--allow-unsafe-provenance", action="store_true")
    parser.add_argument("--decay", action="store_true")
    args = parser.parse_args(argv)
    if not args.sanitize_provenance and not args.allow_unsafe_provenance:
        parser.error("unsafe provenance requires --allow-unsafe-provenance")
    print(json.dumps({"source": args.source, "mode": "apply" if args.apply else "dry-run", "sanitize_provenance": args.sanitize_provenance}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
