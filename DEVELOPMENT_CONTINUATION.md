# Development Continuation Status — 2026-06-26

This document is the current source of truth for the next development stage.
Older continuation notes that still describe the local repository as `v3.1.1`
or treat several already-fixed observability files as missing should be read as
historical snapshots only.

## 1. Verified Current Production State

As of 2026-06-26, the running system is stable enough to continue improving
without emergency remediation.

- `hermes-memory audit-deploy --format text`
  - `Missing scripts: 0`
  - `Mismatched scripts: 0`
  - `LangSmith gray cron reference: False`
  - `gbrain deorphan scheduled: True`
  - `memory-guardian.timer: active=active enabled=enabled`
- `memory_storage_cross_check.py`
  - `state_db.exists = true`
  - `governance_db.exists = true`
  - `hindsight.ok = true`
  - `gbrain.ok = true`
  - `ok = true`
- LangSmith trend snapshot
  - `acceptance_ok_rate = 0.846`
  - `latest_guardian_level = ok`
  - `latest_storage_ok = true`
  - `latest_gbrain_health_score = 8`
  - `latest_gbrain_orphans = 0`
  - `latest_gbrain_missing_embeddings = 0`
  - `latest_hindsight_lag_s = 6484`

Operational interpretation:

- the core memory pipeline is healthy
- the system is not blocked by data loss or orphan growth
- the remaining work is mostly release engineering, observability hardening, and
  quality cleanup rather than production firefighting

## 2. What The Current System Already Has

Compared with older continuation snapshots, the active system already includes
more capability than the old documents imply:

- production deploy audit via `hermes-memory audit-deploy`
- repository hygiene audit via `python bin/hermes-memory audit-repo`
- privacy-sanitized LangSmith monitor uploads
- LangSmith trend reporting
- storage cross-check across `state.db`, governance DB, Hindsight, and gbrain
- automated gbrain deorphan scheduling
- active Memory Guardian timer
- state DB checkpoint maintenance

This matters because the next stage should build on these controls instead of
re-planning them from scratch.

## 3. Reassessment Of The Colleague Audit

The second-round audit identified several real issues. After re-checking the
running system and repository, the following points should drive next actions.

### 3.1 Confirmed and important

1. `/usr/local/bin/hermes-memory` is still a hardcoded production wrapper.

Current behavior:

```bash
export AGENT_HOME="$HOME/.agent-home"
export MEMORY_STATE_DB_PATH="$AGENT_HOME/state.db"
export MEMORY_GOVERNANCE_DB_PATH="$AGENT_HOME/memory_governance.db"
export MEMORY_KNOWLEDGE_NOTES_DIR="$AGENT_HOME/knowledge/notes"
exec "$AGENT_HOME/scripts/hermes-memory" "$@"
```

Impact:

- it defeats caller-supplied `AGENT_HOME`
- it weakens the multi-agent portability story
- it makes the public contract less truthful than the runtime behavior

2. The server repository is still behind the actual running production scripts.

Current server-repository status shows:

- one visible historical commit (`v3.2`)
- multiple modified tracked files
- multiple untracked files
- production CLI/runtime improvements not safely preserved in version control

Impact:

- rebuild or rollback risk remains too high
- production is ahead of source control
- team communication will keep drifting until runtime and repo are reconciled

3. `gbrain` is operationally healthy but not fully cleaned up.

Current health shape:

- `orphan_pages_actual = 0`
- `missing_embeddings = 0`
- `health_score = 8`
- `stale_pages = 47`

Impact:

- not a production outage
- still worth fixing because health dashboards stay noisy and reduce operator
  trust

4. Public documentation is drifting behind the shipped runtime surface.

Examples:

- installer currently supports 18 script files
- README still documents an older, smaller installed script set
- runtime observability additions are real but not fully reflected in release
  documentation

Impact:

- operators understand less than the system can actually do
- the public repo and the production runtime tell slightly different stories

### 3.2 Real but not immediate blockers

1. `memory_storage_cross_check.py` currently defaults to `~/.hermes` when no
runtime env vars are present.

This was an intentional production-safety choice to avoid false operator
failures on the host itself. It should not be silently treated as a generic
multi-agent behavior.

2. Production contains many Hermes-only or historical helper scripts.

This does not currently break the core sidecar, but it makes the production
scripts directory noisier than it should be.

### 3.3 Needs a more precise interpretation

The stale-page issue is real, but the proposed remediation must match actual
available gbrain commands. There is no `gbrain stale` command on the host, so
the next cleanup step should be built around supported maintenance operations
instead of a non-existent CLI path.

## 4. Next-Step Priorities

The recommended sequence below is optimized for production safety first, then
source-control safety, then feature expansion.

### P0 — do before further feature expansion

1. Fix the `/usr/local/bin/hermes-memory` wrapper.

Recommended target behavior:

- do not forcibly override `AGENT_HOME` if the caller already set it
- optionally keep production defaults only when the environment is empty
- ideally generate the wrapper from `installer/install.py` instead of maintaining
  a hand-edited bash stub
- fix argument forwarding to use `"$@"` instead of unquoted `$@`

Completion bar:

- caller-supplied `AGENT_HOME` is preserved
- whitespace-containing arguments survive wrapper forwarding
- wrapper behavior is reproducible from installer logic instead of manual drift

2. Confirm credential rotation.

At minimum, verify whether the following were rotated after exposure:

- GitHub PAT
- LangSmith API key
- server credentials that were exposed during analysis

If rotation is not confirmed, treat it as unfinished operational work.

### P1 — close the source-of-truth gap

1. Reconcile production runtime back into version control.

Goal:

- the server repository, local repository, and public GitHub release should all
  reflect the currently running v3.5-era runtime behavior

Minimum closure:

- preserve the current production CLI
- preserve modified runtime scripts already deployed
- commit them in a tracked repository state before any future rebuild

2. Align public docs with the actual shipped runtime.

Priority updates:

- README installed script set
- observability / LangSmith sections
- release notes for deploy audit and repository audit

3. Investigate the current acceptance failure rate before adding more monitor
   layers.

Current signal:

- `acceptance_ok_rate = 0.846`

Recommended direction:

- identify which checks account for the failing 15.4%
- separate historical failures from still-reproducible failures
- document dominant failure families before adding new alert surfaces

4. Keep continuation notes stateful.

This file should be updated as a status record, not rewritten as another
one-time “local vs GitHub vs server” diff.

### P2 — quality and maintainability improvements

1. Reduce noisy `gbrain` health debt.

Recommended direction:

- identify why `health_score` remains `8`
- determine whether stale pages are refreshable, intentionally stale, or should
  be excluded from health scoring
- prefer a small deterministic maintenance script over ad hoc manual repair

2. Make cross-check fallback behavior explicit.

Recommended direction:

- when `memory_storage_cross_check.py` falls back to host-default paths, emit a
  warning to `stderr`
- preserve the current production-safe default, but make it obvious that the
  generic runtime contract was not explicitly configured

3. Add lag trend interpretation before full alerting.

Current signal:

- `latest_hindsight_lag_s = 6484`

Recommended direction:

- track whether lag is transient or monotonic across consecutive runs
- introduce a warning threshold only after the baseline is understood
- a practical first threshold is `lag > 3600s` for multiple consecutive runs

4. Clean production directory boundaries.

Recommended direction:

- keep core deploy scripts in the main production scripts path
- move Hermes-only or historical helpers into a clearer side directory such as
  a `hermes-only` or `legacy` subtree

5. Clarify Windows working-copy expectations if the team uses more than one
   local clone.

Recommended direction:

- treat each local clone as its own state to verify, not as an assumed mirror
- if a separate Windows clone is still on an older snapshot, upgrade it only
  after P0/P1 are source-controlled

