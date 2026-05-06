# Context Routing Reference

## Scoring Algorithm
```
final_score = similarity * exp(-age_days / 30.0)
```

## Thresholds
| Layer | min_similarity | limit | Notes |
|-------|---------------|-------|-------|
| L1 (agent-local) | 0.55 | 2 | Lower for Chinese names |
| L2 (cross-platform) | 0.65 | 5 | Higher confidence needed |
| L3 (gbrain) | 0.55 | 5 | Full knowledge graph |

## Injection Format
- Local: `[Related memory (role, ~85%): content]`
- Cross-platform: `[Cross-platform memory (telegram:user, ~72%): content]`

## Agent ID Format
`source:user_id` (e.g., `telegram:5975133381`, `cli`, `cron`)
