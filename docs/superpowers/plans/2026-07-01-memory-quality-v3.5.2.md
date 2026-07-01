# Memory Sidecar v3.5.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver privacy-safe dual-registry memory evaluation, additive policy metadata, and dry-run-first gbrain edge planning without modifying existing memory services.

**Architecture:** Add importable `memory_eval`, `governance`, `gbrain_edges`, and disabled extension packages at repository root so they work in both source and installed layouts. Reuse the existing governance SQLite database and installer rollback/idempotency patterns; all production reads and writes remain behind adapters, explicit flags, or `--apply`.

**Tech Stack:** Python 3.9+, standard library (`argparse`, `dataclasses`, `importlib`, `json`, `sqlite3`, `subprocess`, `urllib`), pytest, existing PyYAML installer dependency.

---

## File Map

- `memory_eval/models.py`: normalized cases, hits, layer status, and reports.
- `memory_eval/registry_default.py`: exactly 40 synthetic cases and fixtures.
- `memory_eval/registry_loader.py`: default/private registry discovery and validation.
- `memory_eval/adapters.py`: adapter protocol, deterministic synthetic adapter, and read-only live adapter.
- `memory_eval/metrics.py`: five metric calculations over evaluated cases only.
- `memory_eval/runner.py`: CLI orchestration, dual reports, JSON output, and previous-report comparison.
- `memory_eval/smoke.sh`: environment-driven weekly entry point.
- `governance/policy.py`: policy schema, importance scoring, confidence decay, and provenance sanitization.
- `governance/inject_policy.py`: dry-run-first policy injection CLI.
- `governance/temporal.py`: disabled temporal-truth contract.
- `gbrain_edges/models.py`: candidate edge contract.
- `gbrain_edges/planner.py`: normalization, deduplication, deterministic budgets, and apply boundary.
- `gbrain_edges/hindsight_feeder.py`: provider composition and CLI.
- `mtm/consolidator.py`: disabled MTM validation/no-op contract.
- `installer/install.py`: additive module deployment, flags, schema init, and idempotent cron registration.
- `.gitignore`: block private production registries wherever commonly placed.
- `tests/test_memory_eval_*.py`: evaluator contract, registries, adapters, metrics, and runner.
- `tests/test_governance_policy.py`: policy schema, scoring, decay, and sanitization.
- `tests/test_gbrain_edges.py`: dry-run, deduplication, budgets, and fail-fast apply.
- `tests/test_feature_flags.py`: disabled Phase 2/4 side-effect checks.
- `tests/test_install_memory_quality.py`: installer deployment and schedule idempotency.
- `docs/release-v3.5.2.md`, `README.md`, `README_CN.md`, `ARCHITECTURE.md`, `ARCHITECTURE_CN.md`: release and operator documentation.

### Task 1: Establish Evaluation Contracts And Registry Loading

**Files:**
- Create: `memory_eval/__init__.py`
- Create: `memory_eval/models.py`
- Create: `memory_eval/registry_loader.py`
- Modify: `.gitignore`
- Test: `tests/test_memory_eval_registry.py`

- [ ] **Step 1: Write failing contract and loader tests**

```python
def test_default_registry_is_always_loadable(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_HOME", str(tmp_path))
    loaded = load_registries("all")
    assert [item.name for item in loaded] == ["default"]


def test_all_adds_private_registry_without_copying_it(monkeypatch, tmp_path):
    private = tmp_path / ".memory_eval" / "registry_production.py"
    private.parent.mkdir()
    private.write_text("REGISTRY = [{'id': 'prod_001', 'category': 'accurate_retrieval', "
                       "'query': 'current project', 'expected_fields': ['project'], "
                       "'expected_layer': 'hindsight', 'expected_min_score': 0.7}]", encoding="utf-8")
    monkeypatch.setenv("AGENT_HOME", str(tmp_path))
    loaded = load_registries("all")
    assert [item.name for item in loaded] == ["default", "production"]
    assert loaded[1].cases[0].id == "prod_001"


def test_invalid_private_registry_becomes_scoped_error(monkeypatch, tmp_path):
    private = tmp_path / ".memory_eval" / "registry_production.py"
    private.parent.mkdir()
    private.write_text("REGISTRY = 'invalid'", encoding="utf-8")
    monkeypatch.setenv("AGENT_HOME", str(tmp_path))
    loaded = load_registries("all")
    assert loaded[0].name == "default"
    assert loaded[1].name == "production"
    assert loaded[1].error
```

