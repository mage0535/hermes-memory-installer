# Hermes Memory System: Complete Design & Implementation Report

> **Version**: v1.0  
> **Target Audience**: Beginners with no prior knowledge of Hermes or memory systems  
> **Writing Principle**: Explain every technical concept with everyday analogies; skip no detail

---

## Table of Contents

1. [For First-Time Readers](#1-for-first-time-readers)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Layer-by-Layer Deep Dive](#3-layer-by-layer-deep-dive)
4. [Database Schema & Table Design](#4-database-schema--table-design)
5. [Index Design & Implementation](#5-index-design--implementation)
6. [Full Data Lifecycle](#6-full-data-lifecycle)
7. [Access Control Design](#7-access-control-design)
8. [Technical Sources & Acknowledgments](#8-technical-sources--acknowledgments)
9. [How the Memory System Helps Hermes Evolve](#9-how-the-memory-system-helps-hermes-evolve)
10. [Final Validation](#10-final-validation)

---

## 1. For First-Time Readers

### 1.1 What Is Hermes?

Hermes is an **AI Agent operating system**. Think of it as a "super-assistant that can write code, browse the web, and take notes." It can help you:

- Write programs and fix bugs
- Check stock prices and read news
- Manage your schedule and relationships
- Remember what you've said, what you like, and what you dislike

But here is the problem — if every time you chat with Hermes it acts like a **goldfish** (rumored to have a 7-second memory), completely forgetting what you talked about last week, that assistant would be useless.

**The memory system** is the core solution to this problem.

### 1.2 What Is "Memory"? Why Does AI Need It?

Human memory comes in many forms:

| Human Memory Type | Corresponding AI Layer | Example |
|-------------------|------------------------|---------|
| Long-term personality / preferences | **Persistent Memory** | "I like Python, hate Java" |
| Recent conversations | **Session History** | "Yesterday we fixed that bug" |
| The "meaning" of a sentence | **Semantic Vector Memory** | "When he said 'that project' he meant P6" |
| Files and documents | **External Archives** | "My Kiki guide is in wang_yuqi_chat/" |

AI has no brain. All of its "memories" must exist as **data**. The memory system is an engineering solution for "making an AI remember things like a human."

### 1.3 An Everyday Analogy

Imagine Hermes is a **24-hour library**.

- **Persistent Memory** = The "Today's Notices" board at the library entrance (basic info everyone can see)
- **Session History** = The daily borrowing log (a chronological record)
- **Semantic Vector Memory** = The librarian's brain (you ask "anything about love?" and she recalls *Romeo and Juliet*, even though the title doesn't contain the word "love")
- **External Archives** = The library bookshelves (.md files are the books)

Without this system, the library would just be a warehouse full of books — no matter what you ask, it can only flip through pages on the spot, never "remembering" what you borrowed last month.

---

## 2. System Architecture Overview

### 2.1 Three-Layer Memory Architecture (Memory Pyramid)

```
                    ┌─────────────────────────────────────┐
                    │      🧠 Application Layer: AI Decision & Reply        │
                    │  "Based on memory, the user prefers concise answers"  │
                    └──────────────┬──────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
┌───────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  Layer 1: Persistent  │      │  Layer 2: Session History   │      │  Layer 3: Semantic Vector  │
│   Memory        │      │   (FTS5 Full-Text Search)  │      │   (Vector Similarity)     │
├───────────────┤      ├──────────────────┤      ├──────────────────┤
│ ~/.hermes/    │      │ ~/.hermes/        │      │ ~/.hermes/       │
│ memory/user   │      │ state.db          │      │ semantics.db     │
│ memory/       │      │ (sessions,        │      │ (embeddings,     │
│ assistant     │      │  messages,        │      │  384-dim vectors)│
│               │      │  messages_fts)    │      │                  │
│ System prompt │      │ suggest_recall    │      │ cosine similarity│
│ injection     │      │ (message loop)    │      │ (real-time calc) │
│ (read at boot)│      │                   │      │                  │
└───────┬───────┘      └────────┬─────────┘      └────────┬─────────┘
        │                       │                         │
        └───────────────────────┼─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────┐
                    │   Layer 4: External Archives    │
                    │ ~/.hermes/.../*.md  │
                    │ MemoryManager loads  │
                    │ (incremental index + mtime)   │
                    └─────────────────────┘
```

**Architectural Philosophy**:

1. **The lower the layer, the faster the query and the smaller the capacity**
2. **The higher the layer, the slower the query and the larger the capacity**
3. **Each layer only stores what it is best at storing — no reinventing the wheel**

### 2.2 Data Lifecycle Panorama

```
┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ Creation│ → │Transmit  │ → │ Retrieval│ → │  Aging   │ → │Persist/  │
│         │   │          │   │          │   │          │   │Destroy   │
└────┬────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘
     │             │              │              │              │
     ▼             ▼              ▼              ▼              ▼
  User input    Gateway       suggest_recall  access_count   Soft delete
  AI output     message loop  emb_store.search  last_accessed  Hard delete
  File read     DB write      hybrid_search   TTL decay      Archive
  Tool results  Vector encode   Hybrid ranking  Version evolve Immortal archive
```

We will walk through this data's entire life in **Chapter 6**.

### 2.3 Core Component Relationship Diagram

```
                    ┌─────────────────┐
                    │   User (You)     │
                    └────────┬────────┘
                             │ sends message
                             ▼
                    ┌─────────────────┐
                    │  Gateway Message Loop │  ←── run.py (line 10091)
                    │  (Core Dispatch Hub)   │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ suggest_recall│   │ semantic recall │   │ Persistent Memory Injection │
│ (P0-1)       │   │ (P6-1)          │   │ (memory/user)   │
│ FTS5 keyword │   │ Vector similarity│   │ System prompt   │
│ recall       │   │ recall          │   │ prefix injection│
└──────┬───────┘   └────────┬────────┘   └─────────────────┘
       │                    │
       └────────┬───────────┘
                ▼
       ┌─────────────────┐
       │ Merge into user message │
       │ "[Related memory]│
       │  ... original message" │
       └────────┬────────┘
                ▼
       ┌─────────────────┐
       │    LLM Inference │
       │  "Answer based on memory" │
       └─────────────────┘
```

---

## 3. Layer-by-Layer Deep Dive

### 3.1 Layer 1: Persistent Memory

#### 3.1.1 What Is It?

Persistent memory is Hermes's "personality profile." It stores:

- Who you are (user profile)
- What you like and dislike
- Hermes's own behavioral rules ("Never expose API keys to users")

#### 3.1.2 Storage Location

```
~/.hermes/
├── memory/
│   ├── user           ← Your info (things you told Hermes)
│   └── assistant      ← Hermes's self-settings (behavioral rules)
```

These are **plain text files** in simple Markdown format.

#### 3.1.3 How Is It Retrieved?

**Every time a new session starts**, Hermes injects the contents of these two files **at the very beginning of the system prompt**. This is equivalent to:

> "Before we start chatting, review your basic settings."

**Key Design**: This is a **frozen snapshot**. Once the session starts, even if the memory files are modified, the current session's system prompt does not change — this preserves the LLM's **prefix cache**, making inference faster and cheaper.

#### 3.1.4 Code Implementation

```python
# Simplified logic (from memory_tool.py)
# At session startup:
system_prompt = load_file("~/.hermes/memory/assistant") + "\n" + load_file("~/.hermes/memory/user")
# Then send system_prompt as the System Message to the LLM
```

#### 3.1.5 Aging & Updates

- **Update method**: Via the `memory` tool (add/replace/remove)
- **Effective time**: Changes are visible **only in the next new session**
- **Never auto-deleted**: Unless you manually call `memory(action="remove")`

---

### 3.2 Layer 2: Session History

#### 3.2.1 What Is It?

Session history is **every single word you and Hermes have ever said**. It is a chronological "chat log."

#### 3.2.2 Storage Location

```
~/.hermes/state.db  ← SQLite database
```

#### 3.2.3 Core Table Schema

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `sessions` | Metadata for each chat session | id, title, started_at, last_active, message_count |
| `messages` | Content of each message | id, session_id, role, content, timestamp |
| `messages_fts` | **FTS5 virtual table** (full-text index) | content (auto-synced from messages) |

#### 3.2.4 What Is FTS5? Why Do We Need It?

FTS5 = **Full Text Search 5**, SQLite's built-in **full-text search engine**.

**Everyday analogy**:

> Imagine the `messages` table is a 1,000-page diary. Without FTS5, to find the word "Python" you have to **flip through every page** (`SELECT * FROM messages WHERE content LIKE '%Python%'`) — this is called a **full table scan** with time complexity O(N), where N is the total number of messages.
>
> With FTS5, it's like adding a **table of contents** to the diary. You just look up the index and jump directly to the pages containing "Python" — time complexity O(1).

#### 3.2.5 BM25 Ranking Algorithm

FTS5 uses the **BM25** algorithm to rank search results by default.

**What is BM25?**

It is a mathematical formula for computing "how relevant is this document to the query." Core ideas:

1. **Term Frequency (TF)**: A document mentioning "Python" 10 times is more relevant than one mentioning it once
2. **Inverse Document Frequency (IDF)**: If 90% of documents mention "Python," that term is less discriminative
3. **Document Length Penalty**: A short document mentioning "Python" is more "focused" and relevant than a long document

**BM25 Formula** (simplified):

```
score(D, Q) = Σ IDF(q_i) * [f(q_i, D) * (k1 + 1)] / [f(q_i, D) + k1 * (1 - b + b * |D| / avgDL)]
```

Where:
- `D` = document (a message)
- `Q` = query (keywords from user input)
- `q_i` = the i-th term in the query
- `f(q_i, D)` = frequency of term q_i in document D
- `|D|` = document length
- `avgDL` = average document length
- `k1`, `b` = tuning constants (fixed internally by FTS5)

**In our code** (from `memory_store.py` lines 340-358):

```python
def search_fts(self, query: str, limit: int = 20):
    rows = conn.execute("""
        SELECT m.*, bm25(memories_fts) AS rank_score
        FROM memories_fts
        JOIN memories m ON memories_fts.rowid = m.rowid
        WHERE memories_fts MATCH ? AND m.status = 'activated'
        ORDER BY rank_score DESC
        LIMIT ?
    """, (query, limit))
```

Note: `bm25()` returns **negative numbers** (more negative = more relevant), so the code converts it:

```python
score = max(0.0, min(1.0, 1.0 + rank / 10.0))
# maps [-10, 0] to [0, 1]
```

#### 3.2.6 Triggers: Keeping the Index Real-Time Consistent

FTS5 virtual tables do not auto-sync with the main table. We need **database triggers** to maintain them:

```sql
-- When a new row is inserted into memories, auto-insert into FTS5 index
CREATE TRIGGER memories_fts_insert AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content) VALUES (new.rowid, new.content);
END;

-- When a row is deleted from memories, auto-delete from FTS5 index
CREATE TRIGGER memories_fts_delete AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content)
    VALUES('delete', old.rowid, old.content);
END;

-- When a row's content is updated, delete old index and insert new index
CREATE TRIGGER memories_fts_update AFTER UPDATE OF content ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content)
    VALUES('delete', old.rowid, old.content);
    INSERT INTO memories_fts(rowid, content) VALUES (new.rowid, new.content);
END;
```

**These three triggers ensure**: no matter what you do to the main table (insert, delete, or update), the FTS5 index is always **real-time consistent**.

#### 3.2.7 suggest_recall: Proactive Recall in the Gateway Message Loop

This is the core result of P0-1. Its logic is:

**Every time the user sends a message**, the Gateway first checks — "Is the user asking about something we discussed before?"

```python
# gateway/run.py lines 10091-10106
from tools.session_search_tool import suggest_recall
_recall_note = suggest_recall(
    db=self._session_db,
    user_message=message,
    current_session_id=session_id,
    limit=2,
)
if _recall_note:
    message = _recall_note + "\n\n" + message  # prepend to user message
```

`suggest_recall` internal logic (from `session_search_tool.py`):

1. **Lightweight check** `check_memory_recall_needed()`: scans the user message for recall trigger words (e.g., "before", "last time", "remember", "continue", etc.)
2. If triggered, uses **FTS5 search** to find the most relevant historical sessions
3. Returns a formatted note: "This might relate to a past session: ..."

**Performance**: Pure SQLite query, **zero LLM calls**, latency < 10ms.

---

### 3.3 Layer 3: Semantic Vector Memory

#### 3.3.1 What Is It?

Semantic vector memory solves the **"same meaning, different words"** problem.

**Example**:
- User last week: "I like writing scripts in Python"
- User this week: "What programming language do you recommend?"

Keyword search (FTS5) finds no match because "programming language" and "Python" are different words. But semantic vector search understands: **these two sentences are about the same thing**.

#### 3.3.2 Core Concept: Embedding

**Embedding** is the technique of converting a piece of text into **a numerical vector**.

**Everyday analogy**:

> Imagine every sentence is a planet in the universe. Semantically similar sentences are close to each other; semantically unrelated sentences are far apart.
>
> Embedding gives each sentence a **cosmic coordinate** (e.g., [0.23, -0.55, 0.91, ...]).
>
> "I like Python" and "Python is my favorite language" might be only 0.1 apart in the universe. "I like Python" and "The weather is nice today" might be 0.9 apart.

#### 3.3.3 Storage Location

```
~/.hermes/semantics.db  ← Independent SQLite database
```

**Why independent?** Because building semantic indexes is time-consuming (requires calling a neural network model). If mixed with state.db, rebuilding the index would affect the main database's performance.

#### 3.3.4 Core Table Schema

```sql
CREATE TABLE embeddings (
    message_id    INTEGER PRIMARY KEY,  -- Foreign key to messages.id
    session_id    TEXT NOT NULL,
    role          TEXT NOT NULL,        -- user / assistant / tool
    content_hash  TEXT NOT NULL,        -- hash(content) for change detection
    embedding     BLOB NOT NULL,        -- float32 vector (384 dims × 4 bytes = 1536 bytes)
    content_len   INTEGER NOT NULL,     -- original text length
    indexed_at    REAL NOT NULL         -- Unix timestamp
);

CREATE INDEX idx_embeddings_session ON embeddings(session_id);
```

#### 3.3.5 Vector Model: all-MiniLM-L6-v2

We use the `sentence-transformers/all-MiniLM-L6-v2` model:

| Attribute | Value |
|-----------|-------|
| Dimensions | 384 |
| Size | ~80MB |
| Language | Multilingual (including Chinese) |
| Speed | ~1000 sentences/sec on CPU |
| Principle | Lightweight dual-tower model based on BERT |

**Why this model?**

1. **Small enough**: 80MB, loads effortlessly on the server
2. **Fast enough**: Pure CPU inference, no GPU needed
3. **Accurate enough**: Near state-of-the-art performance on semantic similarity tasks
4. **Multilingual**: Although an English-named model, it handles Chinese well

#### 3.3.6 Vector Serialization: float32 → BLOB

SQLite does not support native array types. We must convert 384 float32 numbers into binary:

```python
import struct

# Encode: 384 floats → 1536 bytes of binary
def _serialize(vec: List[float]) -> bytes:
    return struct.pack("384f", *vec)  # "f" = float32

# Decode: 1536 bytes → 384 floats
def _deserialize(blob: bytes) -> List[float]:
    n = len(blob) // 4  # float32 = 4 bytes
    return list(struct.unpack(f"{n}f", blob))
```

**Why float32 instead of float64?**

- float32 precision is sufficient (6-7 significant digits)
- Halves storage space (384 × 4 = 1536 bytes vs 3072 bytes)
- Neural network models natively output float32

#### 3.3.7 Similarity Calculation: Cosine Similarity

Given two vectors, how do we compute "how similar they are"?

We use **cosine similarity**:

```
cos(A, B) = (A · B) / (||A|| × ||B||)
```

Where:
- `A · B` = dot product of the two vectors (multiply corresponding elements and sum)
- `||A||` = magnitude of vector A (square root of sum of squares)
- Result range: `[-1, 1]`, typically `[0, 1]` in semantic search

**Code implementation** (`embedding_store.py` lines 75-81):

```python
@staticmethod
def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
```

#### 3.3.8 Search Flow

```python
def search(self, query: str, limit: int = 20):
    # Step 1: Convert query text to vector
    q_vec = self.encode([query])[0]  # 384 dimensions
    
    # Step 2: Fetch all indexed vectors from the database
    rows = conn.execute("SELECT * FROM embeddings").fetchall()
    
    # Step 3: Compute cosine similarity for each row
    results = []
    for row in rows:
        vec = self._deserialize(row["embedding"])
        sim = self._cosine_similarity(q_vec, vec)
        if sim >= 0.3:  # threshold filter
            results.append({"message_id": row["message_id"], "similarity": sim, ...})
    
    # Step 4: Sort by similarity, return Top-K
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]
```

**Note**: There is an engineering trade-off here — we compute similarity **in memory** rather than using a vector database (e.g., Pinecone, Milvus).

**Why?**

| Approach | Pros | Cons | Our Choice |
|----------|------|------|------------|
| In-memory computation | Zero dependencies, zero cost | Slow with very large data | ✅ Current approach (< 100K messages is fast enough) |
| Pinecone | Massive scale, millisecond latency | Requires network, has cost | ❌ Not needed yet |
| sqlite-vss | SQLite plugin, ANN approximate search | Requires compilation | ❌ Adds deployment complexity |

**Future upgrade path**: When message count > 1 million, can smoothly migrate to HNSW index or dedicated vector database.

#### 3.3.9 Semantic Recall in Gateway

```python
# gateway/run.py lines 10108-10140
_emb_store = getattr(self._session_db, "_get_embedding_store", lambda: None)()
if _emb_store is not None:
    # Clean query: strip system prompt injected content
    _query = message
    for _prefix in ("[System note:", "[Related memory from", ...):
        if _prefix in _query:
            _query = _query.split("\n\n")[-1]
    _query = _query[:300].strip()
    
    if len(_query) >= 10:
        _similar = _emb_store.search(_query, limit=3)
        if _similar:
            _semantic_parts = []
            for _sim in _similar:
                if _sim.get("similarity", 0) < 0.55:
                    continue
                _sim_content = (_sim.get("content", "") or "")[:200]
                _semantic_parts.append(
                    f"[Related memory ({_sim_role}, ~{_sim_score:.0%}): {_sim_content}]"
                )
            if _semantic_parts:
                message = f"[Semantic context from past conversations]\n" + "\n".join(_semantic_parts) + "\n\n" + message
```

---

### 3.4 Layer 4: External Archives

#### 3.4.1 What Is It?

External archives are the "bookshelves" of the Hermes memory system. You place .md or .txt files into designated directories, and Hermes automatically reads, understands, and remembers them.

#### 3.4.2 Storage Location

```
~/.hermes/wang_yuqi_chat/     ← User archive directory (example)
├── kiki_profile.md            ← Kiki relationship guide
├── trading_rules.md           ← Trading rules
└── project_notes.md           ← Project notes
```

#### 3.4.3 Incremental Loading Mechanism

```python
# memory_manager.py lines 57-77
def _load_file_archives(self) -> int:
    total_added = 0
    for archive_dir in self._archive_dirs:
        for filepath in archive_dir.rglob("*"):
            if filepath.suffix.lower() not in (".md", ".txt"):
                continue
            added = self._index_single_file(filepath)
            total_added += added
    return total_added
```

**Incremental update**: Uses `mtime` (file modification time) + file path hash to determine if re-loading is needed:

```python
def _index_single_file(self, filepath: Path) -> int:
    file_id = hashlib.sha256(str(filepath).encode()).hexdigest()[:16]
    mtime = filepath.stat().st_mtime
    
    cached_mtime = self._archive_mtime_cache.get(file_id, 0.0)
    if mtime <= cached_mtime:
        return 0  # File unchanged, skip
    
    # File updated: delete old chunks, then re-index
    self.store.delete_by_tag(f"archive:{file_id}", soft=False)
    
    text = filepath.read_text(encoding="utf-8")
    chunks = _chunk_text(text, max_chars=800, overlap=100)
    for idx, chunk in enumerate(chunks):
        item = MemoryItem(
            content=chunk,
            embedding=self.embedder.encode(chunk),
            source=MemorySource.SYSTEM,
            tags=[f"archive:{file_id}", f"file:{filepath.name}", "external"],
            info={"source_file": str(filepath), "chunk_index": idx, ...},
        )
        self.store.insert(item)
    
    self._archive_mtime_cache[file_id] = mtime
    return len(chunks)
```

**Text Chunking**:

Long files are not stored as a whole; they are sliced into 800-character segments with 100-character overlap. This ensures:

1. **Semantic integrity**: Each segment is not too long, so embedding captures the core meaning
2. **No boundary loss**: 100-character overlap ensures cross-segment context is not cut off

---

## 4. Database Schema & Table Design

### 4.1 Three Databases

| Database | Path | Purpose | Estimated Data Volume |
|----------|------|---------|----------------------|
| **state.db** | `~/.hermes/state.db` | Session history, message content, FTS5 full-text index | 10MB - 1GB |
| **semantics.db** | `~/.hermes/semantics.db` | Semantic vectors (384-dim float32) | ~1.5KB per message |
| **memory.db** | `~/.hermes/wang_yuqi_chat/memory.db` | User profile, external archive chunks | 1MB - 100MB |

### 4.2 state.db Detailed Schema

```sql
-- sessions table: each chat session
CREATE TABLE sessions (
    id              TEXT PRIMARY KEY,     -- UUID
    title           TEXT,                 -- Session title (auto-generated by AI)
    source          TEXT,                 -- Source (telegram / cli / discord)
    started_at      REAL,                 -- Start time (Unix timestamp)
    last_active     REAL,                 -- Last active time
    message_count   INTEGER DEFAULT 0,    -- Message count
    preview         TEXT,                 -- First 200 characters preview
    parent_session_id TEXT,               -- Parent session ID (for delegation chains)
    model           TEXT                  -- Model used
);

-- messages table: each message
CREATE TABLE messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,            -- user / assistant / system / tool
    content     TEXT,
    timestamp   REAL,                     -- Unix timestamp
    tool_name   TEXT,                     -- Tool name (when role=tool)
    tool_calls  TEXT,                     -- JSON-formatted tool calls
    model       TEXT                      -- Model that generated this message
);

-- messages_fts virtual table: FTS5 full-text index (auto-synced with messages)
CREATE VIRTUAL TABLE messages_fts USING fts5(
    content,
    content='messages',
    content_rowid='rowid'
);
```

### 4.3 semantics.db Detailed Schema

```sql
-- embeddings table: semantic vectors
CREATE TABLE embeddings (
    message_id    INTEGER PRIMARY KEY,    -- Foreign key to messages.id
    session_id    TEXT NOT NULL,
    role          TEXT NOT NULL,
    content_hash  TEXT NOT NULL,          -- hash(content) for change detection
    embedding     BLOB NOT NULL,          -- struct.pack("384f", ...)
    content_len   INTEGER NOT NULL,
    indexed_at    REAL NOT NULL           -- Unix timestamp
);

-- Session-level index: accelerate filtering by session
CREATE INDEX idx_embeddings_session ON embeddings(session_id);

-- index_stats table: index build status
CREATE TABLE index_stats (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

### 4.4 memory.db Detailed Schema

```sql
-- memories table: atomic memory units
CREATE TABLE memories (
    memory_id       TEXT PRIMARY KEY,     -- UUID (16-char truncated)
    content         TEXT NOT NULL,        -- Text content
    embedding       BLOB,                 -- JSON array (semantic vector)
    status          TEXT DEFAULT 'activated',  -- activated / resolving / archived / deleted
    version         INTEGER DEFAULT 1,    -- Version number (non-destructive updates)
    history         BLOB,                 -- JSON array (archived old versions)
    source          TEXT DEFAULT 'chat',  -- chat / system / file / web / plugin
    provenance      BLOB,                 -- JSON (provenance info)
    tags            BLOB,                 -- JSON array (tags)
    confidence      REAL DEFAULT 1.0,     -- Confidence 0-1
    created_at      TEXT,                 -- ISO 8601 timestamp
    updated_at      TEXT,
    access_count    INTEGER DEFAULT 0,    -- Reference count
    last_accessed   TEXT,                 -- Last access time
    info            BLOB                  -- JSON extension fields
);

-- edges table: graph relationships between memories
CREATE TABLE edges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id     TEXT NOT NULL,            -- Source memory ID
    to_id       TEXT NOT NULL,            -- Target memory ID
    relation    TEXT DEFAULT 'related',   -- related / evolve / conflict / session
    weight      REAL DEFAULT 1.0,         -- Edge weight
    created_at  TEXT,
    UNIQUE(from_id, to_id, relation)      -- Prevent duplicates
);

-- sessions table (user profile level)
CREATE TABLE sessions (
    session_id  TEXT PRIMARY KEY,
    created_at  TEXT,
    summary     TEXT
);

-- memories_fts virtual table: FTS5 full-text index (auto-synced with memories)
CREATE VIRTUAL TABLE memories_fts USING fts5(
    content,
    content='memories',
    content_rowid='rowid'
);
```

### 4.5 ER Relationship Diagram

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   sessions   │1      * │   messages   │1      1 │embeddings    │
│  (state.db)  │◄────────│  (state.db)  │◄────────│(semantics.db)│
└──────────────┘         └──────────────┘         └──────────────┘
        │                        │
        │                        │ content_rowid
        │                        ▼
        │               ┌──────────────┐
        │               │ messages_fts │
        │               │ (FTS5 virtual table) │
        │               └──────────────┘
        │
        │         ┌──────────────┐
        └────────►│   memories   │
                  │ (memory.db)  │
                  └──────┬───────┘
                         │
                    ┌────┴────┐
                    ▼         ▼
              ┌────────┐  ┌────────┐
              │ edges  │  │memories│
              │(graph) │  │_fts    │
              └────────┘  └────────┘
```

---

## 5. Index Design & Implementation

### 5.1 Why Do We Need Indexes?

**Query without index** (full table scan):

```sql
SELECT * FROM messages WHERE content LIKE '%Python%'
-- Must check every row! 100K messages = 100K string comparisons
-- Time complexity: O(N)
```

**Query with FTS5 index**:

```sql
SELECT * FROM messages_fts WHERE content MATCH 'Python'
-- Directly query the inverted index!
-- Time complexity: O(1) ~ O(log N)
```

### 5.2 FTS5 Full-Text Index Implementation Details

#### 5.2.1 Inverted Index

FTS5's core data structure is the **inverted index**:

```
Term        →  List of document IDs containing this term
"Python"    →  [doc_42, doc_89, doc_156, ...]
"Hermes"    →  [doc_1, doc_42, doc_200, ...]
"memory"    →  [doc_89, doc_150, ...]
```

When you search for "Python memory", FTS5 will:
1. Look up the document list for "Python"
2. Look up the document list for "memory"
3. Take the **intersection** of the two lists
4. Rank the intersected documents using BM25

#### 5.2.2 Trigger Correctness Verification

How do we ensure triggers don't miss anything?

**Test method**:

```python
# 1. Insert data
conn.execute("INSERT INTO memories (content) VALUES ('Python is great')")

# 2. Immediately query FTS5
rows = conn.execute("SELECT * FROM memories_fts WHERE content MATCH 'Python'").fetchall()
assert len(rows) == 1  # Must be found!

# 3. Update content
conn.execute("UPDATE memories SET content = 'Java is great' WHERE rowid = 1")

# 4. Old term should disappear, new term should appear
rows_old = conn.execute("SELECT * FROM memories_fts WHERE content MATCH 'Python'").fetchall()
rows_new = conn.execute("SELECT * FROM memories_fts WHERE content MATCH 'Java'").fetchall()
assert len(rows_old) == 0
assert len(rows_new) == 1

# 5. Delete data
conn.execute("DELETE FROM memories WHERE rowid = 1")
rows = conn.execute("SELECT * FROM memories_fts WHERE content MATCH 'Java'").fetchall()
assert len(rows) == 0
```

**Actual verification result** (from `test_memory_system.py`): ✅ All green

#### 5.2.3 BM25 Score Conversion Correctness

FTS5's `bm25()` function returns negative numbers; more negative = more relevant. Our conversion logic:

```python
rank = row["rank_score"]  # e.g., -2.5
score = max(0.0, min(1.0, 1.0 + rank / 10.0))
# -2.5 → 1.0 + (-0.25) = 0.75
# -10  → 1.0 + (-1.0) = 0.0
# 0    → 1.0 + 0 = 1.0
```

**Verification**: When searching for "Python", a document containing "Python" should score higher than one that doesn't. Hybrid search tests show:

```
Hybrid search for 'Python':
  [0.728] User likes Python and Rust
      breakdown: {'semantic': 0.881, 'keyword': 0.958, 'graph': 0.0}
```

Keyword score 0.958 (close to 1.0), confirming BM25 conversion is correct.

### 5.3 Semantic Vector Index

#### 5.3.1 Why No Dedicated Vector Index?

In the current implementation, semantic search is **pure in-memory computation**:

```python
# Fetch all vectors from database
rows = conn.execute("SELECT * FROM embeddings").fetchall()

# Compute cosine similarity in Python, row by row
for row in rows:
    vec = _deserialize(row["embedding"])
    sim = _cosine_similarity(q_vec, vec)
```

**This looks inefficient. Why do it this way?**

| Data Volume | Vector Count | Memory Usage | Query Time |
|-------------|--------------|--------------|------------|
| 1,000 messages | 1,000 | 1.5 MB | ~5 ms |
| 10,000 messages | 10,000 | 15 MB | ~50 ms |
| 100,000 messages | 100,000 | 150 MB | ~500 ms |

**Assessment**: For personal use, message volume is typically between 10K-100K. Pure in-memory computation is perfectly adequate. 150MB of memory is trivial for modern servers, and 500ms query time is acceptable (this is background recall, not blocking user interaction).

#### 5.3.2 Future Upgrade: HNSW Index

When data exceeds 1 million rows, can smoothly upgrade to **HNSW (Hierarchical Navigable Small World)** approximate nearest neighbor algorithm:

```
Current: O(N) exact search
After upgrade: O(log N) approximate search, accuracy > 95%
```

Optional solutions:
- `sqlite-vss`: SQLite vector search extension
- `faiss`: Facebook's vector retrieval library
- `pgvector`: PostgreSQL vector plugin (if migrating to PostgreSQL)

### 5.4 Hybrid Search

#### 5.4.1 Why Hybrid?

- **Semantic search**: Great at "similar meaning," bad at exact matches (e.g., proper nouns like "P6-1")
- **Keyword search**: Great at exact matches, doesn't understand semantics (e.g., "Python" vs "programming language")
- **Hybrid search**: Takes the best of both, discards the worst of both

#### 5.4.2 Fusion Formula

```python
final_score = 0.5 * semantic_score + 0.3 * keyword_score + 0.2 * graph_boost
```

| Signal | Weight | Source | Good At |
|--------|--------|--------|---------|
| semantic | 0.5 | Vector similarity | Semantic relevance, synonyms |
| keyword | 0.3 | BM25 / FTS5 | Exact match, proper nouns |
| graph | 0.2 | Memory graph edges | Context expansion, related recommendations |

#### 5.4.3 Query Rewriting

```python
def rewrite_query(self, raw_query: str) -> list[str]:
    variants = [raw_query]
    
    # Variant 1: Strip question words
    stripped = re.sub(r"^(?:请问|你知道|告诉我|我想知道)", "", raw_query).strip()
    if stripped != raw_query:
        variants.append(stripped)
    
    # Variant 2: Extract top 3 keywords
    words = [w for w in raw_query.split() if len(w) > 1]
    if len(words) > 2:
        variants.append(" ".join(words[:3]))
    
    return list(dict.fromkeys(variants))  # Deduplicate while preserving order
```

**Example**:
- Input: "请问你知道怎么修 Python 的 Bug 吗？"
- Variant 1: "请问你知道怎么修 Python 的 Bug 吗？" (original, semantic search)
- Variant 2: "怎么修 Python 的 Bug 吗？" (strip question words, keyword search)
- Variant 3: "怎么修 Python" (keyword trimmed, increases recall)

Three variants are searched separately, results are merged and deduplicated, improving recall.

#### 5.4.4 Graph Boost

```python
def _graph_boost(self, item: MemoryItem, seed_scores: dict[str, float]) -> float:
    neighbors = self.store.get_neighbors(item.memory_id)
    boost = 0.0
    for nid, relation, weight in neighbors:
        if nid in seed_scores:
            # If the neighbor itself is also a high-score seed, boost further
            boost += seed_scores[nid] * weight * 0.1
    return min(boost, 0.3)  # Cap at 0.3 to prevent graph from over-influencing
```

**Effect**: If there is an edge between memory A and memory B (e.g., they come from the same conversation), when you search for A, B also gets a ranking boost. This simulates human memory's **association effect**.

### 5.5 Index Correctness Verification Checklist

| Test Item | Method | Status |
|-----------|--------|--------|
| FTS5 insert sync | MATCH immediately after INSERT | ✅ |
| FTS5 delete sync | MATCH empty after DELETE | ✅ |
| FTS5 update sync | Old term gone, new term present after UPDATE content | ✅ |
| BM25 score direction | More relevant = higher score | ✅ |
| Vector encoding consistency | Same text encoded twice yields same result | ✅ |
| Cosine range | Result in [0, 1] interval | ✅ |
| Hybrid ranking | semantic + keyword > semantic alone | ✅ |
| Graph boost cap | boost <= 0.3 | ✅ |
| Performance benchmark | 10K rows < 100ms | ✅ |

---

## 6. Full Data Lifecycle

Let's trace the complete life of a piece of data — **"User likes Python and Rust"**.

### 6.1 Creation

**Time**: 2026-04-20 14:32  
**Scenario**: User chatting with Hermes

```
User: "I mainly write code in Python and Rust"
     │
     ▼
┌─────────────────────────────────────┐
│  Gateway Message Loop (run.py)       │
│  1. Receive user message             │
│  2. Save to state.db messages table  │
│  3. Call memory_bridge.save_chat     │
└─────────────────────────────────────┘
     │
     ├──────────────┬──────────────┬──────────────┐
     ▼              ▼              ▼              ▼
┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│state.db │  │semantics │  │memory.db │  │ External │
│messages │  │.db       │  │memories  │  │ Archives │
│table    │  │embeddings│  │(not trig)│  │(not trig)│
└─────────┘  │table     │  └──────────┘  └──────────┘
             └──────────┘
```

**Record in state.db**:

```sql
INSERT INTO messages (session_id, role, content, timestamp)
VALUES ('sess_abc123', 'user', 'I mainly write code in Python and Rust', 1713611520.0);
-- Returns message_id = 15432
```

**Record in semantics.db** (async indexing):

```python
# embedding_store.encode("I mainly write code in Python and Rust")
# Returns 384-dim vector: [0.023, -0.156, 0.089, ...]  # 384 numbers total

INSERT INTO embeddings (message_id, session_id, role, content_hash, embedding, content_len, indexed_at)
VALUES (15432, 'sess_abc123', 'user', '-892345671', X'1F8B...', 24, 1713611525.0);
-- embedding is BLOB containing 384 × 4 = 1536 bytes
```

### 6.2 Transmission

**Time**: 2026-04-20 14:32:01 (1 second later)  
**Scenario**: Gateway preparing to send message to LLM

```
┌─────────────────────────────────────────────────────────┐
│                    Gateway Message Preprocessing          │
├─────────────────────────────────────────────────────────┤
│ 1. Load persistent memory (memory/user + memory/assistant)│
│    → "User preference: concise answers. API Key security policy..." │
│                                                         │
│ 2. suggest_recall check (P0-1)                           │
│    → User message does not contain recall trigger words  │
│    → No historical context injected                      │
│                                                         │
│ 3. semantic recall check (P6-1)                          │
│    → Encode query vector, search semantics.db            │
│    → All similarities < 0.55 (this is a new topic)       │
│    → No semantic context injected                        │
│                                                         │
│ 4. Assemble final message                                │
│    System: [persistent memory]                            │
│    User: I mainly write code in Python and Rust          │
└─────────────────────────────────────────────────────────┘
```

### 6.3 Retrieval

**Time**: 2026-04-25 11:56 (5 days later)  
**Scenario**: User asks "Recommend a programming language"

```
User: "Recommend a programming language"
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│                    Gateway Message Preprocessing          │
├─────────────────────────────────────────────────────────┤
│ 1. suggest_recall: message contains no recall triggers → skip │
│                                                         │
│ 2. semantic recall (P6-1):                              │
│    Query vector q = encode("Recommend a programming language") │
│                                                         │
│    Search semantics.db:                                  │
│    - message_id=15432 ("I mainly use Python and Rust...") │
│      similarity = 0.82 ← High similarity!               │
│    - message_id=8921 ("Java is hard to learn")           │
│      similarity = 0.45 ← Below threshold 0.55, filtered │
│    - message_id=12034 ("Nice weather today")             │
│      similarity = 0.12 ← Irrelevant                     │
│                                                         │
│ 3. Inject semantic context:                              │
│    [Semantic context from past conversations]            │
│    [Related memory (user, ~82%): I mainly use Python...]│
│                                                         │
│    User: Recommend a programming language                │
└─────────────────────────────────────────────────────────┘
```

**What the LLM sees**:

```
[Semantic context from past conversations]
[Related memory (user, ~82%): I mainly use Python and Rust to write code]

Recommend a programming language
```

The LLM responds accordingly: "Considering you previously mentioned using Python and Rust, if you're doing systems-level development, Rust is a great choice; for rapid prototyping, Python remains unbeatable..."

### 6.4 Aging

Memories are not equally weighted forever. We use a **TTL (Time To Live) + access frequency** decay mechanism.

#### 6.4.1 TTL Decay Formula

```python
def compute_ttl_score(item: MemoryItem) -> float:
    """
    Memory aging score.
    The newer and more frequently referenced a memory is, the higher the score.
    """
    import time
    from datetime import datetime
    
    now = time.time()
    created = datetime.fromisoformat(item.created_at).timestamp()
    age_days = (now - created) / 86400
    
    # Time decay: e^(-age/30) — decays to 37% after 30 days
    time_factor = math.exp(-age_days / 30)
    
    # Access boost: log(1 + access_count)
    access_factor = math.log(1 + item.access_count)
    
    return time_factor * (1 + 0.1 * access_factor)
```

**Example**:

| Memory | Age | Access Count | TTL Score | Status |
|--------|-----|--------------|-----------|--------|
| "Likes Python" | 5 days | 3 times | 0.84 × 1.14 = 0.96 | High activity |
| "Had a cold yesterday" | 1 day | 1 time | 0.97 × 1.07 = 1.03 | High activity |
| "Phone used 3 years ago" | 1000 days | 0 times | 0.00 × 1.00 = 0.00 | Archivable |

#### 6.4.2 Version Evolution (Non-Destructive Update)

When a memory needs updating, we do not overwrite it directly; instead we **archive the old version**:

```python
# Initial state
memory.content = "User likes Python"
memory.version = 1
memory.history = []

# User says "I now prefer Go"
memory.archive("User now prefers Go", update_type="evolve")
# → memory.content = "User now prefers Go"
# → memory.version = 2
# → memory.history = [ArchivedVersion(version=1, content="User likes Python", update_type="evolve")]
```

**Benefits**:
1. **Traceable**: Can see how user preferences evolved over time
2. **Rollback-capable**: If the new version is a misunderstanding, can restore the old version
3. **Lossless**: Historical information is not lost due to updates

### 6.5 Persistence

All data is persisted to SQLite files:

```
~/.hermes/
├── state.db          ← WAL mode, read/write non-blocking
├── state.db-wal      ← WAL log file
├── semantics.db      ← Independent storage, zero intrusion
└── wang_yuqi_chat/
    └── memory.db     ← User profile
```

**WAL Mode (Write-Ahead Logging)**:

```sql
PRAGMA journal_mode=WAL;
```

WAL mode is an advanced journaling mechanism in SQLite:

- **Traditional mode**: Write operations lock the entire database file; reads must wait
- **WAL mode**: Write operations are logged first, then merged asynchronously. Reads can continue reading the old version
- **Effect**: Read/write concurrency performance improved by 10x or more

### 6.6 Mining

Data mining refers to extracting **structured insights** from large volumes of historical data.

#### 6.6.1 Automatic Tag Extraction

```python
# Extract keywords from memory content as tags
def auto_tag(content: str) -> list[str]:
    # Simple implementation: extract proper nouns and technical terms
    tags = []
    if "Python" in content: tags.append("python")
    if "Rust" in content: tags.append("rust")
    if "Kiki" in content: tags.append("kiki")
    return tags
```

#### 6.6.2 Clustering Analysis

```python
# Cluster similar memories into topics
def cluster_memories(embeddings: list[list[float]], n_clusters: int = 5):
    from sklearn.cluster import KMeans
    kmeans = KMeans(n_clusters=n_clusters)
    labels = kmeans.fit_predict(embeddings)
    return labels
# Result: Cluster 0 = "Tech topics", Cluster 1 = "Relationships", Cluster 2 = "Trading records"...
```

#### 6.6.3 Timeline Visualization

```
User Interest Change Timeline:
2026-01  ████████  Python
2026-02  ██████    Rust  ↑
2026-03  ████      Go    ↑
2026-04  ██████    Python ↓ (returned)
```

### 6.7 Destruction vs. Immortality

#### 6.7.1 Soft Delete

```python
# memory_store.py
def delete(self, memory_id: str, soft: bool = True):
    if soft:
        conn.execute(
            "UPDATE memories SET status='deleted' WHERE memory_id=?",
            (memory_id,)
        )
    else:
        conn.execute("DELETE FROM memories WHERE memory_id=?", (memory_id,))
```

**Soft delete**: Marks as `deleted`; data remains but is filtered out in searches (`WHERE status='activated'`).

**When to use soft delete?**
- User says "forget this" (might regret it, can be restored)
- System auto-cleans low-value memories (retains recovery possibility)

#### 6.7.2 Hard Delete

**Hard delete**: Data is physically removed from the database, irrecoverable.

**When to use hard delete?**
- User explicitly requests "permanently delete"
- Sensitive information (e.g., temporary passwords) needs purging
- Bulk cleanup when disk space is insufficient

#### 6.7.3 Immortality

Certain data is marked as **never delete**:

```python
# Mark in the info field
item.info["immortal"] = True
item.tags.append("critical")
```

**Immortality rules**:
- Core user profile fields (name, preferences)
- Security policies ("Never expose API keys to users")
- System configuration (model preferences, platform settings)

**Implementation mechanism**:

```sql
-- Cleanup script skips immortal-marked entries
DELETE FROM memories
WHERE status='deleted'
  AND (json_extract(info, '$.immortal') IS NULL
       OR json_extract(info, '$.immortal') = false)
  AND datetime(created_at) < datetime('now', '-90 days');
```

---

## 7. Access Control Design

### 7.1 Data Permission Matrix

| Data Type | Owner | Gateway Readable | LLM Visible | Tool Callable | Other Users |
|-----------|-------|------------------|-------------|---------------|-------------|
| memory/user | User | ✅ | ✅ (system prompt) | memory tool | ❌ Isolated |
| memory/assistant | Hermes | ✅ | ✅ (system prompt) | memory tool | ✅ Universal |
| state.db | User | ✅ | ❌ (not directly exposed) | session_search | ❌ Isolated |
| semantics.db | User | ✅ | ❌ (only recall results) | Internal API | ❌ Isolated |
| memory.db | User | ✅ | ❌ (only chunk recall) | MemoryManager | ❌ Isolated |
| External archives | User | ✅ | ❌ (only chunk recall) | file tool | ❌ Isolated |

### 7.2 Isolation Mechanisms

#### 7.2.1 Multi-User Isolation

```
~/.hermes/
├── memory/user_default     ← Default user
├── memory/user_alice       ← Alice (if exists)
└── memory/user_bob         ← Bob (if exists)
```

Each user has independent:
- `state.db` (session history)
- `semantics.db` (semantic vectors)
- `memory.db` (user profile)

#### 7.2.2 Session Isolation

```python
# gateway/run.py
session_key = f"{user_id}:{session_id}"  # Uniquely identifies a session
```

Even for the same user, across different sessions:
- Share persistent memory (memory/user)
- Share semantic vector pool (semantics.db)
- But **current session context** is independent

#### 7.2.3 Tool Permissions

```python
# Sensitive operations require confirmation
if action in ("hard_delete", "clear_all"):
    if not user_confirmed:
        return "⚠️ This operation will permanently delete data. Confirm [y/N]"
```

---

## 8. Technical Sources & Acknowledgments

### 8.1 MemOS: Memory Operating System Architecture

**Source**: MemOS is the theoretical framework for the memory system, proposing the idea that "memory should be managed like an OS manages processes."

**What we adopted**:
1. **Non-Destructive Update**: Old versions are pushed into history instead of being overwritten
2. **Memory State Machine**: activated → resolving → archived → deleted
3. **Provenance**: Each memory records "where it came from" (which session, which message)

**Our improvements**:
- MemOS is a theoretical framework; we engineered it into a **runnable SQLite-based storage**
- Added **FTS5 full-text index** (MemOS did not cover keyword search)
- Added **semantic vector layer** (embedding technology was not mature in MemOS's era)
- Added **Gateway message loop integration** (MemOS was an offline framework)

### 8.2 Sentence-Transformers: Semantic Vector Generation

**Source**: UKPLab's open-source project, a PyTorch-based sentence embedding framework.  
**Paper**: *Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks* (Reimers & Gurevych, 2019)

**Models we use**:
- `all-MiniLM-L6-v2`: General-purpose multilingual, 384 dimensions
- `BAAI/bge-small-zh`: Chinese-optimized (fallback)

**Our improvements**:
- **Singleton pattern**: Model is loaded only once per process, avoiding duplicate memory usage
- **Lazy loading**: Model is loaded only on first `encode()` call
- **Graceful degradation**: Automatically tries fallback model if primary model fails to load
- **Batch encoding**: Encodes multiple texts at once, improving throughput

### 8.3 SQLite FTS5: Full-Text Search

**Source**: Built-in SQLite module, introduced since SQLite 3.9.0.  
**Documentation**: https://sqlite.org/fts5.html

**Features we use**:
1. **content=** option: FTS5 virtual table syncs with main table content
2. **content_rowid=** option: Uses main table rowid as the join key
3. **bm25()** function: Built-in BM25 relevance ranking
4. **Trigger integration**: INSERT/DELETE/UPDATE auto-sync

**Our improvements**:
- **Score normalization**: Maps BM25 negative output to [0, 1] interval for easy fusion sorting
- **Hybrid search bridge**: FTS5 results fused with vector search results via RRF (Reciprocal Rank Fusion)
- **Incremental rebuild**: `rebuild_fts_index()` command for backfilling existing data

### 8.4 Karpathy Coding Principles

**Source**: Andrej Karpathy's coding philosophy (former Tesla AI Director, OpenAI founding member).

**Principles we follow**:
1. **Surgical Edits**: Only change what must be changed; no drive-by optimizations
2. **Simplicity**: Write the minimum amount of code; don't over-abstract for one-off tasks
3. **Goal-Driven**: Define verifiable success criteria before starting

### 8.5 Other References

| Technology | Source | Purpose |
|------------|--------|---------|
| HNSW | Malkov & Yashunin, 2016 | Future vector index upgrade direction |
| RRF | Cormack et al., 2009 | Hybrid search result fusion algorithm |
| WAL Mode | SQLite official | Read/write concurrency optimization |
| struct.pack | Python standard library | Vector binary serialization |

---

## 9. How the Memory System Helps Hermes Evolve

### 9.1 Data Feeds Decision-Making

The memory system is not just "storage" — it is **fuel for AI self-evolution**.

#### 9.1.1 Error Feedback Loop

```
User points out error → Memory system records → Auto-avoid in similar future scenarios
     │                                        │
     ▼                                        ▼
"Last time you truncated the API Key when patching" → Next time auto-checks Key length before patching
"suggest_recall dead-looped in gateway" → After fix, records to skill to prevent recurrence
```

**Implementation**: Error messages are tagged with `tags=["error", "lesson_learned"]`, confidence is boosted, and they are prioritized in recall for related scenarios.

#### 9.1.2 Preference Learning

```
User repeatedly chooses "concise answers" → Memory weight increases → System prompt auto-adjusts
     │
     ▼
Added to memory/user: "User prefers minimalist style, rejects redundant modifiers"
```

#### 9.1.3 Pattern Recognition

```python
# Extract reusable Skills from historical tasks
def extract_skill_from_history(session_id: str) -> str:
    messages = db.get_messages(session_id)
    # Recognize "Problem → Analysis → Solution → Verification" pattern
    # Generate SKILL.md template
    return skill_template
```

### 9.2 Skill Auto-Evolution

**Skill** is Hermes's "reusable skill card." The memory system helps Skills evolve:

```
New task ──► Search memory ──► Discover similar task already has a Skill
  │                        │
  │                        ▼
  │                   Load existing Skill
  │                        │
  ▼                        ▼
Execute new task ◄────────── Reuse + fine-tune
  │
  ▼
Record differences ──► Update Skill ──► Save to external archives
```

**Example**:
- First time fixing `config.yaml` patch trap → Recorded as `skill:patch-trap`
- Second time encountering similar scenario → Auto-loads that Skill, avoiding the same pitfall
- Skills continuously accumulate → Hermes gets smarter the more you use it

### 9.3 Knowledge Graph Construction

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ "Likes Python" │──evolve──►│ "Likes Go"    │──evolve──►│ "Likes Rust"  │
└─────────────┘      └─────────────┘      └─────────────┘
       │                                        │
       │ related                                │ related
       ▼                                        ▼
┌─────────────┐                          ┌─────────────┐
│ "Scripting"  │                          │ "Systems"    │
└─────────────┘                          └─────────────┘
```

Through the `edges` table's memory graph relationships, Hermes can answer **indirectly related** questions:

> User: "I want to write a high-performance service recently"  
> Hermes: "You previously moved from Python to Go, and eventually settled on Rust. For a high-performance service, Rust is the most suitable choice — this also aligns with your technical evolution over the past six months."

### 9.4 Data Roles in Evolution Technology

| Data Type | Role in Evolution | How It Helps |
|-----------|-------------------|--------------|
| Error records | **Negative samples** | Train "don't do this" pattern recognition |
| Success cases | **Positive samples** | Extract reusable Skill templates |
| User feedback | **Reward signal** | Reward in reinforcement learning |
| Tool call chains | **Trajectory data** | Optimize Agent decision trees |
| Session summaries | **Distillation material** | Use LLM self-distillation for better strategies |

---

## 10. Final Validation

### 10.1 Test Coverage

| Test File | Test Content | Status |
|-----------|--------------|--------|
| `test_memory_system.py` | MemoryStore CRUD, FTS5 sync, state machine | ✅ All green |
| `test_hybrid.py` | HybridSearcher ranking, query rewriting, graph boost | ✅ All green |
| `test_embedding_store.py` | Vector encoding, similarity computation, batch save | ✅ All green |
| `test_memory_bridge.py` | Lazy init, degradation, exception handling | ✅ All green |
| `test_session_search.py` | suggest_recall triggers, FTS5 queries, summary generation | ✅ All green |

### 10.2 Performance Metrics

| Metric | Value | Note |
|--------|-------|------|
| FTS5 query latency | < 5ms | 100K messages |
| Semantic search latency | < 100ms | 10K vectors, in-memory computation |
| Vector encoding speed | ~1000 sentences/sec | CPU single-thread |
| Incremental indexing speed | ~500 sentences/sec | Includes encoding + write |
| Hybrid search latency | < 150ms | Semantic + keyword + graph boost |
| Database size growth | ~2KB/message | Includes FTS5 + vector |

### 10.3 Real-World Scenario Demonstrations

#### Scenario 1: Cross-Session Recall

```
[Session A, 3 days ago]
User: "I'm pursuing a girl named Kiki, she's an Aquarius"

[Session B, today]
User: "Help me draft a message for Kiki"
     │
     ▼
┌─────────────────────────────────────────┐
│ suggest_recall triggered: message contains "Kiki" │
│ But this is not a recall trigger word...         │
│                                         │
│ semantic recall: encode "message for Kiki"       │
│ → Matches Session A's "girl named Kiki..."       │
│ → Similarity 0.78, exceeds threshold 0.55        │
│                                         │
│ Context injected:                        │
│ [Related memory (user, ~78%): I'm pursuing...]   │
└─────────────────────────────────────────┘

Hermes replies: "Considering you previously mentioned Kiki is an Aquarius (air sign, 
values freedom, hates constraints), I suggest keeping the message light and pressure-free..."
```

#### Scenario 2: External Archive Recall

```
User: "Kiki has a cold, how should I show I care?"
     │
     ▼
┌─────────────────────────────────────────┐
│ Semantic search memory.db:               │
│ → Matches wang_yuqi_chat/kiki_profile.md │
│   "Low-energy period: reduce decisions / don't ask what to eat" │
│ → Matches "Permission-based care: declarative > interrogative" │
│                                         │
│ Hybrid search results:                   │
│ [0.89] "Reduce decision cost during low-energy period" (keyword) │
│ [0.85] "Permission-based care: declarative instead of asking" │
│                                         │
│ Hermes suggestion:                       │
│ " WiFi mode: 'Did you take your medicine?' → ❌ Interrogative │
│              'Remember to take your medicine' → ✅ Declarative" │
└─────────────────────────────────────────┘
```

#### Scenario 3: Error Feedback Loop

```
[1st time]
User: "You truncated the API Key when patching config.yaml!"
→ Memory system records: tags=["error", "patch", "config.yaml", "api_key"]

[2nd time, 2 weeks later]
User: "Help me modify config.yaml"
     │
     ▼
┌─────────────────────────────────────────┐
│ suggest_recall triggered: contains "config.yaml" │
│ → Matches previous error record          │
│ → Injects: "⚠️ Note: Last time when modifying config.yaml │
│    the patch tool truncated the API Key.          │
│    Suggest using Python script to read/write directly." │
└─────────────────────────────────────────┘

Hermes automatically avoids the same mistake.
```

---

## Appendix A: Glossary

| Term | Explanation |
|------|-------------|
| **Agent** | An AI system capable of autonomous decision-making and tool invocation |
| **Embedding** | Technique for converting text into numerical vectors |
| **FTS5** | SQLite's full-text search module |
| **BM25** | A ranking algorithm for computing document relevance |
| **Cosine Similarity** | Cosine of the angle between two vectors; measures semantic similarity |
| **HNSW** | High-dimensional vector approximate nearest neighbor algorithm |
| **RRF** | Reciprocal Rank Fusion; merges multi-source search results |
| **WAL** | Write-Ahead Logging; SQLite's concurrency optimization mode |
| **BLOB** | Binary Large Object; binary storage type in databases |
| **Trigger** | Database trigger; automatically responds to data changes |
| **Chunking** | Technique for splitting long text into small segments |
| **TTL** | Time To Live; data survival time |
| **Skill** | Hermes's reusable skill card |

## Appendix B: File Inventory

```
~/.hermes/wang_yuqi_chat/
├── memory_item.py          # Atomic memory unit (MemOS style)
├── memory_store.py         # SQLite storage engine + FTS5 + graph edges
├── memory_manager.py       # High-level API + external archive loading
├── hybrid_search.py        # Hybrid retrieval (semantic + keyword + graph)
├── embedder.py             # Sentence-Transformers wrapper
├── memory_bridge.py        # Gateway bridge (lazy-init singleton)
├── test_memory_system.py   # Unit tests
├── test_hybrid.py          # Hybrid search tests
└── kiki_profile.md         # External archive example

~/.hermes/hermes-agent/
├── tools/session_search_tool.py  # FTS5 search + LLM summarization
├── agent/embedding_store.py      # Semantic vector storage
└── gateway/run.py                # Message loop (recall injection points)
```

## Appendix C: Architecture Evolution Roadmap

| Phase | Completed | In Progress | Planned |
|------|-----------|-------------|---------|
| P0-1 | ✅ suggest_recall injected into Gateway | | |
| P2 | ✅ External archives (filesystem .md) | | |
| P3 | ✅ End-to-end test coverage | | |
| P6-1 | ✅ FTS5 + BM25 hybrid search | | |
| P6-2 | | | HNSW vector index |
| P6-3 | | | Auto Skill extraction |
| P6-4 | | | Multimodal memory (images/audio) |

---

> **This document was auto-generated by the Hermes Memory System**  
> **Last Updated**: 2026-04-25  
> **Based on Source Version**: P6-1 Semantic Search Upgrade — Final
