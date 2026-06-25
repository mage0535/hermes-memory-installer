# Hermes Agent — Pre-Audit Capability Report

> Historical audit snapshot: this report captures a pre-sidecar-cleanup Hermes deployment and is background material, not the current portable multi-agent contract. Use `README.md`, `ARCHITECTURE.md`, and `docs/compatibility-matrix.md` for the maintained local/public build.

**Generated**: 2026-05-29
**Host**: Linux 6.8.0-48-generic
**Hermes Home**: $AGENT_HOME
**Profile**: default

## 1. System Overview

- **RAM**: MemTotal:        8131944 kB
- **Disk (/)**: /dev/vda1        88G   79G  8.3G  91% /
- **CPU Cores**: 4
- **Python**: Python 3.12.3
- **GPU**: No GPU detected (CPU-only inference for embeddings)

## 2. Available Tools Summary

| Category | Tool | Description |
|----------|------|-------------|
| Terminal | terminal() | Shell command execution on Linux |
| Browser | browser_* + Chrome DevTools MCP | Page navigation, clicks, screenshots, JS eval, Lighthouse audits |
| Web Search | web_search() | Web search with operator support |
| File System | read/write/patch/search_files (via terminal) | Full file read/write/search capabilities |
| Memory (Hot) | memory() tool | 5KB system prompt injection, cross-session persistence |
| Memory (Warm) | hindsight_retain/recall/reflect | PostgreSQL-backed auto-retain/recall/reflect |
| Memory (Bridge) | agentmemory MCP (51 tools) | Hybrid BM25+vector+graph search, smart recall, audit trail |
| Knowledge Graph | gbrain MCP (40+ tools) | Vector+keyword+graph query, page CRUD, wikilinks, timelines, Minion workers |
| Code Analysis | codegraph MCP (9 tools) | Symbol search, context, callers/callees, impact analysis |
| Task Mgmt | todo() | In-session task tracking with priorities |
| Scheduling | cronjob() | Flexible cron with no_agent/LLM modes, workdir/profile isolation |
| Image Gen | image_generate() | Text-to-image via configured backend (FAL/OpenAI) |
| Vision/OCR | vision_analyze() | Image analysis with vision model fallback |
| Scraping | scrapling MCP (14 tools) | Anti-detection scraping with 3 fetcher modes + CF bypass |
| TTS | text_to_speech() | Voice synthesis (Edge-TTS, multi-voice) |
| Video | video_gen tools | HyperFrames HTML→MP4 rendering pipeline |
| Documents | markitdown | PDF/DOCX/PPTX/XLSX → Markdown conversion |
| Email | himalaya CLI | IMAP/SMTP email management |
| MCP | native-mcp + mcporter | Extensible MCP server framework |
| Git | git via terminal | Full git workflow: clone, commit, push, PRs |
| Social | send_message() | Multi-platform delivery (Telegram, Discord, etc.) |
| Subagents | delegate_task() | Parallel subagent spawning (up to 3 concurrent) |
| Skills | skill_manage/create/patch/view | Reusable procedural knowledge system |
| Finance | mcp_tushare_* (200+ APIs) | A-share, HK, US stocks, futures, macro data |
| News | mcp_horizon_* | Automated news aggregation pipeline |

## 3. Skill Inventory

- **Installed skill directories**: ~30
- **Available via skills_list**: ~900+ including archived categories

### Key Skill Categories

- **financial**: A-stock analysis, macro economics, hedge fund, risk control, swing trading
- **devops**: Server mgmt, proxy/v2raya, cron, tool installation, CI/CD, container debug
- **security**: Penetration testing, forensics, malware analysis, incident response (200+)
- **academic/research**: Paper writing, literature review, causal inference, econometrics
- **engineering**: Code review, architecture design, data engineering, SRE, backend, frontend
- **creative**: UI design, ASCII art, diagrams, image/video gen, design systems
- **social-media**: TikTok/Douyin automation, YouTube, X/Twitter, content matrix
- **video**: Video rendering, FFmpeg pipelines, TVC ads, faceless automation
- **data-science**: Statistical analysis, ML pipelines, Jupyter, Polars, Bayesian methods

## 4. Active Cron Jobs

