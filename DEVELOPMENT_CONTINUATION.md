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
export AGENT_HOME=/root/.hermes
export MEMORY_STATE_DB_PATH=/root/.hermes/state.db
export MEMORY_GOVERNANCE_DB_PATH=/root/.hermes/memory_governance.db
export MEMORY_KNOWLEDGE_NOTES_DIR=/root/.hermes/knowledge/notes
exec /root/.hermes/scripts/hermes-memory $@
```

Impact:

- it defeats caller-supplied `AGENT_HOME`
- it weakens the multi-agent portability story
- it makes the public contract less truthful than the runtime behavior

2. The server repository is still behind the actual running production scripts.

Current `/root/hermes-memory-installer` status shows:

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
  - `/root/.hermes/metrics/langsmith-monitor-latest.json`
  - `/root/.hermes/metrics/langsmith-trend-latest.json`

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
  `/root/.hermes/metrics/`
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

2. Commit the 657/214 server-repo diff
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

- stop adding new “round” sections unless one of the verified facts above
  changes
- do not continue expanding feature-roadmap prose while P0/P1 remain open
- treat the next meaningful update to this file as an execution-status update

### 11.3 Confirmed next-step order

The next-step order remains:

1. P0
   - fix wrapper env handling
   - fix wrapper `"$@"`
   - confirm credential rotation

2. P1
   - preserve production-only CLI logic in version control
   - commit the 657/214 diff
   - push reconciled runtime baseline
   - break down `acceptance_ok_rate = 0.846` by failure family

3. P2
   - determine whether `latest_hindsight_lag_s = 6484` is persistent or spiky
   - determine why 47 stale pages remain
   - make cross-check fallback explicit

4. Only then expand
   - deploy manifest
   - runtime-to-repo drift alerting
   - acceptance failure summarization
   - lag thresholding
   - stale-page refresh/classification helper

### 11.4 Recommended communication framing

When discussing next work with the team, use this framing:

- do not describe the project as needing more diagnosis
- describe it as needing release reconciliation and signal interpretation
- feature expansion is allowed only after the current runtime is brought back
  under version control discipline

---

## 12. Consensus Reached — Implementation Can Begin (2026-06-26)

§11 is correct: analysis is complete. The team agrees on every substantive
point. No further round-by-round assessments. This section marks closure.

### 12.1 Agreed execution order

| Step | Action | Time |
|------|--------|------|
| P0-1 | Fix `"$@"` quoting in `/usr/local/bin/hermes-memory` | 1 min |
| P0-2 | Fix wrapper: use `AGENT_HOME:-/root/.hermes` instead of hard override | 5 min |
| P0-3 | Rotate credentials (GitHub PAT, LangSmith key, SSH) | 30 min |
| P1-1 | `cp` production `hermes-memory` to repo + `git commit` 657-line diff | 10 min |
| P1-2 | `git push` to GitHub | 2 min |
| P1-3 | Investigate `acceptance_ok_rate=0.846` root cause in `archive_sessions` | 1h |
| P2-1 | `gbrain reindex` stale pages → `health_score` 8→10 | 5 min |
| P2-2 | Trend hindsight lag across 3+ consecutive snapshots | 1h |
| P2-3 | Add fallback WARNING to `memory_storage_cross_check.py` | 5 min |

### 12.2 Agreed feature roadmap (post-P0/P1)

1. `hermes-memory manifest` — JSON deploy manifest with script hashes + timer state
2. Drift alert cron — nightly hash compare production vs repo, warn on mismatch
3. Acceptance failure report — failure-family breakdown for `0.846` rate
4. Lag threshold alert — warn if `latest_hindsight_lag_s > 3600` × 3 consecutive
5. Stale-page refresh helper — `hermes-memory reindex-stale`

### 12.3 Agreed: what NOT to build

- New recall layers
- Hermes-only script genericization
- `audit-repo` (doesn't exist, not needed before P1)

### 12.4 Decision

Consensus reached. Implementation can begin with P0-1.
