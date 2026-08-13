# System Design — Progress Tracker

**Started:** 9 Aug 2026
**Project:** Bookmarker — FastAPI + Postgres, raw SQL via psycopg 3
**Pace:** ~1 hr/day, Mon–Fri, longer session Saturday

Legend: ✅ done · 🔄 in progress · ⬜ not started

---

## Week 1 — Build it, then learn to describe it

| Day | Topic | Status | Key finding |
|---|---|---|---|
| 1 | Build the app — 4 tables, 5 endpoints | ✅ | A `with` block *is* the transaction boundary. Splitting writes across helper calls silently breaks atomicity. |
| 2 | Seed 500k rows | ✅ | Naive inserts 2.5 s/10k (~7 min projected). COPY did 1.75M rows in 57.7 s. Round trips are the cost, and they scale with network distance. |
| 3 | Storage analysis + failure questions | ✅ | `bookmark_tags`: 103 MB heap + 73 MB index. Indexes are physical objects — disk, slower writes, competing for cache. |
| 4 | Query logging + EXPLAIN | ✅ | 21 queries confirmed — but 35.4 ms in the list query vs 0.8 ms across all 20 tag queries. **The named design flaw was not the measured bottleneck.** |
| 5 | Indexes | ✅ | `(user_id, created_at DESC)` → 29.2 ms to 0.382 ms (76×). Cost: 50 MB index on a 111 MB table. Leftmost-prefix rule. |
| 6 (Sat) | Guess the insides of an app I use | ⬜ | |

**Artifacts:** `baseline.md`, `notes/day-04-query-logging.md`, `notes/day-05-indexes.md`, `bench.ps1`, `seed.py`

---

## Week 2 — Making the database fast

| Day | Topic | Status | Key finding |
|---|---|---|---|
| 1 | Tag join + `ILIKE` search | 🔄 | Expect: `bookmark_tags` has no index on `tag_id`; `ILIKE '%x%'` cannot use a B-tree at all. |
| 2 | Index types beyond B-tree — `pg_trgm`, GIN, full-text | ⬜ | |
| 3 | When indexes *don't* help — low cardinality, leading wildcards, write cost | ⬜ | |
| 4 | Transactions and races — fix the find-or-create tag race with `ON CONFLICT` | ⬜ | Already have this bug: two concurrent requests creating the same tag → unique violation → 500. |
| 5 | Denormalization + keyset pagination | ⬜ | Fixes the deep-offset problem found on Day 5. |
| 6 (Sat) | Design a pastebin with expiry | ⬜ | |

---

## Week 3 — Break it on purpose

| Day | Topic | Status | Key finding |
|---|---|---|---|
| 1 | Learn k6, first load test | ⬜ | Need a better instrument — curl's 260 ms floor is louder than the queries now. |
| 2 | p50 vs p99, why averages lie | ⬜ | |
| 3 | Turn up the dial: 10 → 50 → 200 → 1000 users | ⬜ | |
| 4 | Find the culprit — pool exhaustion at `max_size=10` is the prediction | ⬜ | |
| 5 | Fix one thing, re-test | ⬜ | |
| 6 (Sat) | Write it up as an incident report | ⬜ | |

---

## Week 4 — Caching

| Day | Topic | Status |
|---|---|---|
| 1 | In-memory dict cache — build one by hand | ⬜ |
| 2 | Stale data — the price of every cache | ⬜ |
| 3 | Move to Redis, and why (three app copies = three disagreeing caches) | ⬜ |
| 4 | Stampede, hot keys, cache penetration | ⬜ |
| 5 | Re-run load test with caching on | ⬜ |
| 6 (Sat) | Design a link shortener | ⬜ |

---

## Week 5 — Queues

| Day | Topic | Status |
|---|---|---|
| 1 | Feel the problem — fetch page titles on save, watch it take 3 s | ⬜ |
| 2 | Fix it with a queue + worker | ⬜ |
| 3 | Retries, backoff, dead letter queues | ⬜ |
| 4 | Idempotency — jobs that run twice | ⬜ |
| 5 | What you gave up — how does the user know it finished? | ⬜ |
| 6 (Sat) | Design a notification system | ⬜ |

---

## Week 6 — More than one server

| Day | Topic | Status |
|---|---|---|
| 1 | Run two app copies behind nginx | ⬜ |
| 2 | Find what breaks — anything held in process memory | ⬜ |
| 3 | Set up a read replica | ⬜ |
| 4 | Replication lag and read-your-own-writes | ⬜ |
| 5 | Sharding — choosing a partition key | ⬜ |
| 6 (Sat) | Design a social media feed | ⬜ |

---

## Week 7 — When things go wrong

| Day | Topic | Status |
|---|---|---|
| 1 | Timeouts on every outbound call | ⬜ |
| 2 | Circuit breakers | ⬜ |
| 3 | Rate limiting — token bucket from scratch | ⬜ |
| 4 | Metrics, logs, traces; what should page someone | ⬜ |
| 5 | Read a real published incident report | ⬜ |
| 6 (Sat) | Design a rate limiter across 50 servers | ⬜ |

---

## Week 8 — Interview shape

| Day | Topic | Status |
|---|---|---|
| 1 | The six-phase framework, from memory | ⬜ |
| 2 | Timed: chat app | ⬜ |
| 3 | Timed: URL shortener with click analytics | ⬜ |
| 4 | Timed: ride-hailing driver matching | ⬜ |
| 5 | Go one level deeper on the hardest part of each | ⬜ |
| 6 (Sat) | **Live mock with a human** — book this early | ⬜ |

---

## Running list of things I couldn't answer

Add a line every time something comes up that I can't explain. Week 8 clears it.

- Why exactly does `ILIKE '%x%'` prevent B-tree use? (answering this week)
- How much does one index actually cost per insert? (FK check drowned the signal
  on Day 5 — needs a controlled test)
- Is `pg_stat_statements` enabled on our production DB at work?

## Known bugs I'm deliberately keeping

| Bug | Why it's still here | Fixed in |
|---|---|---|
| N+1 on tag loading | Built on purpose to see it; measured at only 0.8 ms locally, but 20 extra round trips ≈ 20 ms in production | Week 4 |
| Find-or-create tag race | Two concurrent requests → unique violation → 500 | Week 2 Day 4 |
| Duplicate tags in payload crash the request | `tags: ["work","work"]` violates the composite PK | Week 2 Day 4 |
| Deep offset pagination | `OFFSET 9980` makes the composite index useless | Week 2 Day 5 |
| No auth at all | Out of scope — this is a lab, not a product | Never |