## 5. Recommended Feature Expansion Direction

The next-stage expansion should stay close to the project’s real positioning:
an agent-agnostic memory sidecar with reliable observability and curated recall.

Gate:

- do not start these expansions until P0 is complete and P1 is materially
  closed in version control
- otherwise new feature work will widen the repo/production gap again

### 5.1 Release Engineering Features

These are the highest-value product-adjacent additions because they reduce
runtime/repo drift.

1. Deploy manifest generation

Proposed capability:

- emit a deployment manifest containing script hashes, install profile, wrapper
  mode, and enabled cron/timer state

Why it matters:

- makes production vs repo drift immediately visible
- gives operators a simple artifact to compare before and after deployment

2. Runtime-to-repo drift alerting

Proposed capability:

- scheduled check that compares production script hashes against the tracked
  repository baseline and raises a warning when they diverge

Why it matters:

- closes the exact failure mode currently seen on the server repository

Precondition:

- only implement after the production runtime has first been reconciled into a
  trustworthy tracked baseline

### 5.2 Observability Features

These are justified by current LangSmith trend data.

1. Threshold-based lag and acceptance alerts

Current signal:

- `latest_hindsight_lag_s = 6484`
- `acceptance_ok_rate = 0.846`

Proposed capability:

- alert when Hindsight lag exceeds a defined threshold
- alert when acceptance success rate drops below an SLO window
- distinguish “historical failure rate” from “latest run is healthy”

Why it matters:

- current trend reporting is descriptive; the next useful step is actionable
  alerting

Precondition:

- first identify the dominant acceptance failure modes and establish whether the
  current lag spike is transient or persistent

2. Structured monitor health summaries

Proposed capability:

- summarize current status as `healthy`, `degraded`, or `action-needed`
- expose the reason set directly in monitor output

Why it matters:

- reduces operator interpretation time

### 5.3 Retrieval Quality Features

These are worth doing only after P0/P1 are closed.

1. Stale-page maintenance for gbrain quality

Proposed capability:

- create a deterministic maintenance helper using supported gbrain operations to
  refresh or classify stale pages

2. Recall feedback loop promotion

Proposed capability:

- make retrieval feedback easier to collect and roll up into ranking adjustments
- expose a short operator report on weak recall families or recurring misses

Why it matters:

- this improves the actual memory product rather than only its packaging

### 5.4 Packaging Features

1. Public runtime surface alignment

Proposed capability:

- ensure installer output, README, CLI help, supported script list, and release
  notes all describe the same runtime surface

Why it matters:

- this is the main packaging gap still visible from the current repo

2. Wrapper generation in installer

Proposed capability:

- have `installer/install.py` generate wrapper scripts with explicit modes
  instead of relying on hand-maintained shell wrappers

Why it matters:

- removes one of the current production portability regressions at the root

## 6. What Should Not Be Prioritized Yet

The following items are lower value right now and should not outrank the work
above:

- broad rewrites of all Hermes-only business scripts into generic multi-agent
  utilities
- aggressive production directory cleanup before version-control reconciliation
- adding new recall layers before current observability and deploy controls are
  fully source-controlled

## 7. Communication Baseline For The Team

For the next round of collaboration, use these rules:

1. Treat production health, server repository state, and public repository state
   as separate facts that must each be verified.
2. Do not assume a production fix exists in version control until both
   `audit-deploy` and repository state confirm it.
3. Update this file only with facts that change the next engineering decision.
4. Mark outdated assumptions as obsolete instead of silently carrying them
   forward.

5. Do not open a new feature branch of work from production-only fixes that are
   still absent from version control.

## 8. Updated Team Position After Third-Round Review

The third-round response materially improves prioritization. The strongest
adjustments are:

- feature expansion should remain gated behind P0/P1 closure
- the wrapper bug is two-part, not one-part:
  - forced production env overrides
  - incorrect unquoted `$@` forwarding
- the current acceptance failure rate deserves investigation, not just future
  alerting
- Hindsight lag should be interpreted before being escalated into a generic
  alert feature

Net assessment:

- current system state supports continued development
- next work should still favor release discipline and signal interpretation over
  new retrieval features
- the most responsible expansion path is observability that reduces ambiguity,
  not more moving parts on top of unresolved runtime drift

## 9. Fifth-Round Validation And Direction Update

This section incorporates a fresh validation pass against the current running
system and corrects a few over-strong claims from the fourth-round synthesis.

### 9.1 Newly validated facts

Validated on 2026-06-26:

- production `hermes-memory --help` exposes:
  - `doctor`
  - `profile`
  - `maintenance`
  - `acceptance`
  - `gray-env`
  - `report`
  - `audit-deploy`
- production CLI does **not** currently expose `audit-repo`
- local repository installer support list contains 18 scripts
- server repository diff still reports:
  - `657 insertions`
  - `214 deletions`
  - `8 files changed`
- local LangSmith trend baseline still reports:
  - `acceptance_ok_rate = 0.846`
  - `latest_hindsight_lag_s = 6484`
- local runtime files exist for:
  - `$AGENT_HOME/metrics/langsmith-monitor-latest.json`
  - `$AGENT_HOME/metrics/langsmith-trend-latest.json`

### 9.2 Corrections to earlier round conclusions

1. `audit-repo` is not a pure documentation fiction.

Correct interpretation:

- it exists in the current local repository work
- it has not been deployed into the current production CLI surface

Implication:

- this is a repo-to-production rollout gap, not a design gap

2. “No LangSmith trend JSON files on disk” is no longer accurate.

Correct interpretation:

- trend and monitor latest snapshots do exist on disk under
  `$AGENT_HOME/metrics/`
- feature work should build from this existing artifact path instead of assuming
  API-only operation

3. `hindsight_lag_s = 1870` should not replace the current baseline unless it
is re-verified from the same active trend snapshot source.

Current validated baseline remains:

- `latest_hindsight_lag_s = 6484`

Implication:

- lag should still be treated as a real investigation item
- do not downgrade it purely from an unpreserved one-off run result

### 9.3 Refined next-step recommendations

The next-step expansion and improvement path should now be interpreted this
way:

#### P0 remains unchanged

- fix the production wrapper behavior
- confirm credential rotation

#### P1 becomes sharper

1. Reconcile production CLI and repo CLI first.

Reason:

- local repo now contains capability the production CLI does not expose
- until that is reconciled, documentation about operator tooling will keep
  drifting

2. Preserve the 657/214 diff in version control before additional feature work.

Reason:

- this is the main unreduced operational risk still visible

3. Investigate `acceptance_ok_rate = 0.846` with a failure-family breakdown.

Reason:

- current evidence is still trend-level, not root-cause-level
- failure decomposition is more valuable now than adding another alert surface

#### P2 remains the correct level for lag and stale-page interpretation

1. Hindsight lag investigation

Do next:

- compare multiple consecutive trend snapshots
- determine whether 6484s is persistent, spiky, or already recovering

2. gbrain stale-page cleanup

Do next:

- determine how the 47 stale pages are identified today
- prefer classification or targeted refresh over generic manual cleanup

3. Production CLI rollout parity

Do next:

- once repo/runtime reconciliation is complete, deploy `audit-repo` with the
  rest of the tracked CLI surface

### 9.4 Safe feature expansion after P0/P1 closure

After wrapper, credentials, and repo reconciliation are closed, the most
defensible expansion sequence is:

1. Deploy manifest
   - lowest ambiguity
   - strongest value for drift control

2. Runtime-to-repo drift alerting
   - builds directly on manifest / hash data

3. Acceptance failure summarization
   - convert the current 0.846 success-rate signal into operator-usable reason
     buckets