- [ ] **Step 2: Run the tests and verify missing-module failure**

Run: `python -m pytest tests/test_memory_eval_registry.py -q`

Expected: FAIL because `memory_eval.models` and `memory_eval.registry_loader` do not exist.

- [ ] **Step 3: Implement immutable contracts and strict registry loading**

Define `EvalCase`, `RecallHit`, `LayerResult`, `CaseResult`, `RegistryLoad`, `MetricSet`, and `EvalReport` as dataclasses. `load_registries(selection, agent_home=None)` must accept only `default`, `production`, or `all`; import the public registry normally; load private code only from `Path(AGENT_HOME)/.memory_eval/registry_production.py`; validate required keys and unique IDs; return a production-scoped error for invalid optional private data; raise when explicitly selected production is absent.

- [ ] **Step 4: Add private-registry ignore rules**

```gitignore
# Private memory evaluation facts
registry_production.py
**/.memory_eval/
```

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_memory_eval_registry.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the contract slice**

```bash
git add .gitignore memory_eval tests/test_memory_eval_registry.py
git commit -m "feat: add memory evaluation registry contracts"
```

### Task 2: Add The 40-Case Synthetic Registry And Deterministic Adapter

**Files:**
- Create: `memory_eval/registry_default.py`
- Create: `memory_eval/adapters.py`
- Test: `tests/test_memory_eval_default_registry.py`
- Test: `tests/test_memory_eval_adapters.py`

- [ ] **Step 1: Write failing distribution, privacy, and deterministic-recall tests**

```python
def test_default_registry_distribution_and_ids():
    counts = Counter(case["category"] for case in REGISTRY)
    assert len(REGISTRY) == 40
    assert counts == {
        "accurate_retrieval": 12,
        "conflict_resolution": 10,
        "temporal_understanding": 10,
        "test_time_learning": 8,
    }
    assert len({case["id"] for case in REGISTRY}) == 40


def test_default_registry_is_privacy_safe():
    serialized = json.dumps(REGISTRY, ensure_ascii=False)
    forbidden = [r"sk-[A-Za-z0-9]", r"/root/", r"postgresql://[^<]", r"\b(?:\d{1,3}\.){3}\d{1,3}\b"]
    assert not any(re.search(pattern, serialized) for pattern in forbidden)


def test_synthetic_adapter_returns_fixture_hits():
    case = validate_case(REGISTRY[0])
    result = SyntheticAdapter().recall(case, k=5)
    assert result.status == "evaluated"
    assert result.hits
    assert result.hits[0].layer == case.expected_layer
```

- [ ] **Step 2: Verify tests fail before implementation**

Run: `python -m pytest tests/test_memory_eval_default_registry.py tests/test_memory_eval_adapters.py -q`

Expected: FAIL because the registry and adapters are absent.

- [ ] **Step 3: Implement exactly 40 fictional cases**

Use IDs `eval_001` through `eval_040`; category ranges 001-012, 013-022, 023-032, and 033-040; each case includes `query`, `expected_fields`, `expected_layer`, `expected_min_score`, `conflict_expected`, and optional `temporal_context`. Store deterministic `synthetic_hits` beside each case so tests do not depend on external services. Credential examples must use literal placeholders such as `<YOUR_API_KEY_HERE>` and `<SERVER_HOST>`.

- [ ] **Step 4: Implement the adapter protocol and synthetic adapter**

```python
class RecallAdapter(Protocol):
    def recall(self, case: EvalCase, k: int) -> CaseResult: ...


class SyntheticAdapter:
    def recall(self, case: EvalCase, k: int) -> CaseResult:
        hits = tuple(RecallHit.from_mapping(item) for item in case.synthetic_hits[:k])
        return CaseResult(case_id=case.id, status="evaluated", hits=hits)
```

