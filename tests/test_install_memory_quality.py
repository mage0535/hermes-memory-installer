from installer.install import VERSION, memory_quality_cron, reconcile_cron


def test_memory_quality_release_and_feature_defaults(tmp_path):
    assert VERSION == "3.5.2"
    block = memory_quality_cron(tmp_path)
    assert "TEMPORAL_TRUTH_ENABLED=false" in block
    assert "MTM_ENABLED=false" in block


def test_cron_reconciliation_is_idempotent(tmp_path):
    block = memory_quality_cron(tmp_path)
    once = reconcile_cron("0 1 * * * existing\n", block)
    twice = reconcile_cron(once, block)
    assert twice.count("# BEGIN hermes-memory-quality") == 1
    assert twice.count("memory_eval.runner --mode full") == 1