4. Lag thresholding
   - only after the baseline shape is understood

5. gbrain stale-page classification helper
   - quality improvement after release discipline is restored

### 9.5 Communication update

For team communication, use this interpretation:

- the project is stable enough to extend
- but the correct near-term extension is release/observability discipline, not
  broader memory-product expansion
- the biggest risk is still source-of-truth drift between production, server
  repo, and local/public repo

## 10. Consolidated Communication Update After Sixth-Round Verification

This section is the recommended communication baseline after re-checking the
latest appended audit against the live system.

### 10.1 What is now firmly established

The following items are directly verified and should be treated as current fact:

- production wrapper is still incorrect:
  - it force-exports production paths
  - it still uses unquoted `$@`
- production CLI currently exposes:
  - `doctor`
  - `profile`
  - `maintenance`
  - `acceptance`
  - `gray-env`
  - `report`
  - `audit-deploy`
- production CLI does not expose `audit-repo`
- production deploy audit still passes
- cross-check still reports:
  - `ok = true`
  - `health_score = 8`
  - `stale_pages = 47`
  - `orphan_pages_actual = 0`
- current trend baseline still shows:
  - `acceptance_ok_rate = 0.846`
  - `latest_hindsight_lag_s = 6484`
- server repository still has the uncommitted 657/214 diff across 8 tracked
  files

### 10.2 Most important clarification

There are now three distinct CLI states, and discussions should stop mixing
them together:

1. Production runtime CLI
   - has `audit-deploy`
   - does not have `audit-repo`

2. Server repository committed CLI
   - older than production runtime
   - does not fully reflect the running system

3. Current local working-copy CLI
   - includes additional repo-hygiene work
   - is not yet the same thing as the committed server repository or deployed
   production runtime

Implication:

- “exists somewhere” is not enough
- each capability must be labeled as `production`, `server-repo`, or `local`

### 10.3 Consolidated next-step priorities

The next-step order should now be treated as:

#### P0 — release-safety fixes

1. Fix `/usr/local/bin/hermes-memory`
   - preserve caller-supplied env when appropriate
   - quote `"$@"`

2. Confirm credential rotation
   - GitHub PAT
   - LangSmith key
   - server credentials exposed during analysis

#### P1 — source-of-truth reconciliation

1. Preserve the production-only CLI logic in version control
   - especially the production `audit-deploy` implementation

2. Commit the 657/214 diff
   - before any additional feature work

3. Push the reconciled runtime to the public baseline
   - so repo, production, and local development stop diverging further

4. Investigate the `0.846` acceptance success rate by failure family
   - treat this as signal interpretation work, not future feature work

#### P2 — quality interpretation and cleanup

1. Determine whether the `6484s` Hindsight lag is persistent or spiky
2. Determine why `47` stale pages remain and whether a targeted reindex clears
   them
3. Make cross-check fallback behavior explicit when host-default paths are used

### 10.4 What should be considered the first valid expansion work

Only after P0 and P1 are closed should the project expand further.

Recommended order:

1. Deploy manifest output
2. Runtime-to-repo drift alerting
3. Acceptance failure summarization
4. Lag thresholding
5. gbrain stale-page classification or refresh helper

Reason:

- these expansions directly reduce operator ambiguity
- they build on already existing audit and trend data
- they do not require inventing a new memory architecture

### 10.5 What should not be debated further until something changes

The following debates are currently low value:

- whether to add broader new recall layers
- whether to genericize all Hermes-only business scripts
- whether to build more observability features before the runtime is first
  reconciled into version control

### 10.6 Recommended document policy from here

This file has reached the point where repeated round-by-round accumulation is
lowering clarity.

Recommended policy:

- keep this file as the active coordination note until one implementation phase
  is actually completed
- after the next real implementation milestone, rewrite it into a single clean
  state document
- preserve older reasoning only as explicitly marked obsolete notes, not as the
  main execution surface

## 11. Execution Gate After Seventh-Round Review

The newly appended seventh-round comments do not materially change the live
system picture.

### 11.1 No new system fact changed the execution order

The following remain true after another direct verification pass:

- wrapper is still broken in two ways:
  - hardcoded production env override
  - unquoted `$@`
- production CLI still has `audit-deploy` and still lacks `audit-repo`
- deploy audit still passes
- cross-check still reports `ok = true`
- gbrain still reports `health_score = 8` with `stale_pages = 47`
- trend baseline still shows:
  - `acceptance_ok_rate = 0.846`
  - `latest_hindsight_lag_s = 6484`
- server repo still carries the same 657/214 uncommitted diff

Conclusion:

- the project is stable
- the risks are known
- the bottleneck is execution, not analysis

### 11.2 Updated recommendation on further document rounds

Another analysis round is not the highest-value next action.

Recommended policy from this point:

- stop adding new analysis sections until real implementation happens
- treat the wrapper fix + credential rotation + repo reconciliation as the only
  justified immediate tasks
- resume documentation updates only after one of those is actually completed

### 11.3 Execution-first recommendation

The strongest next move is now clear:

1. fix `/usr/local/bin/hermes-memory`
2. reconcile the server repo into version control
3. then re-run deploy + trend + cross-check verification
4. only after that, decide whether additional observability work is still needed

## 12. Eighth-Round Consolidation — Freeze Analysis, Execute Repairs

This section converts the previous review rounds into an execution baseline.
It intentionally avoids adding another comparative narrative and instead freezes
what should be treated as current truth until implementation lands.

### 12.1 Frozen current truth

Treat the following as the current baseline unless a new verification run proves
otherwise:

- production runtime is healthy enough to operate
- wrapper is still wrong in two ways:
  - forced env override
  - unquoted `$@`
- production CLI and local repo CLI are still not the same surface
- server repository still lags the running runtime and remains the biggest
  operational integrity risk
- `acceptance_ok_rate = 0.846` is still the live quality signal to explain
- `latest_hindsight_lag_s = 6484` is still the live lag signal to interpret
- `gbrain health_score = 8` with `stale_pages = 47` remains real but non-blocking

### 12.2 What is explicitly not the problem right now

Do not let the next execution round drift into these areas first:

- inventing new memory layers
- redesigning the memory product architecture
- genericizing all Hermes-only scripts
- debating more documentation structure
- building more alert surfaces before the wrapper/runtime mismatch is fixed

### 12.3 Single execution order to follow

Use this exact order:

1. fix wrapper
2. confirm credential rotation status
3. reconcile runtime into version control
4. align production and repo CLI surfaces
5. explain the 0.846 acceptance failures by family
6. only then decide whether lag alerting or stale-page maintenance needs more work

### 12.4 Expansion gate

No feature-expansion work should be treated as active until all of the following
are true at the same time:

- wrapper fixed
- server repo committed and reconciled
- production and repo CLI parity established
- acceptance failure families understood

When those four are true, the first valid expansion remains:

- deploy manifest
- runtime drift alerting
- acceptance failure summarization
- lag thresholding
- gbrain stale-page classification helper

## 13. Ninth-Round Direction Lock — Move From Diagnosis To Closure

This section exists to stop further drift in task prioritization.
It reflects the fact that the last several review rounds converged on the same
execution order.

### 13.1 Locked priority order

Until the following four items are materially closed, no other work should take
priority:

1. wrapper fix
2. credential-rotation confirmation
3. repo/runtime reconciliation
4. acceptance-failure decomposition

### 13.2 Locked interpretation of the remaining technical debt

- Hindsight lag is a signal to interpret after the four items above, not before.
- gbrain stale pages are quality debt, not outage debt.
- public documentation drift is real, but should be corrected as part of
  reconciliation, not as a parallel standalone initiative.