The adapter must support isolated setup/cleanup state for test-time-learning cases and never write outside its in-memory fixture map.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_memory_eval_default_registry.py tests/test_memory_eval_adapters.py -q`

Expected: PASS with 40 unique cases.

- [ ] **Step 6: Commit the synthetic evaluator slice**

```bash
git add memory_eval tests/test_memory_eval_default_registry.py tests/test_memory_eval_adapters.py
git commit -m "feat: add synthetic memory evaluation registry"
```

### Task 3: Implement Metrics And Dual-Registry Reports

**Files:**
- Create: `memory_eval/metrics.py`
- Create: `memory_eval/runner.py`
- Create: `memory_eval/smoke.sh`
- Test: `tests/test_memory_eval_metrics.py`
- Test: `tests/test_memory_eval_runner.py`

- [ ] **Step 1: Write failing metric tests with skipped cases excluded**

```python
def test_metrics_use_only_evaluated_cases():
    results = [matching_result(), irrelevant_result(), skipped_result()]
    metrics = calculate_metrics(results)
    assert metrics.recall_at_k == 0.5
    assert metrics.precision_at_k == 0.5


def test_stale_contradiction_and_agreement_metrics():
    metrics = calculate_metrics([conflicting_stale_multilayer_result()])
    assert metrics.contradiction_rate == 1.0
    assert metrics.stale_hit_rate == 0.5
    assert metrics.cross_layer_agreement == 1.0
```

- [ ] **Step 2: Write failing runner tests**

Assert `--registry all` emits separate `default` and `production` reports when private data exists, invalid production does not suppress default, smoke selects three cases per category, full selects all 40, JSON contains counts/failures/per-category data, and a missing previous report yields `comparison: null`.

- [ ] **Step 3: Verify failures**

Run: `python -m pytest tests/test_memory_eval_metrics.py tests/test_memory_eval_runner.py -q`

Expected: FAIL because metrics and runner are absent.

- [ ] **Step 4: Implement the five metrics**

Normalize expected fields and hit content case-insensitively. Compute denominators from `status == "evaluated"` only. Return `None` for cross-layer agreement when no comparable multi-layer case exists. A contradiction requires two active hits in the same conflict group with different normalized facts; stale means expired or superseded.

- [ ] **Step 5: Implement runner and CLI**

Expose `run_eval(category="all", model=None, mode="smoke", registry="all", adapter=None)`. CLI options: `--mode smoke|full`, `--registry default|production|all`, `--backend synthetic|live`, `--category`, `--k`, `--output`, and `--previous`. Write JSON atomically with a temporary sibling file and `os.replace`; print one concise heading per registry.

- [ ] **Step 6: Add the environment-driven smoke entry point**

```bash
#!/usr/bin/env bash
set -euo pipefail
: "${MEMORY_SIDECAR_HOME:?MEMORY_SIDECAR_HOME is required}"
OUTPUT_DIR="${MEMORY_EVAL_OUTPUT_DIR:-${AGENT_HOME}/logs}"
mkdir -p "$OUTPUT_DIR"
cd "$MEMORY_SIDECAR_HOME"
python3 -m memory_eval.runner --mode smoke --registry "${MEMORY_EVAL_REGISTRY:-all}" --output "$OUTPUT_DIR/memory-smoke.json"
```

- [ ] **Step 7: Run evaluator tests and a real synthetic smoke**

Run: `python -m pytest tests/test_memory_eval_metrics.py tests/test_memory_eval_runner.py -q`

Expected: PASS.

Run: `python -m memory_eval.runner --mode smoke --registry default --backend synthetic --output build/memory-smoke.json`

Expected: exit 0; JSON reports 12 evaluated cases and all five metric keys.

- [ ] **Step 8: Commit the reporting slice**

```bash
git add memory_eval tests/test_memory_eval_metrics.py tests/test_memory_eval_runner.py
git commit -m "feat: add memory quality metrics and reports"
```

### Task 4: Add A Read-Only Live Adapter

**Files:**
- Modify: `memory_eval/adapters.py`
- Test: `tests/test_memory_eval_live_adapter.py`

- [ ] **Step 1: Write failing layer-isolation and write-opt-in tests**

Mock hot-file reads, Hindsight HTTP, governance SQLite, and gbrain subprocess calls. Assert an unavailable layer is recorded as degraded without converting the whole case to a zero score; production test-time-learning is skipped unless `MEMORY_EVAL_ALLOW_WRITES=true`; generated test IDs start with `memory-eval-` and cleanup runs in `finally`.

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_memory_eval_live_adapter.py -q`

