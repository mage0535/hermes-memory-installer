#!/usr/bin/env python3
"""Import Hermes Grafana dashboards and set the default home dashboard."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from urllib import request
from urllib.parse import quote


def api_request(url: str, method: str, username: str, password: str, payload: dict | None = None) -> dict:
    headers = {
        "Authorization": "Basic " + base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii"),
        "Content-Type": "application/json",
    }
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method=method)
    with request.urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--grafana-url", default="http://127.0.0.1:3000")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password-file", required=True)
    parser.add_argument("--dashboards-dir", required=True)
    parser.add_argument("--folder", default="Hermes Memory")
    parser.add_argument("--home-uid", default="hermes-memory-home")
    args = parser.parse_args()

    password = Path(args.password_file).read_text(encoding="utf-8").strip()
    dashboards_dir = Path(args.dashboards_dir)

    folders = api_request(
        f"{args.grafana_url}/api/search?type=dash-folder&query={quote(args.folder)}",
        "GET",
        args.username,
        password,
    )
    folder_uid = None
    for row in folders if isinstance(folders, list) else []:
        if row.get("title") == args.folder:
            folder_uid = row.get("uid")
            break
    if not folder_uid:
        created = api_request(
            f"{args.grafana_url}/api/folders",
            "POST",
            args.username,
            password,
            {"title": args.folder},
        )
        folder_uid = created["uid"]

    imported = []
    for path in sorted(dashboards_dir.glob("*.json")):
        dashboard = json.loads(path.read_text(encoding="utf-8"))
        payload = {
            "dashboard": dashboard,
            "folderUid": folder_uid,
            "overwrite": True,
        }
        api_request(f"{args.grafana_url}/api/dashboards/db", "POST", args.username, password, payload)
        imported.append(dashboard.get("uid") or path.name)

    api_request(
        f"{args.grafana_url}/api/org/preferences",
        "PUT",
        args.username,
        password,
        {"homeDashboardUID": args.home_uid, "theme": "", "timezone": ""},
    )
    print(json.dumps({"ok": True, "folder_uid": folder_uid, "imported": imported, "home_uid": args.home_uid}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
