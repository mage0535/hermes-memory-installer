from memory_eval.adapters import LiveAdapter
from memory_eval.models import EvalCase


def case(category="accurate_retrieval"):
    return EvalCase("prod_1", category, "query", ["fact"], "hindsight", 0.7)


def test_live_adapter_isolates_layer_failures():
    adapter = LiveAdapter(layer_readers={"hot": lambda _: (_ for _ in ()).throw(RuntimeError("down")), "hindsight": lambda _: [{"content": "fact", "score": .9}]})
    result = adapter.recall(case(), 5)
    assert result.status == "evaluated"
    assert result.hits[0].layer == "hindsight"


def test_test_time_learning_is_skipped_without_write_opt_in(monkeypatch):
    monkeypatch.delenv("MEMORY_EVAL_ALLOW_WRITES", raising=False)
    assert LiveAdapter(layer_readers={}).recall(case("test_time_learning"), 5).status == "skipped"
