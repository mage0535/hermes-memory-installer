from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


def test_langsmith_monitor_exists_and_targets_acceptance_and_recall():
    content = (REPO / "scripts" / "langsmith_monitor.py").read_text(encoding="utf-8")
    assert "sidecar_acceptance_check.py" in content
    assert "tiered_context_injector.py" in content
    assert "LANGSMITH_PROJECT" in content
    assert "traceable" in content


def test_langsmith_task_wrapper_exists_and_uses_traceable():
    content = (REPO / "scripts" / "langsmith_task_wrapper.py").read_text(encoding="utf-8")
    assert "traceable" in content
    assert "task_name" in content
    assert "subprocess.run" in content
