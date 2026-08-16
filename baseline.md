# Baseline

Running record of measurements. Every change gets compared against this.

## Setup

- 5,000 users / 500k bookmarks / ~1.25M bookmark_tags
- Seeded with `random.seed(42)` — reproducible
- **heavy user: 2796** (14,884 bookmarks) — used for all measurements
- light user: _fill in_
- Postgres 16 in Docker, app on the same machine

## Method

- **Endpoint timings:** PowerShell `Measure-Command` around `curl.exe`, median of
  5 after one warmup. **curl.exe on Windows costs ~260 ms per invocation** —
  measured against `/docs` (no DB work) and subtracted below.
- **Query timings:** `EXPLAIN ANALYZE` in pgAdmin, second or third run (the first
  run after any schema change reads from cold cache and is meaningless).

---

## Endpoint timings

Measured wall-clock, with the ~260 ms curl floor subtracted.

| endpoint | before indexes | after Day 5 |
|---|---|---|
| list p1, heavy user | ~30 ms | **~1 ms** |
| list p1, light user | ~17 ms | **~0 ms** |
| list p500, heavy user | ~29 ms | **~0 ms** |
| tag=python, heavy | ~67 ms | **~12 ms** |
| search q=python, heavy | ~136 ms | **~45 ms** |
| search q=zeppelin, heavy | ~123 ms | **~7 ms** |

Several results are now within noise of the 260 ms floor. "~0 ms" means "too fast
for this instrument" — need k6 in Week 3.

---

## Query timings (EXPLAIN ANALYZE)

| query | before | after | change |
|---|---|---|---|
| list, user 2796, page 1 | 29.2 ms | **0.38 ms** | index on `(user_id, created_at DESC)` |
| list, user 2796, page 500 | 28.4 ms | ~7 ms | same index, but offset limits the gain |
| tag = python | 24 ms | 24 ms | left alone deliberately |
| search `%python%` | — | 0.5 ms | common term, `LIMIT` satisfied early |
| search `%zeppelin%` | 35.9 ms | **14.6 ms** | trigram GIN index |
| insert one bookmark | — | ~6 ms | 2.7 ms of it is the FK check |

---

## Storage

| | Day 3 | after Day 5 | after Day 6 |
|---|---|---|---|
| bookmarks table | 132 MB | 111 MB | 111 MB |
| bookmarks indexes | — | 50 MB | **82 MB** |
| bookmark_tags heap | 103 MB | 103 MB | 103 MB |
| bookmark_tags indexes | 73 MB | 73 MB | 73 MB |

Seed time: **57.7 s** via `COPY` (1.75M rows). Naive per-row inserts measured at
2.5 s per 10k → ~7 min projected.

---

## Index change log

| index | verdict | why |
|---|---|---|
| `bookmarks(user_id)` | **dropped** | redundant — leftmost prefix of the composite |
| `bookmarks(user_id, created_at DESC)` | **kept** | 29.2 ms → 0.38 ms, 76×. Cost: ~45% index overhead. |
| `bookmarks USING gin (title gin_trgm_ops)` | **kept, marginal** | 35.9 → 14.6 ms on rare terms. Cost: +32 MB (50→82 MB) and slower writes. Probably a net loss on a real product — kept to observe write cost in Week 3. |
| `bookmark_tags(tag_id, bookmark_id)` | **reverted** | made the tag query **30× worse** (24 ms → 743 ms). Planner switched to starting from the tag: 81,107 lookups to find 20 rows. |

---

## Open questions

- `page=500` still uses a different plan than `page=1` (full quicksort vs top-N
  heapsort). Keyset pagination would fix it — Week 2.
- Can't isolate the index write cost — the FK check (2.7 ms) drowns it. Needs a
  controlled test: insert 10k, drop index, insert 10k, compare.
- Search still can't use both `user_id` and the trigram index in one scan.
  `btree_gin` composite would, untested.
- Real concurrency ceiling is `min(40 threadpool threads, 10 pool connections)`
  = 10. Untested until Week 3.