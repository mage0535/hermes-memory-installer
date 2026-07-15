# Resource Governance

This note documents the conservative production policy for running Hermes memory services on fixed-size hosts.

## Goals

- Keep user-facing gateway traffic responsive during memory or CPU pressure.
- Prevent background embedding and browser automation from starving Hindsight and the gateway.
- Avoid aggressive memory ceilings that cause restart loops.
- Keep Prometheus memory alerts scoped to memory services, not unrelated host workloads.

## Runtime Policy

Recommended systemd resource boundaries:

```text
hindsight.service:      CPUQuota=100%, CPUWeight=100, keep MemoryHigh=1.5G and MemoryMax=2G
hermes-gateway.service: CPUQuota=150%, CPUWeight=250
gbrain-embed.service:   CPUQuota=50%, CPUWeight=30, IOWeight=30, MemoryHigh=1200M, MemoryMax=1600M
gbrain-worker.service:  CPUQuota=50%, CPUWeight=40, IOWeight=60
```

Do not set `hindsight.service` to `MemoryMax=800M`. Production RSS can exceed that during normal warmup or index rebuilds, and a low ceiling can create a restart loop.

## Scheduled Work

`gbrain_stale_maintenance.py --refresh-embeddings` is intentionally scheduled every 6 hours with `flock` and a stale-page budget. Hourly or unbounded embedding refreshes are too expensive once missing embeddings are healthy.

```cron
12 */6 * * * AGENT_HOME=/path/to/agent/home flock -n /tmp/gbrain-stale-refresh.lock /usr/bin/python3 /path/to/agent/home/scripts/gbrain_stale_maintenance.py --refresh-embeddings --stale-budget 100 --missing-budget 0 --output /path/to/agent/home/metrics/gbrain-stale-latest.json >> /var/log/gbrain-stale.log 2>&1 # gbrain-stale-refresh
```

Foreground recall should stay read-only. `memory_governance.db` freshness is handled by a separate `flock`-guarded cron so user queries do not pay the rebuild cost.

```cron
*/15 * * * * AGENT_HOME=/path/to/agent/home flock -n /tmp/memory-governance-rebuild.lock /usr/bin/python3 /path/to/agent/home/scripts/memory_governance_rebuild.py --quiet >> /var/log/memory-governance-rebuild.log 2>&1 # memory-governance-rebuild
```

## Load Shedding

`hermes_load_shedder.py` runs every 5 minutes on production. It only terminates stale temporary browser driver trees under real pressure. Persistent browser profiles are deprioritized with `renice`/`ionice`, not killed.

Under critical pressure (`load1 >= 32` or `swap >= 95%` by default), persistent browser publishing trees older than the configured age gate are also terminated. Production uses `HERMES_LOAD_SHEDDER_PERSISTENT_MIN_AGE_S=180` so browser publishing yields quickly when the memory host is already critical. Publishing parent runners such as scheduled browser upload jobs are also terminated under critical pressure so they cannot immediately respawn a new browser tree. This is intentional: browser publishing is non-core and must not starve `hindsight.service` or `hermes-gateway.service`.

Do not re-enable the legacy `swap-pressure-responder.sh` pattern that restarts `hindsight` or `hermes-gateway` based only on swap usage. Swap is a lagging signal; using it as a direct restart trigger caused repeated Hindsight re-indexing and gateway restart storms on 2026-07-15.

## Prometheus Alert Scope

`prometheus_alert_bridge.py` forwards memory-related alerts by default. Alerts from unrelated services, such as content delivery platforms, are filtered out of the memory webhook pipeline. Use `--include-all` only for debugging shared Prometheus state.
