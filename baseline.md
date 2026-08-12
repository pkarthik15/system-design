# Baseline — 12 Aug 2026
Before any indexes. All numbers from a fresh seed (random.seed(42)).

## Setup
- 5,000 users / 500k bookmarks / ~1.25M bookmark_tags
- heavy user: 2796 (14,884 bookmarks)
- light user: 50 (10 bookmarks)
- bookmarks table: 132 MB
- bookmark_tags: 177 MB (103 MB heap + 73 MB index)
- seed time: 57.7s via COPY (~7 min projected for naive inserts)

## Method
PowerShell `Measure-Command` around `curl.exe`, median of 5 after one warmup.
curl.exe on Windows costs ~260ms per invocation — measured against
/docs (no DB work) and subtracted from every result below.

## Endpoint timings
| endpoint | measured | minus overhead |
|---|---|---|
| list p1, light user | 277 ms | ~17 ms |
| list p500, heavy user | 289 ms | ~29 ms |
| list p1, heavy user | 290 ms | ~30 ms |
| tag=python, heavy user | 327 ms | ~67 ms |
| search q=zeppelin, heavy | 383 ms | ~123 ms |
| search q=python, heavy | 396 ms | ~136 ms |

## Observations
- Tag filter ~4x the plain list. Search ~8x. Both are join or scan heavy.
- page=500 barely slower than page=1 — unexpected, needs explaining.
- Every endpoint issues 21 queries (1 list + 20 tag lookups). Unverified.