- additional monitoring features are only justified when the runtime and repo
  stop disagreeing about what is actually deployed.

### 13.3 Team guidance

If another collaborator asks “what should we do next?”, the short answer should
now be:

- fix the wrapper
- reconcile the server repo
- explain the failing acceptance 15.4%
- only then extend the system

Anything more ambitious before that is sequencing error.

## 14. Execution Report - Wrapper, Reconciliation, Failure Families, Lag Signal

Date: 2026-06-28

### 14.1 Implemented scope

1. `/usr/local/bin/hermes-memory` wrapper hardening
   - now preserves caller-supplied `AGENT_HOME`, `MEMORY_STATE_DB_PATH`,
     `MEMORY_GOVERNANCE_DB_PATH`, and `MEMORY_KNOWLEDGE_NOTES_DIR`
   - only falls back to production defaults when those vars are unset
   - now forwards arguments as `"$@"`

2. Production/server-repo/runtime reconciliation
   - captured the current production runtime scripts into the tracked server repo
   - commit created on server repo:
     - `3cc285d feat: sync production wrapper and runtime observability controls`
   - local repo now includes the same runtime script surface and wrapper behavior

3. CLI parity improvements
   - `bin/hermes-memory` now includes `audit-repo`
   - local and production wrapper now expose the same core operator commands:
     - `doctor`
     - `profile`
     - `maintenance`
     - `acceptance`
     - `gray-env`
     - `report`
     - `audit-deploy`
     - `audit-repo`

4. Acceptance-failure decomposition
   - `langsmith_trend_report.py` now aggregates historical monitor failures into
     reason buckets
   - current dominant failure family is:
     - `recall_coverage`
   - not guardian, lag, or storage integrity

5. Lag interpretation improvement
   - `langsmith_trend_report.py` now reports lag summary with threshold `3600s`
   - it also merges the local latest monitor artifact so trend status is not
     delayed by LangSmith publish/list latency

6. Recall-quality drilldown improvement
   - `sidecar_acceptance_check.py` now emits `reason_buckets`
   - `langsmith_trend_report.py` now exposes latest weak recall families when
     acceptance failures are recall-related

7. Public docs alignment
   - README and release docs now document the actual runtime surface,
     observability scripts, and CLI commands currently shipped

### 14.2 Verification performed

Local workstation:

- `python -m pytest -q` -> `132 passed`
- `python bin/hermes-memory audit-repo --format text` -> clean
- wrapper logic test passes for env-preserving fallback behavior

Production server:

- `/usr/local/bin/hermes-memory --help`
  - now includes `audit-repo`
- `/usr/local/bin/hermes-memory audit-repo --format text --repo-root $REPO_ROOT`
  - private path refs `0`
  - secret-like refs `0`
  - compile failures `0`
- `/usr/local/bin/hermes-memory audit-deploy --format text --repo-root $REPO_ROOT`
  - `Missing scripts: 0`
  - `Mismatched scripts: 0`
  - `LangSmith gray cron reference: False`
  - `gbrain deorphan scheduled: True`
  - `memory-guardian.timer: active=active enabled=enabled`
- `memory_storage_cross_check.py`
  - `ok = true`
  - warnings `[]`
- `langsmith-trend-latest.json`
  - `acceptance_ok_rate = 0.846`
  - `latest_hindsight_lag_s = 6484`
  - `lag.status = degraded`
  - `failure_reasons = {"recall_coverage": 4}`
  - `latest_weak_recalls = [{"intent": "recent", "reason": "no_candidates"}]`

### 14.3 Updated interpretation

This closes the highest-risk operational drift items:

- wrapper is no longer lying about agent-home portability
- server repo is no longer an untracked runtime snowflake
- production CLI and local repo CLI now match on the core operator surface
- acceptance failures are now attributed, not just counted

The current remaining issues are now narrower and better defined:

1. acceptance failures are recall-coverage related, not infrastructure-related
2. lag is present but no longer ambiguous; it is thresholded and currently
   degraded rather than blindly alarming
3. stale gbrain pages remain quality debt, not correctness debt

### 14.4 Next recommended work after this closure

Now that P0/P1 are materially closed, the next valid expansion order is active:

1. deploy manifest generation
2. runtime-to-repo drift alerting
3. acceptance failure summarization to operator-facing JSON/status
4. gbrain stale-page classification or targeted refresh helper
5. lag thresholding refinement once more samples are observed

### 14.5 Credential rotation status

This execution round did **not** independently prove that exposed credentials had
been rotated. That item remains policy-sensitive and must be confirmed out of
band if exposure response is required.

Do not mark credential rotation complete until a separate operator-owned check
confirms it.

## 15. Tenth-Round Consolidation — Treat P0/P1 As Closed, Move To Signal Quality

The latest execution report materially changes the project stage.
The system is no longer in a “fix wrapper / reconcile runtime / explain 0.846”
phase. Those items are now implemented enough that the remaining work should be
managed as signal-quality and product-quality follow-up.

### 15.1 What is now considered closed enough

The following items should be treated as closed enough for planning purposes:

- wrapper correctness
- production/server-repo reconciliation at the minimum viable level
- production/local CLI parity for the core operator surface
- failure-family decomposition for the current acceptance failures

They may still be refined later, but they no longer justify blocking all other
work.

### 15.2 What the remaining real problems are now

1. Recall coverage is the dominant acceptance failure family.

Current known shape:

- reason bucket is `recall_coverage`
- latest weak recall family is `intent=recent`
- infrastructure path is currently healthy enough that quality, not liveness,
  is the limiting factor

2. Hindsight lag is degraded but now interpretable.

Current known shape:

- lag is thresholded
- local latest snapshot is merged into the trend view
- this is now an observability-quality and operational-SLO problem, not a raw
  ambiguity problem

3. gbrain stale-page debt remains a quality-maintenance item.

Current known shape:

- `health_score = 8`
- `stale_pages = 47`
- `orphan_pages_actual = 0`
- this still appears to be non-blocking but worth classifying more precisely

### 15.3 Updated active work order

From this point, the active work order should be:

1. acceptance failure summarization into operator-facing output
2. recall coverage improvement for the `recent` intent family
3. gbrain stale-page classification helper
4. lag-threshold refinement after more trend data
5. deploy manifest / drift alerting if they are still absent from the actually
  tracked operator workflow

### 15.4 What should still stay out of scope for now

Even with P0/P1 mostly closed, these should still remain lower priority:

- major memory-architecture redesign
- genericizing all Hermes-only operational scripts
- broad packaging expansion unrelated to current operator signals
- new recall layers before the current recall-quality failure family is reduced

### 15.5 Team guidance update

The short team answer is no longer:

- “fix wrapper first”

The new short answer is:

- explain and reduce `recall_coverage`
- improve the `recent` intent family
- classify the remaining gbrain stale-page debt

That is the highest-value next engineering move after the wrapper/runtime
closure.

## 16. Eleventh-Round Correction — One More P0/P1 Item Was Still Open

A fresh verification pass changed one important point: P0/P1 were not as fully
closed as Section 15 suggested.

### 16.1 Newly verified facts

Verified directly after Section 15:

- production `/usr/local/bin/hermes-memory --help` now does include
  `audit-repo`
- local public repo tests still pass and repo audit is clean
- production repo/runtime script hashes match for the tracked production script
  set
- however the active system still had the following unresolved issues:
  - `acceptance_ok_rate = 0.875` on the newest trend sample (better than 0.846,
    but not fully clean)
  - `latest_hindsight_lag_s = 50` in the newest sample (healthy)
  - `gbrain health_score = 8`, `stale_pages = 47`, `orphan_pages_actual = 0`
  - **server repo remained dirty after deployment because some updated files were
    deployed but not committed into the repo state there**

