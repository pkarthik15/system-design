# System Design — Concept Checklist

Not a schedule. This is the list of *ideas*, tracked separately, because the same
concept often shows up across several days and some show up before their week.

Legend: ✅ learned and demonstrated on my own system · 🔄 partly · ⬜ not yet

---

## Databases — fundamentals

| Concept | Status | Where I met it |
|---|---|---|
| Connection pooling — why connections are expensive, borrow/return | ✅ | Day 1. `min_size=2, max_size=10` set deliberately low for Week 3. |
| Transactions — atomicity, the `with` block as the boundary | ✅ | Day 1. Splitting writes across helpers = separate commits, no rollback. |
| Rollback on exception, and why swallowing errors breaks it | ✅ | Day 1. `try` must wrap the `with`, not sit inside it. |
| Parameterised queries / SQL injection | ✅ | Day 1. `%s` is a placeholder, not string formatting. |
| Foreign keys and cascade behaviour | ✅ | Day 1. `ON DELETE CASCADE` removed a whole endpoint's worth of code. |
| Many-to-many via a join table, composite primary key | ✅ | Day 1. `bookmark_tags(bookmark_id, tag_id)`. |
| `RETURNING` — one round trip instead of insert-then-select | ✅ | Day 1. |
| Bulk loading — `COPY` vs per-row inserts | ✅ | Day 2. 1.75M rows in 57.7 s vs ~7 min projected. |
| Round trips as the dominant cost, scaling with network distance | ✅ | Day 2. Localhost hid most of it — production would be ~30 min. |
| Per-row storage overhead (MVCC row headers) | ✅ | Day 3. 16 bytes of data → ~82 bytes on disk. |
| Read-modify-write races | 🔄 | Day 1 — identified the find-or-create tag race. Not yet fixed. |
| Isolation levels and the anomalies each prevents | ⬜ | Week 2 |
| Optimistic vs pessimistic locking | ⬜ | Week 2 |
| Normalization vs denormalization | ⬜ | Week 2 |
| SQL vs NoSQL — what each shape is actually good at | ⬜ | Week 2 |

## Databases — performance

| Concept | Status | Where I met it |
|---|---|---|
| Reading `EXPLAIN ANALYZE` — bottom-up, cost vs actual | ✅ | Day 4–5. |
| `Seq Scan` vs `Index Scan`; `Filter` vs `Index Cond` | ✅ | Day 5. One word tells you which. |
| B-tree indexes — what they are, why sorted order matters | ✅ | Day 5. 29.2 ms → 0.382 ms. |
| Composite indexes and the leftmost-prefix rule | ✅ | Day 5. `(A,B)` covers A and A+B, never B alone. |
| Index cost — disk, write amplification, cache competition | ✅ | Day 5. 50 MB index on a 111 MB table. |
| An index helps a *query shape*, not a table | ✅ | Day 5. Composite index ignored at `OFFSET 9980`. |
| Fixing one bottleneck promotes the next | ✅ | Day 5. Sort was always 5 ms; only visible once the scan stopped hiding it. |
| Measured bottleneck ≠ named design flaw | ✅ | Day 4. N+1 was 2% of the time; the query I ignored was 97%. |
| Query planning vs execution; prepared statements | ✅ | Day 4. First parse 9.9 ms; psycopg auto-prepared after 5 repeats. |
| Stale statistics causing bad plans; `ANALYZE` | 🔄 | Day 5, mentioned but not hit. |
| Parallel query execution | ✅ | Day 4. 2 workers compensating for the missing index. |
| N+1 query problem | ✅ | Day 1 built, Day 4 measured. Fix deferred to Week 4. |
| Offset pagination and why it degrades | ✅ | Day 4–5. Full quicksort of 10k rows vs top-N heapsort of 20. |
| Keyset pagination | ⬜ | Week 2 |
| Why `ILIKE '%x%'` can't use a B-tree | 🔄 | Week 2 — next up. |
| Trigram / GIN indexes, full-text search | ⬜ | Week 2 |
| `ON CONFLICT` for concurrent upserts | ⬜ | Week 2 |

## Observability

