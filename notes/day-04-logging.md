# Day 4 — Watching the database from the inside

**Goal:** stop inferring what my app does to Postgres by reading my own code, and
instead read what Postgres actually received.

---

## Why this matters

Everything I knew before today about query counts came from remembering code I
wrote three days ago. That works on a small app I just built. It fails on a
system with fifty endpoints, one someone else wrote, or anything where the slow
query is generated inside a library.

Every database can tell you what it was asked to do. Learning to ask is the
skill that transfers.

---

## Turning logging on

Postgres settings apply at four levels, narrowest wins:

| Level    | Command                                | Scope                      |
|----------|----------------------------------------|----------------------------|
| Session  | `SET log_min_duration_statement = 0`   | current connection only    |
| Database | `ALTER DATABASE db SET ...`            | new connections to that db |
| Role     | `ALTER ROLE user SET ...`              | that user                  |
| Server   | `ALTER SYSTEM SET ...`                 | everything on the server   |

Session level is useless here — a `SET` in pgAdmin only affects pgAdmin's own
connection, and the queries I want come from FastAPI's separate connections.

**Used database level:**

```sql
ALTER DATABASE bookmarker SET log_min_duration_statement = 0;
```

`0` = log every statement with its duration. Then **restart the app** — the pool
holds connections opened before the change and they won't pick it up.

My Postgres runs in Docker with `logging_collector = off`, so logs go to the
container's stdout: `docker logs -f <container>`.

**Turn off before load testing:**

```sql
ALTER DATABASE bookmarker RESET log_min_duration_statement;
```

---

## Finding 1 — the N+1 is not the bottleneck

One request to `GET /bookmarks?user_id=2796&page=1` produced **21 statements**,
exactly as predicted. But the time split was nothing like expected:

| statement | count | time |
|---|---|---|
| `LIST_BOOKMARKS` | 1 | **35.4 ms** |
| `TAGS_FOR_BOOKMARK` | 20 | **~0.8 ms total** (0.02–0.06 ms each) |

A 44:1 split. The N+1 I spent three days worrying about is ~2% of the database
time. The single query I assumed was fine is 97%.

**Lesson: a design flaw you can name is not the same as the bottleneck you
measured.** Both matter — but when they differ, only the measurement tells you
where to spend today. Optimising the 20 tag queries would have been a day's work
to save 0.8 ms.

The N+1 still needs fixing eventually, because:
- On production the app and DB are on different machines — 20 extra round trips
  at ~1 ms each is 20 ms of pure network wait, not 0.8 ms.
- It scales with page size. 20 bookmarks = 21 queries; 100 bookmarks = 101.

---

## Finding 2 — psycopg prepares statements automatically

The first five tag queries logged as `<unnamed>` with a `parse` step each time.
From the sixth onward they switched to `_pg3_0` and the parse lines vanished —
only `bind` and `execute` remained. Durations dropped from ~0.06 ms to ~0.02 ms.

psycopg noticed the repeated SQL and asked Postgres to remember the plan. Part of
why the N+1 measured so cheap.

Also learned: one query is three protocol steps, not one.
- **parse** — turn SQL text into a plan
- **bind** — attach the parameters
- **execute** — run it

The very first parse cost 9.9 ms. That's planning, not execution.

---

## Finding 3 — why the list query is slow

```sql
EXPLAIN ANALYZE
SELECT id, url, title, created_at, user_id
FROM bookmarks WHERE user_id = 2796
ORDER BY created_at DESC LIMIT 20 OFFSET 0;
```

```
Limit  (actual time=26.290..29.122 rows=20)
  -> Gather Merge  (actual time=26.288..29.119 rows=20)
       Workers Planned: 2 / Workers Launched: 2
       -> Sort  (actual time=22.701..22.703 rows=16 loops=3)
            Sort Key: created_at DESC
            Sort Method: top-N heapsort  Memory: 29kB
            -> Parallel Seq Scan on bookmarks  (actual time=13.414..22.000 rows=4961 loops=3)
                 Filter: (user_id = 2796)
                 Rows Removed by Filter: 320081
Execution Time: 29.211 ms
```

**`Seq Scan` + `Rows Removed by Filter: 320081`** (per worker, 3 workers ≈ 960k
row checks) to return 20 rows. No index on `user_id`, so Postgres has no way to
find that user's rows except by reading all 500,000.

Bonus: Postgres launched 2 parallel workers to compensate. Parallel query is why
this is 35 ms and not 100 ms.

---

## Finding 4 — the page-500 anomaly explained

`OFFSET 9980` measured *faster* than `OFFSET 0` in my bench. The plans show why:

| | page 1 | page 500 |
|---|---|---|
| Seq Scan | ~20 ms | ~20 ms |
| Sort method | top-N heapsort, 29 kB | quicksort, 842 kB |
| Rows through Gather Merge | 20 | 10,000 |
| Execution time | 29.2 ms | 28.4 ms |

Deep offset **is** more expensive — a full quicksort of 10,000 rows instead of
keeping a running top-20. But the sequential scan dominates both, so the
difference is invisible. Fix the scan and this becomes measurable.

---

## How to read EXPLAIN ANALYZE

1. **Read bottom-up.** Most indented = runs first. Data flows upward.
2. **The bottom line is usually the problem** — it's where data comes from.
3. **Ignore `cost`, read `actual time`.** Cost is a pre-run guess in arbitrary
   units. Actual time is milliseconds.
4. **`Rows Removed by Filter` is the waste indicator.** Big number = add an index.

| Sign | Meaning |
|---|---|
| `Seq Scan` | reading the whole table — usually the problem |
| `Index Scan` | using an index — good |
| `Rows Removed by Filter: <big>` | wasted work, needs an index |
| `Sort Method: top-N heapsort` | cheap, only needed a few rows |
| `Sort Method: quicksort` | full sort, more expensive |
| `Execution Time` | the total, at the very bottom |

---

## Observing a database I don't control

I can't `docker logs` production. Options that work there:

**`pg_stat_statements`** — an extension that keeps a running tally of every query
ever run: call count, total time, mean time. Query it like a table, no log access
needed:

```sql
SELECT calls, round(mean_exec_time::numeric,2) AS avg_ms,
       round(total_exec_time::numeric,2) AS total_ms, query
FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 10;
```

Ranks by **total** time, not average — a 5 ms query called 10,000 times costs
more than a 2 s query called once. That's usually the right priority order.

Enabling it needs a restart, which is why it's a maintenance-window job:

```sql
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
-- restart, then:
CREATE EXTENSION pg_stat_statements;
```

Most managed Postgres (RDS, Cloud SQL, Azure) ships with it already on.

**Slow query log** — same setting, thresholded: `log_min_duration_statement =
1000` logs only queries over 1 second. Safe for production.

**APM tools** — Datadog, New Relic, Sentry, Grafana. Web UI, no DB access needed.

**Timing in my own code** — always available, needs nobody's permission:

```python
start = time.perf_counter()
cur.execute(LIST_BOOKMARKS, params)
print(f"list query: {(time.perf_counter()-start)*1000:.1f}ms")
```

---

## To do at work

- [ ] Ask whether `pg_stat_statements` is enabled on our production database.
- [ ] If yes, pull the top 10 by total time and see what's actually there.
- [ ] Find out whether we have an APM tool and whether I have access.

## Next

Add an index on `bookmarks(user_id, created_at)` and re-run both EXPLAIN
ANALYZEs. Expect `Seq Scan` → `Index Scan` and `Rows Removed by Filter` → 0.