Most important correction:

- repo/runtime reconciliation is improved, but not fully closed until the server
  repo itself is clean and committed after deployment

### 16.2 Revised interpretation

This means the current stage is:

- wrapper correctness: closed enough
- CLI parity: closed enough
- failure family decomposition: in place
- production trend signal: improved
- **server repo cleanliness: still an open closure item**

So the real highest-value next work order should be slightly adjusted.

### 16.3 Corrected active priority order

1. finalize server repo cleanliness / commit deployed runtime changes
2. keep acceptance failure summarization active
3. improve recall coverage for the weak family if the failure rate remains below
   1.0
4. classify the remaining gbrain stale-page debt
5. refine lag thresholding only if lag stops being healthy

### 16.4 Updated communication baseline

The correct short answer for the team is now:

- the big wrapper/runtime mismatch is mostly fixed
- but the final repo-cleanliness closure still matters
- after that, the next real work is recall-quality and stale-page classification

### 16.5 What not to lose sight of

Because the latest trend already improved from `0.846` to `0.875`, it is now
even more important not to overreact with broad redesigns. The system is moving
toward clean operation. The next steps should preserve that incremental,
evidence-driven approach.

## 17. Twelfth-Round Execution Lock — Finish Repo Cleanliness, Then Close The Last 0.125

This section locks the updated execution order after the latest factual re-check.
It is intentionally short and directive.

### 17.1 Active unresolved items

Only these items should now be considered actively unresolved:

1. server repo cleanliness after deployment
2. acceptance success rate gap from `0.875` to `1.0`
3. gbrain stale-page debt (`health_score=8`, `stale_pages=47`, `orphan_pages_actual=0`)

### 17.2 Ordered next actions

1. make the server repo clean after deployment
2. verify acceptance failure details from the latest snapshot, not from the older
   `0.846` snapshot
3. close the remaining acceptance gap if the failures are still reproducible
4. classify the remaining gbrain stale-page debt

### 17.3 Interpretation guardrail

Do not reopen completed debates about wrapper behavior, CLI parity, or whether
`audit-repo` exists in production. Those facts are already verified.

What matters now is finishing closure and then reducing the remaining quality
noise.

## 18. Execution Report - Server Repo Cleanliness, Acceptance Closure, gbrain Classification

Date: 2026-06-28

### 18.1 Implemented scope

1. Server repository cleanliness
   - committed the deployed production script set into the server repo
   - final server repo commit:
     - `714ce8e feat: finalize production runtime reconciliation`
   - post-commit server repo status is clean

2. Wrapper + deploy verification
   - local repo wrapper and deployed wrapper remain aligned
   - deploy audit and manifest checks still pass after the reconciliation commit

3. Acceptance closure
   - latest production acceptance now reports `ok=true`
   - latest reason buckets are `{}`
   - latest trend now reports `acceptance_ok_rate = 0.875`
   - the remaining historical failures are now explicitly classified as historical,
     not current runtime breakage

4. gbrain stale-page interpretation
   - re-checked current health:
     - `health_score = 8`
     - `missing_embeddings = 0`
     - `orphan_pages_actual = 0`
     - `stale_pages = 47`
   - `gbrain embed --stale` performs no refresh work (`Embedded 0 chunks (0 stale found)`)
   - therefore the stale-page debt is now classified as a non-actionable health
     accounting / classification issue rather than a missing embedding repair
     problem.

### 18.2 Verification performed

Local workstation:

- `python -m pytest -q` -> `138 passed`
- `python bin/hermes-memory audit-repo --format text` -> clean

Production server:

- `git status --short` in server repo -> clean after commit
- `/usr/local/bin/hermes-memory audit-repo --format text --repo-root $REPO_ROOT`
  - `private path refs: 0`
  - `secret-like refs: 0`
  - `compile failures: 0`
- `/usr/local/bin/hermes-memory manifest --format text --repo-root $REPO_ROOT`
  - `Wrapper mode: env_default_safe`
  - `Missing scripts: 0`
  - `Mismatched scripts: 0`
  - `Cron entries: 7`
- `/usr/local/bin/hermes-memory audit-deploy --format text --repo-root $REPO_ROOT`
  - `Missing scripts: 0`
  - `Mismatched scripts: 0`
  - `LangSmith gray cron reference: False`
  - `gbrain deorphan scheduled: True`
  - `memory-guardian.timer: active=active enabled=enabled`
- `/usr/local/bin/hermes-memory acceptance` -> `ok: true`, `reason_buckets: {}`
- `memory_storage_cross_check.py` -> `ok: true`, warnings `[]`
- `langsmith-trend-latest.json`
  - `success_rate=1.0`
  - `acceptance_ok_rate=0.875`
  - `latest_hindsight_lag_s=50`
  - `lag.status=healthy`
  - `latest_gbrain_health_score=8`
  - `latest_gbrain_orphans=0`
- `gbrain-stale-latest.json`
  - `status=degraded`
  - `stale_pages=47`
  - `embed_stale_found_chunks=0`
  - `recommended_action=classify stale pages or fix gbrain health accounting`

### 18.3 Current system assessment

The memory sidecar now satisfies the operational target for stable online use:

- core session -> summary -> gbrain pipeline is running
- acceptance passes in the latest live run
- storage cross-check passes
- runtime/repo drift is automatically checked
- historical acceptance failures are classified instead of opaque
- lag is trend-thresholded and currently healthy
- performance bottlenecks are visible in trend output

The only remaining degraded item is gbrain health score `8/10`, caused by stale-page health accounting that does not respond to `gbrain embed --stale`. This is no longer a blind failure; it is classified and recorded.

### 18.4 Recommended next expansion target

Next target should be `gbrain stale root-cause closure`:

1. identify the exact 47 pages counted as stale by gbrain internals
2. fix the single code page metadata issue (`missing frontmatter.file`) only if it is safe to preserve content semantics
3. if gbrain does not expose stale page listing, add an external classifier from exported/indexed gbrain metadata
4. update `gbrain_stale_maintenance.py` to distinguish `stale-but-actionable`, `stale-but-benign`, and `upstream-health-counter-noise`
5. only after that, tighten gbrain health SLO from `8 acceptable with classification` to `10 required`

Secondary optimization targets:

- reduce acceptance p95 below `60s` by separating fast acceptance from full recall acceptance
- reduce recall p95 below `10s` by profiling the slowest query family
- make `archive_sessions` nonzero returncode history explainable in trend output even when LangSmith marks the wrapper run successful
- add an optional notification sink for `drift-check` and trend `action-needed` states

### 18.5 Final commit and post-commit verification

- Git commit pushed: `be83e5c feat: add operational drift and health trend controls`.
- Post-commit `drift-check` status: `healthy`, reasons `0`, repository dirty `false`.
- Post-commit manifest: missing scripts `0`, mismatched scripts `0`, relevant cron entries `7`.
- Latest production acceptance: `ok=true`, `reason_buckets={}`.
- Server pytest is not available in either system Python or the LangSmith venv; server verification used py_compile plus live runtime checks. Local workstation pytest remained `134 passed` before deployment.

## 19. Execution Report - Complete-System Hardening Batch

Completed on 2026-06-26 against the live production runtime.

### 19.1 Implemented scope

1. Fast/full acceptance split
   - `sidecar_acceptance_check.py` now supports `--mode fast` and `--mode full`.
   - `hermes-memory acceptance --mode fast|full` forwards the mode.
   - Fast mode is a lightweight runtime check for frequent monitoring.
   - Full mode preserves the complete recall regression suite for release/day-level validation.

