# gbrain stale health counter upstream request

## Problem

The memory sidecar can automatically run `gbrain embed --stale` and validate real orphan count with `gbrain orphans --count`, but the `gbrain health` panel can still report stale pages or orphan pages after the actionable maintenance work is clean.

This leaves automation unable to distinguish these cases from the health panel alone:

- Truly stale pages that need embedding refresh.
- Code or metadata pages that `embed --stale` does not consider embeddable stale work.
- Cached or derived health counters that no longer match the actionable orphan list.

## Requested gbrain capability

Expose one of the following stable interfaces:

- `gbrain stale --json`, returning stale page IDs, paths, type/category, and recommended fix.
- `gbrain health --json --explain`, returning each non-perfect health contributor with page IDs where applicable.
- A corrected `gbrain health` counter that only counts actionable stale or orphan work.

## Acceptance Criteria

- A sidecar script can classify every non-10/10 health deduction without parsing human text.
- `gbrain embed --stale` returning zero work must not leave an unexplained stale-page deduction.
- `gbrain orphans --count` returning zero must not coexist with an unexplained orphan-page deduction, or the health output must label it as a non-actionable cached counter.

## Proposed JSON Shape

```json
{
  "health_score": 10,
  "contributors": [
    {
      "code": "stale_pages",
      "severity": "info",
      "count": 0,
      "actionable": false,
      "pages": []
    }
  ]
}
```

For non-zero contributors, `pages` should include stable page IDs, paths or slugs, page type, and recommended repair command.

## Current Sidecar Mitigation

`gbrain_stale_maintenance.py` treats non-actionable stale and orphan counter discrepancies as `info` when:

- `gbrain embed --stale` finds zero chunks.
- `gbrain orphans --count` returns zero actual orphan pages.

This keeps operational alerts accurate, but the gbrain panel itself may still display less than `10/10` until gbrain exposes page-level stale evidence or fixes the counter.