Expected: FAIL because `LiveAdapter` is absent.

- [ ] **Step 3: Implement read-only layer clients**

Use `AGENT_HOME`, `HINDSIGHT_API_URL`, `GOVERNANCE_DB_PATH`, and `GBRAIN_BIN`. Put each layer behind a small method returning `LayerResult`; apply per-layer timeouts; parse only documented JSON; never include raw retrieved content in exceptions or logs. Merge normalized hits after collecting layer statuses.

- [ ] **Step 4: Gate live write cases**

Skip unless `MEMORY_EVAL_ALLOW_WRITES=true`. Generate a UUID-prefixed marker, require adapter-specific cleanup support, and report an error if cleanup fails. Default and smoke registries remain synthetic-only.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_memory_eval_live_adapter.py -q`

Expected: PASS without network or production services.

- [ ] **Step 6: Commit the live adapter slice**

```bash
git add memory_eval/adapters.py tests/test_memory_eval_live_adapter.py
git commit -m "feat: add read-only live memory adapter"
```

### Task 5: Add Policy Metadata, Decay, And Sanitized Injection

**Files:**
- Create: `governance/__init__.py`
- Create: `governance/policy.py`
- Create: `governance/inject_policy.py`
- Test: `tests/test_governance_policy.py`

- [ ] **Step 1: Write failing schema and idempotency tests**

Assert `ensure_policy_schema()` creates only policy-owned fields, repeated initialization preserves rows, and `upsert_policy()` updates the same `memory_id` without duplication. Explicitly assert validity/conflict/object-confidence columns are absent from `memory_policy`.

- [ ] **Step 2: Write failing scoring, decay, and sanitization tests**

```python
@pytest.mark.parametrize("value", [
    "sk-live-abcdefghijklmnopqrstuvwxyz",
    "postgresql://alice:secret@db.example/test",
    "https://bob:secret@example.test/path",
])
def test_sanitize_provenance_redacts_credentials(value):
    sanitized = sanitize_provenance(value)
    assert "secret" not in sanitized
    assert "sk-live" not in sanitized
    assert "[REDACTED]" in sanitized


def test_injection_sanitizes_by_default(tmp_path):
    result = inject_rows([secret_bearing_row()], db_path=tmp_path / "gov.db", apply=True)
    assert result.sanitize_provenance is True
    assert "[REDACTED]" in read_policy(tmp_path / "gov.db").provenance
```

Also assert `--no-sanitize-provenance` is rejected unless paired with an explicit `--allow-unsafe-provenance` acknowledgement; dry-run is default; decay marks but never deletes eviction candidates.

- [ ] **Step 3: Verify failure**

Run: `python -m pytest tests/test_governance_policy.py -q`

Expected: FAIL because the policy package is absent.

- [ ] **Step 4: Implement policy schema and scorer**

Create `memory_policy(memory_id TEXT PRIMARY KEY, importance_score REAL, tier TEXT CHECK(...), policy_confidence REAL, source_layer TEXT, provenance TEXT, promotion_reason TEXT, eviction_candidate INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT)`. Use `CREATE TABLE IF NOT EXISTS`, inspect columns with `PRAGMA table_info`, and add only missing policy-owned columns. Score deterministically from declared content classes and source weights, clamped to 1.0-5.0.

- [ ] **Step 5: Implement provenance sanitization**

Redact API-token patterns and credentials in HTTP/PostgreSQL URLs before constructing SQL parameters, log records, or dry-run output. Add `--sanitize-provenance` / `--no-sanitize-provenance`, with sanitization defaulting true. Unsafe mode requires `--allow-unsafe-provenance`; documentation must state it is for isolated debugging only.

- [ ] **Step 6: Implement dry-run-first injection and decay**

Read stable IDs and authoritative fields from existing `memory_objects`; return proposed rows by default; require `--apply` for transaction writes. Decay only `policy_confidence`, using observation/world/experience rates 0.05/0.02/0.01 and configurable threshold default 0.2; set `eviction_candidate=1` at threshold and never delete source rows.

- [ ] **Step 7: Run focused tests**

Run: `python -m pytest tests/test_governance_policy.py -q`

Expected: PASS, including all redaction cases.

- [ ] **Step 8: Commit the policy slice**

```bash
git add governance tests/test_governance_policy.py
git commit -m "feat: add sanitized memory policy metadata"
```

### Task 6: Add Dry-Run-First gbrain Edge Planning

**Files:**
- Create: `gbrain_edges/__init__.py`
- Create: `gbrain_edges/models.py`
- Create: `gbrain_edges/planner.py`
- Create: `gbrain_edges/hindsight_feeder.py`
- Test: `tests/test_gbrain_edges.py`

- [ ] **Step 1: Write failing planner tests**

Cover invalid slugs, self-links, candidate deduplication, existing-edge deduplication, stable score ordering, top-k inbound/outbound budgets, zero subprocess calls in default dry-run, exact `gbrain link FROM TO --type TYPE` argv in apply mode, and immediate non-zero stop after the first failed write.

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_gbrain_edges.py -q`

