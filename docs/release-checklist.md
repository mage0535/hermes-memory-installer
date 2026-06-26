# Release Checklist

Run this before creating a public release tag.

```bash
python -m pytest -q
python bin/hermes-memory audit-repo --format text
python installer/install.py --dry-run --skip-checks --noninteractive --agent-home /tmp/hermes-release-check --lang en
python scripts/profile_isolation_soak.py --repo-root . --iterations 2 --interval-s 0
```

Acceptance criteria:

- Tests pass.
- `audit-repo` reports no private path refs, no secret-like refs, and no compile failures.
- Installer dry-run prints the intended version and script set.
- Profile isolation soak reports `ok=true`.
- Release notes and README files mention the same version.
