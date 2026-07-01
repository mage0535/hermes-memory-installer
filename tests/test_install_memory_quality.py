from installer.install import VERSION, deploy_memory_quality_modules, memory_quality_cron, parse_args, reconcile_cron


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


def test_memory_quality_installer_flags_are_explicit():
    args = parse_args(["--enable-memory-quality", "--install-memory-quality-cron", "--init-memory-policy"])

    assert args.enable_memory_quality is True
    assert args.install_memory_quality_cron is True
    assert args.init_memory_policy is True


def test_memory_quality_modules_deploy_without_private_registry(tmp_path):
    deployed = deploy_memory_quality_modules(tmp_path)

    assert "memory_eval" in deployed
    assert (tmp_path / "memory-sidecar" / "memory_eval" / "runner.py").exists()
    assert not (tmp_path / "memory-sidecar" / ".memory_eval" / "registry_production.py").exists()