Expected: FAIL because the package is absent.

- [ ] **Step 3: Implement candidate contracts and providers**

Define immutable `EdgeCandidate(source, target, edge_type, score, provenance)`. Providers may enumerate governance relations and supported Hindsight records only when concrete source and target IDs exist. Do not use aggregate `/stats` data as edge input.

- [ ] **Step 4: Implement deterministic planning**

Normalize slugs and edge type, reject self-links, deduplicate by `(source, target, edge_type)`, retain highest score, subtract existing edges, sort by `(-score, source, target, edge_type)`, then enforce independent inbound/outbound `top_k` counters.

- [ ] **Step 5: Implement explicit apply boundary**

CLI defaults to `--dry-run`; only `--apply` calls `subprocess.run` with an argv list and `shell=False`. Stop at the first non-zero return code. Do not unlink or evict existing edges.

- [ ] **Step 6: Run focused tests and CLI dry-run**

Run: `python -m pytest tests/test_gbrain_edges.py -q`

Expected: PASS.

Run: `python -m gbrain_edges.hindsight_feeder --dry-run --limit 10`

Expected: exit 0 and a plan summary; no `gbrain link` write is executed.

- [ ] **Step 7: Commit the edge-planning slice**

```bash
git add gbrain_edges tests/test_gbrain_edges.py
git commit -m "feat: add safe gbrain edge planning"
```

### Task 7: Add Disabled Temporal And MTM Extension Contracts

**Files:**
- Create: `governance/temporal.py`
- Create: `mtm/__init__.py`
- Create: `mtm/consolidator.py`
- Test: `tests/test_feature_flags.py`

- [ ] **Step 1: Write failing disabled-mode tests**

Assert `TEMPORAL_TRUTH_ENABLED` and `MTM_ENABLED` default false, disabled temporal retrieval returns the unchanged query/plan, disabled MTM validates configuration and emits a no-op dry-run report, and neither path opens a database, invokes HTTP, or starts a subprocess.

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_feature_flags.py -q`

Expected: FAIL because the extension modules are absent.

- [ ] **Step 3: Implement side-effect-free contracts**

Use a strict boolean parser accepting `true/false`, `1/0`, and `yes/no`; reject other values. Enabled mode must raise `NotImplementedError("requires a separately approved design")` rather than silently performing partial production work.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_feature_flags.py -q`

Expected: PASS with no mocked I/O calls.

- [ ] **Step 5: Commit the extension contracts**

```bash
git add governance/temporal.py mtm tests/test_feature_flags.py
git commit -m "feat: add disabled temporal and mtm contracts"
```

### Task 8: Integrate Modules And Idempotent Schedules Into The Existing Installer

**Files:**
- Modify: `installer/install.py`
- Modify: `tests/test_install.py`
- Create: `tests/test_install_memory_quality.py`
- Modify: `install.sh`
- Modify: `install_cli.sh`

- [ ] **Step 1: Write failing deployment tests**

Assert all four packages deploy under `$AGENT_HOME/memory-sidecar`, staging/rollback remains atomic, private `$AGENT_HOME/.memory_eval/registry_production.py` survives reruns, policy initialization occurs only with `--init-memory-policy`, and default installation leaves `TEMPORAL_TRUTH_ENABLED=false` and `MTM_ENABLED=false`.

