# Memory Sidecar v3.5.2 Design

## Goal

Add measurable memory-quality evaluation, an additive policy layer, and safe gbrain edge planning without modifying Hindsight, gateway, headroom, or existing memory-service internals.

## Scope

The release contains three working additions and two disabled extension contracts:

- Phase 0: a dual-registry evaluation system with deterministic public cases and optional private production cases.
- Phase 1: policy metadata, deterministic importance scoring, confidence decay, and initial policy injection.
- Phase 1.5: gbrain candidate-edge planning, deduplication, budgets, and explicit apply mode.
- Phase 2: a disabled temporal-truth interface backed by policy validity metadata.
- Phase 4: a disabled MTM consolidation interface with no production write path.

Existing governance rebuild, tiered recall, maintenance, guardian, and watermark behavior remain unchanged. The installer receives additive deployment support only.

## Release Baseline

Development starts from production commit `16a2716`, which is one commit ahead of the public `origin/main`. Work happens in an isolated worktree and branch. The existing dirty workstation checkout is not modified.

The complete v3.5.2 change is released as one commit and tag, per the release requirement. The production-only predecessor commit remains in history and is pushed with the release rather than recreated or squashed.

## Evaluation Architecture

`memory_eval.runner` owns orchestration and reporting. It loads one or both registries, executes each case through a backend adapter, and calculates metrics from normalized results.

The public `registry_default.py` contains exactly 40 synthetic cases:

- 12 accurate retrieval cases
- 10 conflict resolution cases
- 10 temporal understanding cases
- 8 test-time learning cases

Cases use fictional values and explicit placeholders. They never contain production credentials, hosts, paths, names, or user facts.

The optional production registry is loaded from:

```text
$AGENT_HOME/.memory_eval/registry_production.py
```

It is never copied into the repository or installer payload. `.gitignore` blocks common accidental placements of `registry_production.py`. An invalid private registry produces a registry-scoped error report; it does not suppress the default report.

The runner supports three registry selections:

- `default`: run only the public registry.
- `production`: require and run only the private registry.
- `all`: always run default and additionally run production when present.

`MEMORY_EVAL_REGISTRY` defaults to `all` for installed runtime use. CI explicitly selects `default`.

## Adapter Contract

Adapters return normalized recall hits with content, layer, score, timestamps, validity, conflict group, and provenance. Metrics depend only on this contract.

Two adapter families are used:

- Synthetic adapter: deterministic in-memory fixtures for CI, installer smoke, and evaluator self-tests.
- Live adapter: reads the hot memory file, calls the configured Hindsight recall endpoint, queries the governance database, and invokes supported gbrain CLI commands.

Unavailable live layers are recorded as degraded layer results. They do not become false zero-quality scores. A report distinguishes `evaluated`, `skipped`, and `errored` cases.

Test-time-learning cases must declare setup and cleanup behavior. The default registry executes against synthetic state only. Production write cases require an explicit opt-in environment flag and unique test identifiers; otherwise they are skipped.

## Metrics

The evaluator reports:

- recall at k: evaluated cases with at least one expected hit divided by evaluated cases.
- precision at k: relevant returned hits divided by returned hits for evaluated cases.
- contradiction rate: evaluated cases whose returned active facts conflict.
- stale hit rate: returned hits marked expired or superseded divided by returned hits.
- cross-layer agreement: comparable cases where independent layers agree on normalized expected fields.

Reports include registry name, mode, timestamp, case counts, skipped/error counts, per-category metrics, failures, and optional comparison with the previous report. A missing prior report produces no baseline comparison rather than a synthetic baseline.

## Policy Layer

The new `memory_policy` SQLite table is additive and references existing stable memory identifiers. It owns only policy metadata:

- importance score
- tier (`core`, `mtm`, `archive`)
- policy confidence
- source layer and provenance
- promotion reason
- eviction-candidate state
- timestamps

Existing `memory_objects` remains authoritative for object confidence, validity windows, status, and conflict groups. Those fields are read when needed and are not duplicated into policy storage.