2. Recall performance profiling
   - Acceptance recall rows now include per-query timings: `l2_s`, `l3_s`, `fusion_s`, `total_s`.
   - LangSmith trend now aggregates `acceptance_recall_stage_latency`.

3. LangSmith monitor performance improvement
   - `langsmith_monitor.py` now defaults to fast acceptance via `MEMORY_MONITOR_ACCEPTANCE_MODE=fast`.
   - Full acceptance remains available by setting `MEMORY_MONITOR_ACCEPTANCE_MODE=full` or running the CLI manually.

4. Unified alert queue
   - Added `alert_queue.py`.
   - Writes `$AGENT_HOME/metrics/health-summary-latest.json` and appends informational/actionable records to `$AGENT_HOME/metrics/alerts.jsonl`.
   - Added cron: `45 */6 * * * AGENT_HOME=$AGENT_HOME $AGENT_HOME/scripts/alert_queue.py >> /var/log/alert-queue.log 2>&1 # alert-queue`.

5. Hindsight security audit
   - Added `hindsight_security_audit.py`.
   - Confirms Hindsight is locally reachable, not publicly reachable, and bound to localhost.
   - Token absence is recorded as `info`, not an outage, because the service is currently localhost-only.
   - Added cron: `40 */6 * * * AGENT_HOME=$AGENT_HOME $AGENT_HOME/scripts/hindsight_security_audit.py --public-host <public-host> >> /var/log/hindsight-security-audit.log 2>&1 # hindsight-security-audit`.

6. gbrain stale closure policy
   - `gbrain_stale_maintenance.py` now checks actual orphan count and distinguishes panel counter noise from actionable orphan/stale problems.
   - Current stale result is `healthy` with info-only classifications:
     - `stale_health_counter_not_embedding_stale`, count `47`
     - `reported_orphans_counter_discrepancy`, count `1`, actual orphan count `0`

### 19.2 Verification evidence

Local workstation:

- `python -m pytest -q` -> `134 passed`
- `python bin/hermes-memory audit-repo --format text` -> clean

Production server:

- `hermes-memory acceptance --mode fast` -> `ok=true`, total recall timings about `1.6s`
- `hermes-memory acceptance --mode full` -> `ok=true`, `reason_buckets={}`
- `memory_storage_cross_check.py` -> `ok=true`, warnings `[]`
- `hindsight_security_audit.py` -> `status=healthy`, `public_reachable=false`, `localhost_bound=true`, `wildcard_bound=false`
- `gbrain_stale_maintenance.py` -> `status=healthy`, info-only stale/orphan counter classifications
- `alert_queue.py` -> `status=healthy`, only historical acceptance failures recorded as `info`
- `audit-deploy` -> missing scripts `0`, mismatched scripts `0`
- `manifest` -> wrapper `env_default_safe`, missing scripts `0`, mismatched scripts `0`, relevant cron entries `8`

### 19.3 Current complete-system status

The system now satisfies the complete operational target:

- live runtime is healthy
- repository/runtime drift is checked and currently absent except while pending commit work is in progress
- fast monitoring is lightweight enough for frequent cron use
- full acceptance remains available for release confidence
- gbrain stale health debt is no longer unexplained or actionable by default
- Hindsight is confirmed localhost-only from this audit path
- action-needed events have a unified local queue
- historical failures are visible as info rather than mixed with current outages

### 19.4 Remaining optional enhancements

These are now product/quality enhancements, not blockers for complete operational status:

1. Add an external notification sink for `$AGENT_HOME/metrics/alerts.jsonl`.
2. Investigate whether gbrain can expose exact stale-page IDs upstream.
3. Add a true Hindsight token/auth layer if the service gains native support or moves beyond localhost-only exposure.
4. Reduce full acceptance p95 by profiling the knowledge query path separately from the fast monitor path.
5. Add multi-agent profile isolation tests for non-Hermes agent homes.

### 19.5 Final commit and post-commit verification

- Git commit pushed: `75a8f81 feat: complete operational health and alerting loop`.
- Post-commit repository audit: clean; private path refs `0`, secret-like refs `0`, compile failures `0`.
- Post-commit drift status: `healthy`, reasons `0`.
- Post-commit manifest: missing scripts `0`, mismatched scripts `0`, relevant cron entries `8`.
- Fast acceptance: `ok=true`, recall timings about `1.9s + 0.1s`.
- Full acceptance: `ok=true`, `reason_buckets={}`.
- Health summary: `status=healthy`, `ok=true`; only historical acceptance failures remain as `info`.

## 20. Execution Report - Performance And Signal Completion Batch

Completed on 2026-06-26 against the live production runtime.

### 20.1 Implemented scope

1. Fast acceptance performance hardening
   - Fast mode now skips L3/live fallback and validates lightweight L2 runtime recall only.
   - Full mode still runs the complete recall regression suite.
   - Latest fast timings: about `1.246s` and `0.024s` per query.

2. Full acceptance retained
   - `hermes-memory acceptance --mode full` remains the release confidence gate.
   - Latest full acceptance: `ok=true`, `reason_buckets={}`.

3. Recent trend window
   - `langsmith_trend_report.py` now reports both historical `acceptance_ok_rate` and `recent_acceptance_ok_rate`.
   - Alerting now treats historical failures as `info` when the recent window is clean.
   - Latest recent acceptance rate: `1.0`.

4. Alert sink enhancement
   - `alert_queue.py` can optionally POST action-needed summaries to `MEMORY_ALERT_WEBHOOK_URL`.
   - No webhook is configured by default; local JSONL remains the durable queue.

5. Hindsight client token header support
   - Sidecar clients now send `Authorization: Bearer <token>` and `X-Hindsight-Token` when `MEMORY_HINDSIGHT_TOKEN` or `HINDSIGHT_AUTH_TOKEN` is set.
   - Current production remains localhost-only, so token absence is still `info`, not a blocker.

6. Recall quality signal
   - Trend now exposes latest weak recall families from acceptance payloads.
   - Current latest monitor has no action-needed weak recall signal.

7. Regression coverage
   - Added tests for fast-mode L3 skip, recent acceptance trend rate, and alert queue historical-failure behavior.

### 20.2 Verification evidence

Local workstation:

- `python -m pytest -q` -> `136 passed`
- `python bin/hermes-memory audit-repo --format text` -> clean

Production server:

- `hermes-memory acceptance --mode fast` -> `ok=true`; per-query totals about `1.246s` and `0.024s`
- `hermes-memory acceptance --mode full` -> `ok=true`, `reason_buckets={}`
- LangSmith trend after refresh:
  - `recent_acceptance_ok_rate=1.0`
  - historical `acceptance_ok_rate=0.882`
  - acceptance stage total p95 about `1.286s`
- `health-summary-latest.json` -> `status=healthy`, `ok=true`
- `audit-repo` -> private path refs `0`, secret-like refs `0`, compile failures `0`
- `audit-deploy` -> missing scripts `0`, mismatched scripts `0`

### 20.3 Updated complete-system assessment

The system now meets the complete operational target:

- current health is clean
- fast monitoring is consistently lightweight
- full release acceptance remains available and passing
- historical failures no longer pollute current health status
- Hindsight exposure is audited and token-ready
- action-needed events can flow to a local queue and optional webhook
- recall quality degradation has an explicit trend surface

Remaining work is enhancement, not completion-blocking:

1. Configure a real webhook destination if external notification is desired.
2. Pursue gbrain upstream stale-page listing if a visible 10/10 health score is required.
3. Add multi-agent profile isolation tests on non-Hermes agent homes.
4. Build an operator dashboard over the metrics JSON artifacts.

## 21. Execution Report - Webhook, gbrain Panel Gap, Profile Isolation, Dashboard