- [ ] **Step 2: Write failing cron idempotency tests**

Given an existing crontab containing one memory smoke entry, run schedule generation twice and assert exactly one weekly smoke, one monthly full evaluation, and one weekly decay entry. Commands must use `$AGENT_HOME`/installed paths and configurable output directories, not repository or server-specific paths.

- [ ] **Step 3: Verify failure**

Run: `python -m pytest tests/test_install.py tests/test_install_memory_quality.py -q`

Expected: FAIL because v3.5.2 deployment options are absent.

- [ ] **Step 4: Extend the existing installer minimally**

Bump `VERSION` to `3.5.2`; add package-directory deployment to the current staging manifest; add `--enable-memory-eval`, `--init-memory-policy`, and `--install-memory-quality-cron`. Preserve the three existing install modes and do not introduce separate manual/semi/auto installers.

- [ ] **Step 5: Implement marker-based cron reconciliation**

Generate a bounded block:

```text
# BEGIN hermes-memory-quality
0 7 * * 1 .../memory_eval/smoke.sh
0 4 1 * * ... -m memory_eval.runner --mode full ...
0 3 * * 0 ... -m governance.inject_policy --decay --apply ...
# END hermes-memory-quality
```

Replace the existing marked block atomically; never append duplicates; require explicit schedule installation. Keep policy injection and gbrain application out of automatic schedules.

- [ ] **Step 6: Run installer tests twice**

Run: `python -m pytest tests/test_install.py tests/test_install_memory_quality.py -q`

Expected: PASS and rerun fixture contains no duplicate files or cron lines.

- [ ] **Step 7: Commit installer integration**

```bash
git add installer/install.py install.sh install_cli.sh tests/test_install.py tests/test_install_memory_quality.py
git commit -m "feat: install memory quality modules idempotently"
```

### Task 9: Update Documentation, Privacy Audit, And Release Metadata

**Files:**
- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `ARCHITECTURE.md`
- Modify: `ARCHITECTURE_CN.md`
- Modify: `docs/release-checklist.md`
- Create: `docs/release-v3.5.2.md`
- Modify: `tests/test_smoke.py`
- Modify: `bin/hermes-memory`

- [ ] **Step 1: Write failing documentation and audit tests**

Assert docs identify synthetic versus private registries, list five metrics, explain dry-run/apply, document `--sanitize-provenance` default true, show Phase 2/4 disabled, and contain no fixed production path. Extend repository audit expectations to scan `memory_eval`, `governance`, `gbrain_edges`, and `mtm`, while excluding private registry files and generated reports from tracked artifacts.

- [ ] **Step 2: Verify failure**

Run: `python -m pytest tests/test_smoke.py -q`

Expected: FAIL on missing v3.5.2 documentation/audit coverage.

- [ ] **Step 3: Update English and Chinese documentation**

Document operator commands for default smoke, optional production evaluation, policy dry-run/apply, edge dry-run/apply, installation flags, report paths, rollback, and the feature-flag boundary. State that production registry content remains under `$AGENT_HOME/.memory_eval` and is never installed or committed.

- [ ] **Step 4: Extend the privacy scanner**

Scan tracked text for private key headers, common token prefixes, credential-bearing URLs, public IPv4 addresses, fixed `/root` paths, and configured user-identifying markers. Reports must name file and rule but never echo a matched secret value.

- [ ] **Step 5: Run docs/privacy tests and repository audit**

Run: `python -m pytest tests/test_smoke.py -q`

Expected: PASS.

Run: `python bin/hermes-memory audit-repo --format json`

Expected: JSON has `"ok": true`, no private paths, no secret-like references, and no compile failures.

- [ ] **Step 6: Commit documentation and audit changes**

```bash
git add README.md README_CN.md ARCHITECTURE.md ARCHITECTURE_CN.md docs bin/hermes-memory tests/test_smoke.py
git commit -m "docs: document memory quality release"
```

### Task 10: Full Verification, Production Dry Deployment, And Single Release Commit

**Files:**
- Modify: `docs/superpowers/specs/2026-07-01-memory-quality-v3.5.2-design.md` only if implementation evidence reveals a factual mismatch
- Create locally only: `build/memory-smoke.json`
- Create on production only: configured baseline report files