Schema creation uses `CREATE TABLE IF NOT EXISTS` and safe column migration. Re-running initialization or installation preserves rows. Policy injection uses upsert semantics and defaults to dry-run; `--apply` is required for writes.

The deterministic importance scorer uses content class and source weighting. Credential-like content may be important, but raw secret values are never logged or copied into policy provenance. Optional LLM scoring is out of scope for v3.5.2 because no provider-neutral response contract is defined.

Decay works on policy confidence only. It returns proposed changes in dry-run mode and updates rows only with `--apply`. Crossing the configured threshold marks an eviction candidate but never deletes source memory.

## gbrain Edge Planning

Hindsight `/stats` exposes aggregate link counts, not individual links, so it is not an edge source. Candidate providers use enumerable governance relations and supported Hindsight data when concrete source and target identities are available.

The edge pipeline is:

1. Load candidates from providers.
2. Normalize source, target, type, score, and provenance.
3. Reject self-links and invalid slugs.
4. Deduplicate candidates and existing edges.
5. Enforce per-page top-k budgets with deterministic score ordering.
6. Print a plan in dry-run mode.
7. Invoke `gbrain link <from> <to> --type <type>` only with `--apply`.

Dry-run is the default. A failed write stops the apply run and returns non-zero. The tool does not automatically unlink or evict existing production edges in v3.5.2.

## Feature-Flagged Extensions

`TEMPORAL_TRUTH_ENABLED=false` exposes validation and interface definitions for current and historical retrieval. Disabled mode performs no query rewriting.

`MTM_ENABLED=false` exposes configuration validation and a no-op dry-run report. It does not create a write buffer or join the maintenance cycle in this release. Those behaviors require a separate design and benchmark gate.

## Installer

The existing three-mode installer remains the single installation path. Additive options control evaluation and policy components. Directory deployment is staged and replaced atomically using the installer's existing rollback pattern.

Installation must:

- deploy importable evaluation modules beside installed scripts;
- initialize policy schema only when requested;
- preserve private registries and existing policy data;
- avoid creating duplicate cron entries;
- use `AGENT_HOME` for all installed paths;
- leave all new feature flags disabled unless explicitly enabled.

Cron registration is explicit and idempotent. Smoke runs weekly, full evaluation monthly, and decay weekly. Commands use installed paths and environment-driven output directories rather than repository paths.

## Security And Privacy

Release scanning covers tracked text files for private keys, token patterns, public IP addresses, production paths, user-identifying strings, and database credentials. Synthetic cases use fictional values such as `<YOUR_API_KEY_HERE>`.

Runtime reports contain case IDs and normalized evidence, not raw secret-bearing memory content. Private registry contents and `.env` files are excluded from source control.

## Verification And Deployment

Verification proceeds in this order:

1. New unit tests fail before implementation and pass after implementation.
2. Existing tests pass unchanged.
3. Installer idempotency tests pass in temporary agent homes.
4. Default smoke and full evaluations produce valid JSON without live services.
5. gbrain dry-run proves no write command is called.
6. Privacy scan reports no release-blocking findings.
7. Code is deployed to production without enabling write features.
8. Default and private production baselines are generated separately.
9. Policy injection and gbrain edge application remain dry-run until their reports are reviewed.
10. Idempotent cron entries are installed and listed.
11. The release commit is pushed and tagged `v3.5.2` only after production acceptance.

If production evaluation fails, cron registration and release publication stop. Deployment rollback restores the previous installed module set; additive policy tables may remain because they do not affect existing services.

## Acceptance Criteria

- The public registry contains 40 correctly distributed, privacy-safe cases.
- CI can run the default evaluator without Hindsight, gbrain, or production data.
- A private registry is discovered only under `AGENT_HOME` and reported separately.
- All five metrics are calculated from normalized evaluated results.
- Policy schema initialization and injection are idempotent and non-destructive.
- gbrain defaults to dry-run and enforces the configured edge budget.
- Phase 2 and Phase 4 are disabled and have no side effects.
- Installer reruns preserve data and avoid duplicate schedules.
- Existing tests plus new tests pass.
- Privacy scan passes before deployment and before push.
- Production baseline artifacts are generated before tag publication.