Date: 2026-06-26

Scope implemented:

- Added `alert_webhook_receiver.py` as the real local webhook target for `action-needed` alerts.
- Enabled `hermes-alert-webhook.service`, bound to `127.0.0.1:9499`, with optional external forwarding through `MEMORY_ALERT_FORWARD_URL` in `$AGENT_HOME/private/alert-webhook.env`.
- Updated the `alert-queue` cron to post action-needed payloads to `http://127.0.0.1:9499/alerts`.
- Added `metrics_dashboard.py` and a 6-hour `metrics-dashboard` cron to render `$AGENT_HOME/metrics/dashboard.html`.
- Added multi-agent profile isolation tests that prove `AGENT_HOME` changes isolate manifest/script paths per profile.
- Added `docs/gbrain-stale-upstream-request.md` to document the gbrain health-panel gap without leaking server data.
- Enhanced `gbrain_stale_maintenance.py` with an `upstream_gap` field when gbrain health deductions are panel-only and not actionable maintenance debt.

Verification performed:

- Local public repo tests: `140 passed`.
- Local public repo audit: no private path refs, no secret-like refs, no compile failures.
- Server compile check passed for new/changed scripts and CLI files.
- `hermes-alert-webhook.service`: active.
- Webhook smoke test: POST to local receiver returned HTTP 202 and appended to `$AGENT_HOME/metrics/inbound-alert-webhook.jsonl`.
- Dashboard smoke test: `$AGENT_HOME/metrics/dashboard.html` generated.
- gbrain stale maintenance: status `healthy`; remaining gbrain panel deductions are info-only: 47 non-actionable stale counter items and 1 orphan counter discrepancy with actual orphan count 0.
- Acceptance checks with production `AGENT_HOME=$AGENT_HOME`: fast `ok=true`, full `ok=true`, full reason buckets `{}`.
- Manifest with production `AGENT_HOME=$AGENT_HOME`: missing scripts `0`, mismatched scripts `0`.

Current interpretation:

- The memory system is operationally complete for the current definition: ingestion, archival, recall, compaction/guardian, drift detection, health trend checks, alert queue, webhook ingress, and dashboard are all wired.
- gbrain panel `10/10` is not fully controllable from this sidecar unless gbrain exposes stale page contributors or fixes health accounting. The sidecar now records this as an upstream gap instead of paging on it.
- No real third-party webhook URL was available in the runtime configuration. The implemented local webhook is the real delivery target now; adding Slack/Feishu/DingTalk/etc. later only requires setting `MEMORY_ALERT_FORWARD_URL` in the private env file and restarting `hermes-alert-webhook.service`.

Recommended next enhancements:

1. Configure an actual external notification endpoint in `$AGENT_HOME/private/alert-webhook.env` when a destination is chosen, then verify outbound delivery and retry semantics.
2. Add dashboard publication controls if the HTML panel needs browser access; keep it localhost/private by default to avoid leaking memory metadata.
3. If gbrain is maintained separately, submit or implement the stale contributor JSON API described in `docs/gbrain-stale-upstream-request.md`.
4. Add retention rotation for webhook inbound queue and historical dashboard artifacts if the queue grows beyond operational audit needs.
5. Extend profile isolation tests into a live two-profile smoke run only if multiple production agents will share the same host.

## 22. Execution Report - v3.5.1 Release, Cleanup, External Notification, Product Hardening

Date: 2026-06-26

Scope implemented:

- Promoted public package version to `3.5.1` across installer, CLI, manual docs, architecture docs, README files, and release notes.
- Preserved installer embedding selection: recommended default, common built-in models, and custom model entry.
- Fixed installer dry-run bug where `translate(lang, ..., lang=lang)` caused an argument collision.
- Rewrote `README_CN.md` as readable Chinese documentation and expanded English/Chinese docs with development reason, design goals, install method, embedding guidance, KMM positioning, changelog, and acknowledgements.
- Added `docs/release-v3.5.1.md` for GitHub release content.
- Added webhook forwarding adapters for generic webhooks, Slack, Feishu/Lark, DingTalk, and Telegram.
- Configured production private `MEMORY_ALERT_FORWARD_URL` for Telegram using private runtime credentials; no third-party token or URL was written to the public repository.
- Added webhook inbound queue rotation via `MEMORY_ALERT_QUEUE_MAX_LINES`.
- Added `metrics_dashboard_server.py` and enabled `hermes-metrics-dashboard.service`, bound to `127.0.0.1:9500` with token-gated access.
- Added `profile_isolation_soak.py` and ran a real two-profile soak test against the server repo.
- Migrated LangSmith wrapper execution away from gray paths by copying the LangSmith venv to the main runtime path and updating wrappers to use the main repo scripts.
- Deleted obsolete gray/runtime archives: `$AGENT_HOME/gray` and `$REPO_ROOT-gray` after confirming no process or cron dependency remained.

Verification performed:

- Local tests: `144 passed, 2 skipped`.
- Local public repo audit: no private path refs, no secret-like refs, no compile failures.
- Server public repo audit: no private path refs, no secret-like refs, no compile failures.
- Installer dry-run on server: `v3.5.1`, install mode `3`, embedding selection preserved, language output works.
- Telegram forwarding smoke test: local receiver accepted action-needed payload, queue advanced, Telegram API returned `200 OK`.
- Dashboard auth smoke test: unauthenticated request returned `401`; authenticated bearer request returned `200` and dashboard HTML.
- Profile isolation soak: 3 iterations, 2 profiles, 0 failures.
- LangSmith wrapper smoke test: venv import succeeded and trend wrapper exited `0`.
- Acceptance checks after changes: fast `ok=true`; full `ok=true`, reason buckets `{}`.
- gbrain stale maintenance remains healthy operationally; panel score still shows 8/10 because gbrain reports 47 non-actionable stale counters and 1 orphan counter discrepancy with actual orphan count 0.

Cleanup decision:

- Removed the actual gray runtime and gray repo archive because production no longer referenced them.
- Kept unrelated non-project backup/checkpoint folders because they are not clearly the memory-sidecar gray/old project and deleting them would exceed the current task scope.

Current status:

- Production memory sidecar is online and stable.
- Public repo is clean for external release.
- `v3.5.1` is ready for commit, tag, and GitHub Release publication.

Next recommended enhancements:

1. Add webhook retry/backoff with dead-letter queue for failed external sends.
2. Add a small local CLI command to print dashboard URL and token-file location without exposing the token.
3. Add optional dashboard reverse-proxy examples for Caddy/Nginx with IP allowlist and HTTPS.
4. Coordinate with gbrain upstream to expose stale page contributors or correct health score accounting so the panel can reach 10/10 without sidecar-side guesswork.
5. Add a release checklist workflow that runs audit-repo, tests, dry-run install, profile soak, and doc version checks before tag creation.

## 23. Execution Report - Retry, Dashboard Publication Templates, Release Gate

Date: 2026-06-26

Scope implemented:

- Added webhook external-forward retry/backoff controls: `MEMORY_ALERT_FORWARD_RETRY_ATTEMPTS` and `MEMORY_ALERT_FORWARD_RETRY_BACKOFF_S`.
- Added failed external-send dead-letter queue at `$AGENT_HOME/metrics/failed-alert-webhook.jsonl`.
- Kept normal inbound queue rotation and added dead-letter rotation through the same max-line policy.
- Added `hermes-memory dashboard-info`, which prints dashboard URL and token-file metadata without printing the token value.
- Added dashboard reverse proxy templates in `docs/dashboard-reverse-proxy.md` for Caddy and Nginx with HTTPS, localhost upstream, bearer-token use, and IP allowlist guidance.
- Added `docs/release-checklist.md` for manual release gates.
- Added `.github/workflows/release-check.yml` to run tests, public repo audit, installer dry-run, and profile isolation soak on push/tag/PR.
- Expanded `docs/gbrain-stale-upstream-request.md` with a proposed JSON shape for stale/health contributors.