- [ ] **Step 1: Run the complete local test suite**

Run: `python -m pytest -q`

Expected: all existing and new tests PASS with no changed legacy-test expectations unrelated to v3.5.2.

- [ ] **Step 2: Run compile and synthetic evaluator verification**

Run: `python -m compileall -q memory_eval governance gbrain_edges mtm installer scripts`

Expected: exit 0.

Run: `python -m memory_eval.runner --mode full --registry default --backend synthetic --output build/memory-benchmark-default.json`

Expected: exactly 40 evaluated cases, 12/10/10/8 distribution, valid JSON, and all five metrics.

- [ ] **Step 3: Prove dry-run safety**

Run: `python -m governance.inject_policy --source governance --dry-run --sanitize-provenance`

Expected: proposed changes only and zero database writes.

Run: `python -m gbrain_edges.hindsight_feeder --dry-run`

Expected: plan only and zero `gbrain link` writes.

- [ ] **Step 4: Run final privacy and tracked-file checks**

Run: `python bin/hermes-memory audit-repo --format json`

Expected: `ok: true`.

Run: `git status --short`

Expected: only intended v3.5.2 source, tests, docs, and the approved design/plan are present; no `.env`, private registry, database, log, or report is tracked.

- [ ] **Step 5: Consolidate implementation history into the required release commit**

After all task-level commits have passed review, create the required single v3.5.2 release commit without rewriting the predecessor `16a2716`. Use a temporary integration branch or soft reset only after confirming the exact merge base and preserving a backup ref.

Expected final history: `16a2716` followed by one v3.5.2 commit. Do not amend or squash `16a2716`.

- [ ] **Step 6: Deploy additive modules with write features disabled**

Deploy through the existing installer into the production `AGENT_HOME`; enable evaluator deployment only; leave policy injection, gbrain apply, temporal truth, and MTM disabled. Verify installed imports and rerun installation once to prove idempotency.

Expected: existing Hindsight, gateway, headroom, governance rebuild, tiered recall, guardian, and watermark services remain unchanged.

- [ ] **Step 7: Generate separate production baselines**

Run default and production registries separately using configured production paths. Verify both reports are valid JSON and production report output contains case IDs/normalized evidence but no raw secret-bearing content.

Expected: default baseline succeeds; production baseline succeeds or release stops before cron/tag/push.

- [ ] **Step 8: Install and list idempotent schedules**

Enable the approved evaluator/decay schedule block only after baseline acceptance. List the resulting crontab and verify one entry per schedule. Rerun installer and verify counts remain one.

- [ ] **Step 9: Create the release commit and tag**

```bash
git add -A
git commit -m "feat: add memory quality evaluation and policy layer"
git tag -a v3.5.2 -m "Memory Sidecar v3.5.2"
```

Expected: one release commit after `16a2716`; annotated tag points to that commit.

- [ ] **Step 10: Push only after production acceptance**

```bash
git push origin codex/v3.5.2:main
git push origin v3.5.2
```

Expected: branch push and tag push succeed; public repository contains no production registry or sensitive artifact.

## Final Acceptance Checklist

- [ ] Public registry has exactly 40 privacy-safe cases distributed 12/10/10/8.
- [ ] Default CI evaluation runs without Hindsight, gbrain, or production data.
- [ ] Private registry is loaded only from `$AGENT_HOME/.memory_eval/registry_production.py` and reported separately.
- [ ] Recall, precision, contradiction, stale-hit, and cross-layer-agreement metrics exclude skipped/errored cases appropriately.
- [ ] Policy schema is additive, idempotent, and does not duplicate authoritative memory-object fields.
- [ ] Provenance sanitization defaults on and redacts token and credential-bearing URL patterns before persistence or logging.
- [ ] Policy injection, decay, and gbrain writes require explicit `--apply`.
- [ ] gbrain planning deduplicates candidates and enforces deterministic per-page budgets.
- [ ] Temporal truth and MTM default disabled and perform no I/O.
- [ ] Installer reruns preserve private data/policy rows and produce no duplicate schedules.
- [ ] Existing and new tests pass; repository privacy audit passes.
- [ ] Separate default and production baselines exist before one release commit and tag `v3.5.2` are published.
