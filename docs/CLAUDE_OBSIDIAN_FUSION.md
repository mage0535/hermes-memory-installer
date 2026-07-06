# claude-obsidian → KMM (hermes-memory-installer) 融合设计

## 现有 KMM 架构 (v3.5.2)
```
4层记忆: Hot(工具) → Warm(Hindsight PG) → Cold(gbrain+session_search) → Knowledge(curated notes)
检索: intent分类 → 4层拉取 → RRF融合 → rerank → 注入context
```

## claude-obsidian 可借鉴的 6 个模式

### 1. Hot Cache (wiki/hot.md) — 新增到 gbrain 热层
**当前**: Hermes 无会话间热缓存。每次会话从头重建上下文。
**改造**: 在 gbrain 中创建 `hot/` 页面，每次会话结束时写入 ~500 字摘要。
```
每次会话结束 → 写入 gbrain hot page → 下个会话开始时自动读取
```
**位置**: `hermes-memory-installer/memory_ops/retrieve.py` 新增 hot_cache 步骤

### 2. .vault-meta 元数据索引
**当前**: gbrain 页面没有结构化的元数据层。
**改造**: 每次 gbrain 写入时自动生成 `.vault-meta/` 风格的索引，包含：
- 页面类型 (entity/concept/domain/comparison/question)
- 标签索引
- 交叉引用计数
- 孤儿页面标记
- 冲突标记

### 3. 混合检索 (BM25 + embedding + rerank)
**当前**: gbrain 仅使用 embedding cosine similarity。
**改造**: 增加 BM25 (关键词匹配) 作为 fallback。两层 RRF 融合后送入 reranker。
```
检索: embedding(top-k) + BM25(top-k) → RRF融合 → cosine rerank → 结果
```
**参考**: Anthropic Sep 2024 论文 + claude-obsidian hybrid retrieval

### 4. 方法论抽象层 (LYT/PARA/Zettelkasten/Generic)
**当前**: KMM 硬编码了文件夹结构分类。
**改造**: 抽象出 methodology 层：
```
METHODOLOGY=generic (默认)
METHODOLOGY=para    → Projects/Areas/Resources/Archives
METHODOLOGY=lyt     → MOC + atomic notes
METHODOLOGY=zettel  → timestamp IDs + flat structure
```
写入 `.vault-meta/mode.json`，消费方 (ingest/save/query) 读取后决定路由。

### 5. 多 Writer 安全锁
**当前**: gbrain 没有并发写入保护。MCP 和 HTTP 两个实例写入可能冲突。
**改造**: 引入 per-page advisory lock (文件名级锁，超时 60s)。
**位置**: `gbrain_bridge.py` 写入前加锁，后释放。

### 6. 跨项目引用协议
**当前**: 每个项目独立知识库，项目间无引用。
**改造**: 实现跨项目 wiki 引用协议：
```
## Wiki Knowledge Base
Path: /root/knowledge/
→ 其他项目 CLAUDE.md 直接引用
```

## 融合优先级

| # | 模式 | 难度 | 优先级 | 说明 |
|---|------|:----:|:------:|------|
| 1 | Hot Cache | 低 | P0 | 会话间缓存，收益直接 |
| 2 | 混合检索 | 中 | P0 | BM25 + embedding，检索质量提升大 |
| 3 | .vault-meta 索引 | 中 | P1 | 知识结构化和可维护性 |
| 4 | 方法论层 | 高 | P2 | 架构改动大，但价值高 |
| 5 | 多 Writer 锁 | 低 | P1 | 当前已有双实例问题 |
| 6 | 跨项目引用 | 低 | P2 | 知识生态扩展 |