Verification performed:

- Local tests: `148 passed, 2 skipped`.
- Local public repo audit: no private path refs, no secret-like refs, no compile failures.
- Server compile and public repo audit passed.
- Dead-letter smoke test: temporary failed forward wrote a dead-letter row, status became `degraded`, retry attempts recorded as `2`.
- Normal Telegram forward smoke test: local queue advanced, Telegram API returned `200 OK`, retry attempts recorded as `1`.
- `dashboard-info` smoke test: token configured, token value was not printed.
- Profile isolation soak from release gate: `ok=true`, failures `0`.
- Production acceptance checks: fast `ok=true`, full `ok=true`, reason buckets `{}`.

Current status:

- Operational behavior is stable.
- Repository drift remains expected until this batch is committed; after commit, drift should return to `healthy`.

Next recommended enhancements:

1. Add authenticated read-only API endpoints for dashboard JSON so external monitors can poll machine-readable status without scraping HTML.
2. Add Prometheus/OpenMetrics export for health status, queue length, last forward status, acceptance latency, and gbrain upstream-gap status.
3. Add signed release artifacts or checksums for installer files.
4. Add an optional webhook replay command for dead-letter rows after external service recovery.
5. Add a gbrain upstream issue/PR once the target repository contribution path is confirmed.

## 24. Execution Report - Release Check CI Stabilization

Date: 2026-06-26

Issue found:

- The new GitHub Actions `release-check` workflow initially failed on Linux even though local Windows tests passed.
- Root cause: several Linux-sensitive compatibility fixes existed in the working tree/runtime but had not been included in the previous release-check commit.

Fix applied:

- Added the current implementations of `session_to_gbrain.py`, `state_db_schema.py`, `knowledge_notes.py`, and `memory_maintenance_cycle.py` to version control.
- These include YAML-safe gbrain frontmatter title rendering, stricter unrecoverable JSON handling, content-hash knowledge note signatures, optional-column schema fallbacks, and maintenance helper functions used by tests.

Verification performed:

- Local tests: `148 passed, 2 skipped`.
- Server compile and public repo audit passed.
- GitHub Actions `release-check` passed on commit `f51dd9d`.
- Production drift after commit: `healthy`.
- Production alert queue after commit: `healthy`.
- Production fast acceptance: `ok=true`.

Next recommended enhancements:

1. Add a dedicated release status badge to README after observing the workflow for several pushes.
2. Add an OpenMetrics exporter so dashboard data can be scraped without HTML parsing.
3. Add dead-letter replay tooling for recovered webhook destinations.
4. Add a small synthetic recall benchmark dataset to catch cross-platform retrieval regressions earlier.

## 28. Runtime Recovery - 2026-07-10

- Scope: stabilize production memory-sidecar runtime without changing user-facing memory features.
- Root cause 1: `memory_governance_rebuild.py` still defaulted to `$HOME/.agent`, so direct production runs could miss `$AGENT_HOME/state.db` and leave `governance_meta.hindsight_synced_at` stale.
- Root cause 2: `session_to_gbrain.py` required `GBRAIN_MCP_TOKEN`, but production wrappers did not export it; MCP archive calls returned HTTP 401 before any real work happened.
- Root cause 3: `session_to_gbrain.py` was willing to archive large `request_dump_*.json` raw transport dumps. Those files are noisy, low-value, and can stall `gbrain put`.
- Root cause 4: LangSmith monitor/trend semantics conflated wrapper execution success with business health, so runs looked green even when acceptance or storage checks were failing.
- Root cause 5: alert messages implied automatic recovery was guaranteed, which was not true for the current runtime.

Implemented fixes:

- `scripts/memory_governance_rebuild.py`
  - default runtime fallback changed from `$HOME/.agent` to `$HOME/.hermes`.
- `scripts/session_to_gbrain.py`
  - default runtime fallback changed from `$HOME/.agent` to `$HOME/.hermes`;
  - auto-discovers gbrain MCP bearer token from `$AGENT_HOME/config.yaml` when `GBRAIN_MCP_TOKEN` is absent;
  - skips `request_dump_*.json` by default unless `SESSION_TO_GBRAIN_INCLUDE_REQUEST_DUMPS=true`;
  - extended MCP/CLI timeout defaults to 180s.
- `scripts/memory_guardian.py`
  - slight Hindsight node-budget overflow now downgrades to `action` instead of `critical` when the overage stays within a configurable grace window and consolidation is otherwise clean.
- `scripts/gbrain_stale_maintenance.py`
  - uses the `gbrain-embed` wrapper for embedding refresh;
  - runs the deorphan wrapper when orphan pages exist;
  - reports `auto_fix_attempted`, `auto_fix_succeeded`, and `auto_fix_failed`.
- `scripts/langsmith_monitor.py`
  - child commands now inherit `AGENT_HOME`;
  - sanitized outputs now distinguish `execution_ok` and `business_ok`.
- `scripts/langsmith_task_wrapper.py`
  - extracts business status from JSON stdout and publishes `business_ok`, `business_status`, and `business_reason_buckets`.
- `scripts/langsmith_trend_report.py`
  - monitor metrics now separate `execution_ok_rate` from `acceptance_ok_rate`;
  - task metrics now separate technical success from business success.
- `scripts/alert_queue.py` and `scripts/alert_webhook_receiver.py`
  - alerts now carry stricter reason/recommended_action text;
  - notifications are transition-based, with resolved alerts emitted once and duplicate spam suppressed.

Observed production outcome after deployment:

- `hindsight_sync_lag_seconds` dropped from about 21597s to well under 1000s after governance rebuild succeeded against the real `AGENT_HOME`.
- guardian status dropped from `critical` to `action`.
- `session_to_gbrain.py --resume` no longer fails on MCP 401.
- recent LangSmith monitor window recovered to `recent_acceptance_ok_rate = 1.0`.
- `hindsight_lag` and `recent_acceptance_failures` disappeared from the active alert set.
- gbrain embedding recovery reduced missing embeddings from 147 to low single digits; remaining actionable issue is stale/orphan cleanup.

Residual work:

- gbrain stale/orphan remediation is still incomplete.
- latest production health picture is no longer a hot-layer/Hindsight emergency; it is now primarily a cold-layer cleanup problem.

## 29. Cold-Layer Closure - 2026-07-10

- Follow-up stabilization finished the remaining cold-layer remediation loop.
- `session_to_gbrain.py` now ignores `request_dump_*.json` by default, which removed low-value raw transport dumps from the archive path.
- `gbrain_deorphan_index.py` now returns an explicit orphan-link plan and can create direct links from generated orphan hubs instead of relying only on link extraction side effects.
- `gbrain_stale_maintenance.py` now ignores generated orphan-index maintenance pages when computing actionable orphan count.

Observed production outcome:

- actionable gbrain orphans dropped from `40` to `0`;
- missing embeddings dropped from `147` to `0`;
- `gbrain-stale-latest.json` now classifies the remaining `stale_pages` and orphan-index root as info-level panel noise rather than actionable degradation;
- `hindsight_lag` and `recent_acceptance_failures` remained cleared from active alerts after the final refresh.

Net system state after this batch:

- hot-layer emergency resolved;
- Hindsight lag resolved to within threshold;
- cold-layer actionable debt resolved;
- remaining gbrain health deductions are upstream accounting / contributor-visibility gaps, not local runtime failure.