| Concept | Status | Where I met it |
|---|---|---|
| Measure, don't infer | ✅ | Day 4. My prediction was right on count, wrong on where time went. |
| Know what your instrument costs | ✅ | Day 5. curl's 260 ms floor was 90% of every measurement. |
| Query logging — `log_min_duration_statement`, setting scope levels | ✅ | Day 4. |
| `pg_stat_statements` — ranking by total time, not average | 🔄 | Day 4, understood but not yet enabled. |
| Slow query logs in production | ✅ | Day 4, conceptually. |
| p50 vs p99, why averages lie | ⬜ | Week 3 |
| Metrics vs logs vs traces; RED and USE | ⬜ | Week 7 |
| SLIs, SLOs, error budgets | ⬜ | Week 7 |

## Application architecture

| Concept | Status | Where I met it |
|---|---|---|
| Blocking vs async, and why the driver decides | ✅ | Day 1. `async def` + blocking driver = one request at a time. |
| Threadpool concurrency ceilings | 🔄 | Day 1. Real ceiling is `min(40 threads, 10 connections)` = 10. Untested. |
| Fail fast at startup vs failing per-request | ✅ | Day 1. `pool.wait()` — a process that dies at boot is caught by the deploy. |
| Context managers as guaranteed cleanup | ✅ | Day 1. Leaked connections are a real outage mode. |
| Not leaking internal errors to clients | ✅ | Day 1. |
| Idempotency | ⬜ | Week 5 |
| Statelessness — what breaks with two app copies | ⬜ | Week 6 |

## Caching

| Concept | Status |
|---|---|
| Cache-aside, read-through, write-through, write-behind | ⬜ |
| Stale data as the unavoidable price | ⬜ |
| Why an in-process cache breaks with multiple instances | ⬜ |
| Stampede / thundering herd | ⬜ |
| Hot keys | ⬜ |
| Cache penetration | ⬜ |
| TTL vs explicit invalidation vs versioned keys | ⬜ |

## Async and messaging

| Concept | Status |
|---|---|
| Queues vs logs (SQS/Rabbit vs Kafka) | ⬜ |
| At-most-once / at-least-once / exactly-once | ⬜ |
| Retries, exponential backoff, jitter | ⬜ |
| Dead letter queues, poison messages | ⬜ |
| Backpressure | ⬜ |
| The dual-write problem and the outbox pattern | ⬜ |
| Event notification vs event-carried state transfer | ⬜ |

## Distribution

| Concept | Status |
|---|---|
| Load balancing | ⬜ |
| Leader–follower replication | ⬜ |
| Replication lag, read-your-own-writes | ⬜ |
| Partitioning / sharding; choosing a partition key | ⬜ |
| Hotspots from a bad partition key | ⬜ |
| Consistency models — strong, eventual, causal, monotonic | ⬜ |
| CAP, and why PACELC is the better frame | ⬜ |

## Reliability

| Concept | Status |
|---|---|
| Timeouts on every outbound call | ⬜ |
| Circuit breakers | ⬜ |
| Bulkheads, graceful degradation, load shedding | ⬜ |
| Rate limiting — token bucket, sliding window | ⬜ |
| Health checks | 🔄 |
| Blameless postmortems | ⬜ |

## Interview craft

| Concept | Status |
|---|---|
| The six-phase framework | ⬜ |
| Back-of-envelope estimation | ⬜ |
| Stating the cost of every component you add | 🔄 |
| Going deep on the hard part, not the easy one | ⬜ |

---

## The five ideas that generalise furthest

If I forget everything else from Week 1, keep these:

1. **Measure, don't infer.** The N+1 I was warned about was 2% of the time. The
   query nobody mentioned was 97%.
2. **Know what your instrument costs.** 90% of my first benchmark was curl.
3. **Every component has a price — say it out loud.** An index bought 76× reads
   and cost 45% disk plus slower writes. Naming the trade unprompted is the
   strongest senior signal available.
4. **Fixing the top bottleneck reveals the next one.** So re-measure after every
   change, never after three.
5. **A design flaw you can name is not the same as the bottleneck you measured.**
   Both matter. Only one of them is worth your afternoon.