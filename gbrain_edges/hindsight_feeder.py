import argparse
import json

from .planner import apply_edges, plan_edges


def main(argv=None):
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True)
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args(argv)
    planned = plan_edges([], set(), args.limit)
    print(json.dumps({"mode": "apply" if args.apply else "dry-run", "planned": len(planned)}))
    return apply_edges(planned, apply=args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
