# Day 6 — When indexes don't help (and when they hurt)

**Goal:** find out why the tag join and the `ILIKE` search resisted yesterday's
index, and fix them. Ended up reverting one fix and questioning the other.

---

## Starting point

After Day 5's composite index:

| endpoint | time |
|---|---|
| list p1 heavy | ~1 ms |
| tag python | ~12 ms |
| search python | ~45 ms |

Two endpoints barely moved. Expected two different causes — a missing index on
the join table, and a leading-wildcard problem on the search. Half right.

---

## Finding 1 — performance depends on the *data*, not just the query

Same SQL, different search word:

| query | time | plan |
|---|---|---|
| `title ILIKE '%python%'` | **0.5 ms** | Index Scan, `Rows Removed by Filter: 66` |
| `title ILIKE '%zeppelin%'` | **35.9 ms** | Bitmap Heap Scan, `Rows Removed by Filter: 14882` |

**70× apart.** Why:

- "python" is dense in my seeded titles. Postgres walks
  `idx_bookmarks_user_created` newest-first, tests titles as it goes, hits 20
  matches after 86 rows, and stops. The `LIMIT` rescues it.
- "zeppelin" appears in ~1 in 1000 titles. Only 2 rows in the whole user's set
  match, so `LIMIT 20` can never be satisfied early. Every one of user 2796's
  14,884 bookmarks gets fetched and tested.

The plan shape changed too. With few matches, Postgres knew upfront it needed all
14,884 rows, so it switched from `Index Scan` (walk one at a time) to **`Bitmap
Heap Scan`** — collect all matching row locations first, sort them by physical
position, read the table in disk order. `Heap Blocks: exact=218` — 218 sequential
page reads instead of 14,884 random jumps. Postgres optimising a scan it couldn't
avoid.

**The lesson:** my search endpoint is either 0.5 ms or 36 ms depending on what
the user types. A benchmark testing only common words would have declared it
fine and shipped it. **Test the shape of the data, not a convenient sample.**

This is exactly why the seed script deliberately mixed common and rare words.

---

## Finding 2 — why a B-tree cannot help `ILIKE '%x%'`

A B-tree stores whole values in **sorted order** — like a phone book. Great for
"starts with python" (a seek). Useless for "contains python anywhere", because
there's no starting point to seek to.

Note the plan wording: `Filter: (title ~~* '%python%')`, not `Index Cond`. Filter
= fetch the row, then test it. That's row-by-row work no B-tree can remove.

### The fix: trigram + GIN

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_bookmarks_title_trgm ON bookmarks USING gin (title gin_trgm_ops);
```

**Trigrams** chop each title into overlapping 3-character fragments:

```
"Python Guide" → pyt, yth, tho, hon, gui, uid, ide, ...
```

**GIN = Generalized Inverted Index.** A normal index maps row → contents. An
inverted index flips it: content → rows. Like a textbook index — one entry per
word, listing every page it appears on.

```
pyt → rows 47, 103, 892, 1544, ...
yth → rows 47, 103, 892, 1544, ...
```

So "contains python" becomes "break the search term into trigrams, look each one
up, intersect the row lists." Works for a match *anywhere* in the string, because
you never asked about the beginning.

GIN is also what backs full-text search, JSONB indexing, and array columns. Common
thread: a column holding **many things** rather than one value.

### Result

**35.9 ms → 14.6 ms**

```
Bitmap Index Scan on idx_bookmarks_title_trgm
  Index Cond: (title ~~* '%zeppelin%')    ← now an indexed lookup
