# Day 5 — Indexes

**Goal:** fix the sequential scan found on Day 4, and learn what an index costs.

---

## The problem

Day 4's plan showed the whole story:

```
Parallel Seq Scan on bookmarks
  Filter: (user_id = 2796)
  Rows Removed by Filter: 320081
```

500,000 rows read to return 20. Postgres had no choice — rows sit on disk in
write order, so user 2796's bookmarks are scattered throughout the table.
Without help, "find user 2796" genuinely means "look at everything."

An index is a second structure holding the indexed column values in **sorted
order**, each pointing at where its row lives. Same idea as the index at the back
of a textbook: without it, finding "photosynthesis" means reading 400 pages; with
it, you look up a sorted list and jump to page 213.

---

## Step 1 — the obvious index

```sql
CREATE INDEX idx_bookmarks_user_id ON bookmarks (user_id);
```

Result: **29.2 ms → 7.9 ms** (3.7× faster)

```
Sort  (actual time=6.496..7.546 rows=10000)
  Sort Key: created_at DESC
  Sort Method: quicksort  Memory: 2363kB
  -> Index Scan using idx_bookmarks_user_id  (actual time=0.204..2.559 rows=14884)
       Index Cond: (user_id = 2796)
```

What changed:
- `Seq Scan` → `Index Scan`
- `Rows Removed by Filter: 320081` → gone
- `Filter:` → `Index Cond:` — this wording matters. **Filter** = read the row,
  then check it. **Index Cond** = only fetch rows that already match.
- Parallel workers gone — no huge scan left to parallelise
- Scan step: 20 ms → 2.5 ms

## Step 2 — but the sort is now the bottleneck

The `Sort` node is 5 ms of the remaining 7.9 ms (63%). It was invisible before
because the scan drowned it out.

**Fixing the biggest bottleneck promotes the second one.** Performance work is
iterative — which is also why you re-measure after every single change instead of
applying three fixes at once.

Why the sort was still needed: the index sorts by `user_id` only. Within user
2796's 14,884 entries, `created_at` is in arbitrary order. Postgres had the right
rows but the wrong order, so it had to sort all 14,884 to find the newest 20.

## Step 3 — the composite index

```sql
CREATE INDEX idx_bookmarks_user_created ON bookmarks (user_id, created_at DESC);
```

Result: **29.2 ms → 0.382 ms — 76× faster than the baseline.**

```
Limit  (actual time=0.310..0.344 rows=20 loops=1)
  -> Index Scan using idx_bookmarks_user_created  (actual time=0.309..0.341 rows=20)
       Index Cond: (user_id = 2796)
Execution Time: 0.382 ms
```

Two lines. No Sort, no Gather Merge, no workers. The index stores user 2796's
entries already newest-first, so Postgres walks it, takes 20, and stops.

**`rows=20`** — not 14,884, not 500,000. The work became proportional to the
*answer*, not to the table. That's the whole point of a matched index.

(The cost estimate reads `0.42..18155.24` — the high end is walking all 15,440
entries. The `Limit` meant Postgres knew it could stop early, so it only paid the
low end. Alarming estimate, trivial actual.)

---

## The offset trap

With `OFFSET 9980`, Postgres **ignored** the composite index and went back to the
single-column index plus a sort. Not a bug — with a deep offset it must produce
10,000 rows regardless, so the sorted index loses most of its value.

**An index helps a query shape, not a table.** The same index that makes page 1
nearly free does almost nothing for page 500. Fixing deep pagination needs
keyset pagination instead — `WHERE created_at < <last seen value>` — which lets
the index work at any depth.

---

## The leftmost-prefix rule

Dropped the single-column index as redundant:

```sql
DROP INDEX idx_bookmarks_user_id;
```

An index on `(A, B)` serves queries on **A**, and on **A and B**.
It does **not** serve queries on **B alone**.

Like a phone book sorted by surname then first name: great for finding "Kumar",
useless for finding everyone named "Priya".

So `(user_id, created_at)` already covers everything `(user_id)` did. Keeping
both would cost disk and slow every write for zero benefit.

---

## What it cost

**Disk:** 50 MB of index against a 111 MB table — **~45% overhead**.

**Writes:** tried to measure with `EXPLAIN ANALYZE INSERT` and found something
else instead:

```
Trigger for constraint bookmarks_user_id_fkey: time=2.692 calls=1
Execution Time: 6.001 ms
```

The **foreign key check costs 2.7 ms** — nearly half the insert. Every insert
verifies the user exists in `users` before allowing the row. The index update is
folded into the Insert node and isn't broken out, so this measurement can't
isolate it.

Foreign keys are a correctness guarantee paid for on every write. Some
high-write systems drop them and enforce integrity in application code — a real
trade-off with real risk. Worth knowing the option exists.

To isolate index write cost properly: insert 10k rows, drop the index, insert
10k more, compare.

---

## Endpoint results

`bench.ps1`, curl's ~260 ms floor subtracted:

| endpoint | before | after |
|---|---|---|
| list p1 heavy | ~30 ms | **~1 ms** |
| list p1 light | ~17 ms | **~0 ms** |
| list p500 heavy | ~29 ms | **~0 ms** |
| tag python | ~67 ms | **~12 ms** |
| search python | ~136 ms | **~45 ms** |
| search zeppelin | ~123 ms | **~7 ms** |

**Everything improved, including queries I didn't index.** Tag filter and search
both start from `WHERE b.user_id = %s`, so they now begin from 14,884 rows
instead of 500,000. The join and the `ILIKE` are unchanged — they just have far
less to chew on.

**`search zeppelin` (~7 ms) vs `search python` (~45 ms)** — same query shape,
same rows scanned, 6× apart. That gap isn't the database. "python" matches
thousands of titles that get fetched, built into Pydantic models, and
JSON-encoded. At sub-millisecond query times, **I'm now measuring my own Python
code**, not Postgres. Further SQL tuning buys almost nothing on these endpoints.

**Precision caveat:** several results are within noise of the 260 ms curl floor.
"~0 ms" means "too fast for this instrument." Need a better tool — that's what
week 3's load testing is for.

---

## Things to remember

- `CREATE INDEX` **locks the table against writes** while building. Seconds on
  500k rows, minutes on 200M — i.e. an outage. Production-safe version is
  `CREATE INDEX CONCURRENTLY` (slower, no lock).
- If Postgres ignores a new index, run `ANALYZE <table>;` — the planner works off
  collected statistics, and stale stats causing bad plans is a common production
  problem.
- Naming: `idx_<table>_<columns>`. Not enforced, but necessary once there are
  fifteen of them.
- Check what exists: `SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'x';`

## To do at work

- [ ] Find our slowest endpoint's query and run `EXPLAIN ANALYZE` on it.
- [ ] Check whether our biggest tables have indexes matching their common `WHERE`
      clauses, or just primary keys.

## Next

`tag=python` (~12 ms) and `search=python` (~45 ms) are the remaining slow paths.
`EXPLAIN ANALYZE` both. Expect to find `bookmark_tags` has no index on `tag_id`,
and that `ILIKE '%...%'` fundamentally cannot use a B-tree — two different
problems needing two different fixes, one of which needs an index type I haven't
met yet.