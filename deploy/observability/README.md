# Hermes Memory Observability Stack

This directory provides a minimal Prometheus + Grafana stack for Hermes Memory.

## What it includes

- `prometheus.yml`: scrapes the dashboard server OpenMetrics endpoint.
- `prometheus-rules.yml`: ships default alert rules for acceptance rate, recall latency, queue growth, and component failure.
- `docker-compose.yml`: starts Prometheus and Grafana with host networking.
- `grafana/provisioning/datasources/prometheus.yml`: preconfigures Prometheus as the default datasource.
- `grafana/provisioning/dashboards/dashboards.yml`: auto-loads dashboard JSON files from `docs/grafana/`.

## Before starting

1. Read the dashboard token:
   `cat $AGENT_HOME/private/dashboard-token`
2. Replace `replace-with-dashboard-token` in `prometheus.yml`.
3. Change `GF_SECURITY_ADMIN_PASSWORD` in `docker-compose.yml`.

## Start

```bash
cd deploy/observability
docker compose up -d
python3 provision_dashboards.py \
  --password-file "$AGENT_HOME/private/grafana-admin-password" \
  --dashboards-dir ../../docs/grafana
```

## Default endpoints

- Prometheus: `http://127.0.0.1:9090`
- Grafana: `http://127.0.0.1:3000`

## Data source path

Prometheus scrapes:

```text
http://127.0.0.1:9500/metrics?token=<dashboard-token>
```

## Dashboard files

Grafana auto-loads:

- `docs/grafana/hermes-memory-openmetrics-dashboard.json`
- `docs/grafana/hermes-memory-home.json`

The web dashboard at `/dashboard` remains the bilingual operator UI with drilldown and status summaries. Grafana is the long-range trend and alerting layer.

`provision_dashboards.py` imports the dashboards through the Grafana API and sets `hermes-memory-home` as the default Grafana home dashboard.