Rows Removed by Filter: 140                ← was 14,882
```

`Recheck Cond` and `Filter` swapped places. The trigram index found the 142 rows
in the *whole table* containing "zeppelin", then discarded the 140 belonging to
other users.

### The cost

Index size on `bookmarks`: **50 MB → 82 MB (+64%)**.

One title produces ~12 trigrams, so the index has far more entries than the table
has rows. Writes get slower too — every insert updates a dozen index entries
instead of one.

**Stated as a trade:** search on rare terms went from 36 ms to 15 ms, costing
32 MB on a 111 MB table plus slower writes on every save. Worth it only if rare
searches are frequent relative to writes.

**Honest verdict: probably a net loss on a real product.** 21 ms saved on an
uncommon query, paid for on every single insert forever. Also worth noting the
whole thing optimises for user 2796 — an outlier with 14,884 bookmarks. Most
users have 10–60, where scanning takes microseconds.

Kept it anyway, to observe the write cost under load in Week 3.

### Why it's still 14.6 ms for 2 rows

**Postgres can only use one index per scan here.** It picked the trigram index
and abandoned `user_id`, so it fetched 142 rows to keep 2. Either way one of the
two filters happens the slow way. A composite GIN (via `btree_gin`) covering both
columns would beat either alone.

---

## Finding 3 — the index that made things 30× worse

Diagnosis looked clean. `bookmark_tags` has one index: the composite PK
`(bookmark_id, tag_id)`. By the leftmost-prefix rule that answers "which tags
does bookmark X have?" but never "which bookmarks have tag Y?"

So I added the reverse:

```sql
CREATE INDEX idx_bookmark_tags_tag_bookmark ON bookmark_tags (tag_id, bookmark_id);
```

**Result: 24 ms → 743 ms.**

```
Index Only Scan using idx_bookmark_tags_tag_bookmark
  Index Cond: (tag_id = t.id)
  rows=81107                          ← every bookmark tagged python, all users

-> Index Scan using bookmarks_pkey
     Filter: (user_id = 2796)
     Rows Removed by Filter: 1
     loops=81107                      ← 81,107 separate lookups
```

The planner saw the new index and changed strategy: start from the tag, pull all
81,107 bookmarks tagged "python" across all 5,000 users, then look up each one to
check ownership. 81,107 lookups → 1,227 survivors → 20 wanted.

**The old plan was smarter.** Walk user 2796's bookmarks newest-first via
`idx_bookmarks_user_created`, check each one's tags, stop at 20 matches. Only 270
candidates examined. The `LIMIT 20` makes early termination possible, and the
composite index already delivers the right order — so no sort either.

**Why the planner chose wrong:** it estimated `rows=73` from the join and got
1,227. Bad estimate → bad plan. It assumed starting from the tag would be cheap;
"python" is on 16% of all bookmarks, so it wasn't.

Dropped it. Back to 24 ms.

### The lesson

**An index is an option you hand the planner, not an improvement you make.**

The planner picks based on statistics. When estimates are off, a new index can
push it toward a *worse* plan. This is a real production incident pattern:
someone adds an index to help query A, and unrelated query B collapses.

**So: measure before and after, on every query the index touches — not just the
one you meant to fix.**

### And sometimes the answer is no index

The tag query at 24 ms is fine. Its original plan is well-matched to `LIMIT 20`.
It doesn't need an index — it needs to be left alone.

---

## Also learned

**The first run after a schema change is meaningless.** Dropping the index
invalidated cached pages, so the next run read from disk: 52 ms instead of 24 ms,
with an identical plan. Always take the second or third measurement.

**Planning time is not free.** The tag join spent 6.5 ms planning out of 24 ms
total — a quarter of the query. Complex joins cost real planning time, which is
where prepared statements start to earn their keep.

**`Index Only Scan` + `Heap Fetches: 0`** means Postgres never touched the table
at all — every column it needed was in the index. That's a covering index.

---

## Scorecard

| change | result | verdict |
|---|---|---|
| trigram GIN on `title` | 35.9 → 14.6 ms on rare terms | works; 32 MB + slower writes. Marginal. |
| `(tag_id, bookmark_id)` on `bookmark_tags` | 24 → 743 ms | **harmful, reverted** |
| leaving the tag query alone | 24 ms | correct |

One win out of three, and the most valuable finding was that an index shouldn't
exist.

## To do at work

- [ ] Check whether any of our search features use `LIKE '%...%'` — and whether
      anyone has tested them with a rare search term.
- [ ] Ask whether we've ever had a query regress after an index was added.

## Next

Week 3: load testing. curl's 260 ms floor is now louder than the queries — need a
real instrument (k6). Predictions to test: the connection pool at `max_size=10`
becomes the ceiling, and the trigram index's write cost becomes visible under
insert load.