# Release Checklist

Run this before creating a public release tag.

```bash
python -m pytest -q
python bin/hermes-memory audit-repo --format text
python installer/install.py --dry-run --skip-checks --noninteractive --agent-home /tmp/hermes-release-check --lang en
python scripts/profile_isolation_soak.py --repo-root . --iterations 2 --interval-s 0
python scripts/synthetic_recall_benchmark.py
python scripts/release_checksums.py --output dist/SHA256SUMS
python scripts/release_checksums.py --verify dist/SHA256SUMS
```

Source-script releases are verified with SHA-256 checksums. Add artifact signing only when publishing compressed archives or standalone binaries.

Acceptance criteria:

- Tests pass.
- `audit-repo` reports no private path refs, no secret-like refs, and no compile failures.
- Installer dry-run prints the intended version and script set.
- Profile isolation soak reports `ok=true`.
- Synthetic recall reports `ok=true` against the public non-private fixture.
- Release checksum generation and verification both pass.
- Release notes and README files mention the same version.
