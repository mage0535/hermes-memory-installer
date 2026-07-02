import json
import sqlite3

from memory_ops.report import build_ops_report


def test_ops_report_collects_latest_eval_policy_and_edge_state(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "memory-smoke.json").write_text(
        json.dumps({"reports": [{"registry": "default", "evaluated_count": 12, "metrics": {"recall_at_k": 1.0}}]}),
        encoding="utf-8",
    )
    db = tmp_path / "memory_governance.db"
    with sqlite3.connect(db) as conn:
        conn.execute("create table memory_policy(memory_id text primary key, eviction_candidate integer)")
        conn.execute("insert into memory_policy values ('m1', 0), ('m2', 1)")

    report = build_ops_report(tmp_path, edge_plan={"planned_edges": 3, "mode": "dry-run"})

    assert report["eval"]["latest_file"].endswith("memory-smoke.json")
    assert report["eval"]["reports"][0]["registry"] == "default"
    assert report["policy"]["rows"] == 2
    assert report["policy"]["eviction_candidates"] == 1
    assert report["gbrain_edges"]["planned_edges"] == 3
    assert report["mtm"]["items"] == 0
