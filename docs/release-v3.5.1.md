# Memory Sidecar v3.5.1

Memory Sidecar v3.5.1 is the operational hardening release for the public agent-agnostic memory sidecar.

Release page: https://github.com/mage0535/hermes-memory-installer/releases/tag/v3.5.1

## Why This Release Exists

The v3.5 public package made the project installable outside a single private Hermes deployment. Production usage then showed the next set of practical gaps: health signals needed a real notification path, dashboard access needed an auth boundary, multi-agent profile isolation needed a repeatable soak check, and the public docs needed clearer guidance for embedding model selection.

## Design Direction

The release keeps the same sidecar boundary: the agent owns its home directory and runtime, while Memory Sidecar reads durable data, rebuilds recall indexes, and emits health artifacts. v3.5.1 adds operational controls around that boundary rather than adding host-specific assumptions.

## Highlights

- Version metadata is unified as `3.5.1` across installer, CLI, docs, and release notes.
- The installer keeps embedding model selection with a recommended default, common presets, and custom model entry.
- Install modes remain available: `--install-mode 3` for automatic bootstrap first, `--install-mode 2` for guided assistance, and `--install-mode 1` for detection-only guidance.
- `alert_webhook_receiver.py` accepts local action-needed alerts and can forward to generic webhooks, Slack, Feishu/Lark, DingTalk, or Telegram.
- Webhook inbound queues can rotate by line count to avoid unbounded growth.
- `metrics_dashboard_server.py` serves the dashboard behind a token gate and binds to localhost by default.
- `profile_isolation_soak.py` performs a two-profile isolation soak without touching production state.
- gbrain stale panel limitations are documented in `docs/gbrain-stale-upstream-request.md`.

## Embedding Model Guidance

Recommended default:

- `intfloat/multilingual-e5-small` for balanced multilingual recall.

Common alternatives:

- `BAAI/bge-small-zh-v1.5` for lightweight Chinese-first deployments.
- `paraphrase-multilingual-MiniLM-L12-v2` for mature sentence-transformers compatibility.
- `Alibaba-NLP/gte-multilingual-base` for higher quality with more memory headroom.
- `sentence-transformers/LaBSE` for cross-language alignment.
- `BAAI/bge-m3` for maximum recall quality when RAM and disk are sufficient.

## Knowledge-and-Memory-Management

For a broader knowledge collection and curation workflow, pair this sidecar with [Knowledge-and-Memory-Management](https://github.com/mage0535/Knowledge-and-Memory-Management). KMM handles upstream knowledge capture and organization; Memory Sidecar turns curated material into recallable agent context.

## Acknowledgements

Thanks to the operators and community users who provided feedback on install friction, recall quality, profile isolation, alerting, and public documentation gaps.