| # | Name | Schedule | Type | Function |
|---|------|----------|------|----------|
| 1 | 系统管家 | :00,:30 hourly | no_agent | System health, GitHub trending collection |
| 2 | 系统维护 | 02:30 daily | LLM+curator | Skill audit, GitHub trend analysis, self-evolution |
| 3 | 晨报 | 05:30 weekdays | LLM+script | Morning briefing: A-stock, global macro, news |
| 4 | 市场数据 | */5 9-16 Mon-Fri | no_agent | Close prices, intraday picks, overnight arb |
| 5 | 渠道内容 | 13x/day | no_agent | Channel discovery, content publishing, audit |

## 5. MCP Server Inventory

- **Chrome DevTools**: Full browser automation - navigation, click, type, screenshot, console, network, Lighthouse, performance tracing, heap snapshots
- **Scrapling**: Anti-detection web scraping - 3 fetch modes (get/fetch/stealthy), Cloudflare bypass, session management, screenshot
- **CodeGraph**: Code intelligence - symbol search, context queries, callers/callees, impact analysis, file listing
- **gbrain**: Knowledge graph - page CRUD, vector+keyword+graph search, wikilinks, timeline, tags, Minion workers
- **Horizon**: News aggregation - fetch/score/filter/enrich/summarize pipeline, webhook delivery
- **Tushare**: Chinese financial data - 200+ API endpoints covering A-shares, HK, US stocks, futures, options, ETFs, macro data, financial statements
- **Sequential Thinking**: Structured multi-step reasoning with revision/branching
- **agentmemory**: Memory server - save, recall, search, audit, export with hybrid retrieval

## 6. Memory System Architecture

| Tier | Name | Storage | Capacity | Latency | Retrieval Type |
|------|------|---------|----------|---------|----------------|
| L0 (Hot) | memory tool | System prompt | 5KB cap | 0ms | Direct injection |
| L1 (Warm) | Hindsight | PostgreSQL 16 | Unlimited | ~50ms retain | Semantic vector |
| L2 (Bridge) | agentmemory | Docker MCP | ~10K docs | ~100ms | BM25+vector+graph RRF |
| L3 (Cold) | gbrain | PG16+pgvector | 10005+ pages | ~500ms-2s | Vector+keyword+wikilinks |

## 7. LLM Provider Configuration

| Priority | Provider | Model | Type | Notes |
|----------|----------|-------|------|-------|
| 1 | opencode-zen-1 | deepseek-v4-flash-free | Free | Default, direct connect |
| 2 | opencode-zen-2 | deepseek-v4-flash-free | Free | Backup key, via relay proxy |
| 3 | opencode-go | deepseek-v4-flash | Paid | 5h/month quota, fallback |
| 4 | deepseek | deepseek-v4-flash | Official API | Last resort |
| Stock analysis | opencode-go | qwen3.6-plus | Paid | Morning briefing stock picks |
| Content gen | opencode-go | kimi-k2.6 | Paid | Auto-publish content generation |

## 8. External Integrations

- **PostgreSQL 16**: Hindsight memory + gbrain storage
- **Docker**: agentmemory MCP server container
- **Bun**: gbrain runtime + Minion workers
- **sentence-transformers**: Local embedding models
- **V2rayA + Xray**: Proxy routing
- **Telegram Bot API**: Message delivery
- **Crier**: Multi-platform content publishing
- **social-auto-upload**: Chinese social media publishing
- **FFmpeg**: Video processing pipeline
- **Playwright**: Browser automation foundational layer

## 9. Pre-Audit Observations

### Strengths
- **Multi-layer memory**: 4-tier redundancy ensures no single point of failure
- **Zero cloud dependency**: All components run locally on-prem
- **Production-proven**: 2+ months continuous operation
- **Extensible**: MCP framework allows adding new capabilities without core changes
- **Skill system**: ~900 skills covering broad domains
- **No GPU required**: All embedding inference runs on CPU

### Areas for Review
- **API key management**: Multiple provider keys stored in config files
- **Docker dependency**: agentmemory requires Docker runtime
- **PostgreSQL dependency**: Two critical components depend on PG16
- **No monitoring dashboard**: Cron status checked manually
- **No backup strategy**: PostgreSQL backup not automated
- **Token cost management**: Free tier fallback chain works but unpredictable

## 10. Project Version Summary

| Component | Version |
|-----------|---------|
| hermes-memory-installer | 3.0 |
| install.sh | 3.0 |
| install.py | 3.0 |
| ARCHITECTURE.md | 3.0 |
| ARCHITECTURE_CN.md | 3.0 |
| README.md | 3.0 |
| README_CN.md | 3.0 |
| Hermes Agent | Ongoing (no semantic version) |
