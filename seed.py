"""Seed the bookmarker database with realistic volume.

Usage:
    python seed.py            # seed (fails if tables already have data)
    python seed.py --reset    # wipe everything first, then seed
"""

import random
import sys
import time
from datetime import datetime, timedelta, timezone

from db import pool, get_cursor

# --- knobs ---------------------------------------------------------------

N_USERS = 5_000
TARGET_BOOKMARKS = 500_000
DAYS_OF_HISTORY = 730

# --- word pools ----------------------------------------------------------

FIRST = ["arun", "priya", "karthik", "meera", "vikram", "divya", "rahul",
         "anita", "suresh", "lakshmi", "ravi", "kavya"]
LAST = ["kumar", "sharma", "reddy", "nair", "iyer", "gupta", "menon",
        "rao", "pillai", "desai"]

TAGS = ["python", "work", "reading", "recipes", "travel", "rust", "database",
        "design", "news", "tutorial", "video", "reference", "todo", "career",
        "finance", "health", "music", "photography", "science", "history",
        "ai", "security", "linux", "docker", "testing", "frontend",
        "backend", "devops", "writing", "productivity"]

# Deliberately mixes very common and very rare words. After seeding,
# ILIKE '%python%' will match tens of thousands of rows while
# ILIKE '%zeppelin%' matches a handful. That contrast matters in week 2.
COMMON_WORDS = ["guide", "introduction", "notes", "building", "understanding",
                "practical", "modern", "deep", "dive", "python", "postgres",
                "system", "design", "scaling", "advanced", "complete"]
RARE_WORDS = ["zeppelin", "quantum", "obscure", "labyrinth", "kaleidoscope",
              "monolith", "tessellation", "phosphorescent"]

NOW = datetime.now(timezone.utc)


# --- steps ---------------------------------------------------------------

def reset(cur):
    cur.execute("TRUNCATE users, bookmarks, tags, bookmark_tags "
                "RESTART IDENTITY CASCADE")
    print("wiped existing data")


def seed_users(cur):
    rows = [
        (f"user{i}@example.com", f"{random.choice(FIRST)} {random.choice(LAST)}")
        for i in range(N_USERS)
    ]
    cur.executemany("INSERT INTO users (email, name) VALUES (%s, %s)", rows)
    cur.execute("SELECT id FROM users")
    ids = [r["id"] for r in cur.fetchall()]
    print(f"users:          {len(ids):>9,}")
    return ids


def seed_tags(cur):
    ids = []
    for name in TAGS:
        cur.execute("INSERT INTO tags (name) VALUES (%s) RETURNING id", (name,))
        ids.append(cur.fetchone()["id"])
    print(f"tags:           {len(ids):>9,}")
    return ids


def bookmark_counts(user_ids):
    """Uneven distribution: most users are light, a few are very heavy.

    This skew is the point. Week 2's index work depends on some users
    being cheap to query and others expensive.
    """
    counts = {}
    for uid in user_ids:
        r = random.random()
        if r < 0.90:
            counts[uid] = random.randint(10, 60)
        elif r < 0.99:
            counts[uid] = random.randint(200, 1_500)
        else:
            counts[uid] = random.randint(5_000, 15_000)
    return counts


def random_title():
    words = random.choices(COMMON_WORDS, k=random.randint(3, 5))
    if random.random() < 0.001:            # ~1 in 1000 gets a rare word
        words.append(random.choice(RARE_WORDS))
    return " ".join(words).title()


def seed_bookmarks(cur, counts):
    """Bulk load via COPY — one continuous stream instead of N round trips."""
    total = 0
    with cur.copy(
        "COPY bookmarks (user_id, url, title, created_at) FROM STDIN"
    ) as copy:
        for uid, n in counts.items():
            for _ in range(n):
                created = NOW - timedelta(
                    seconds=random.randint(0, DAYS_OF_HISTORY * 86_400)
                )
                copy.write_row((
                    uid,
                    f"https://example.com/{random.randint(1, 10**9)}",
                    random_title(),
                    created,
                ))
                total += 1
    print(f"bookmarks:      {total:>9,}")
    return total


def seed_bookmark_tags(cur, tag_ids):
    """Attach 2-3 random tags to every bookmark.

    Reads the id range rather than pulling 500k ids into memory. Safe here
    because this runs on a freshly seeded table with no gaps.
    """
    cur.execute("SELECT min(id) AS lo, max(id) AS hi FROM bookmarks")
    row = cur.fetchone()
    lo, hi = row["lo"], row["hi"]

    total = 0
    with cur.copy("COPY bookmark_tags (bookmark_id, tag_id) FROM STDIN") as copy:
        for bid in range(lo, hi + 1):
            for tid in random.sample(tag_ids, random.randint(2, 3)):
                copy.write_row((bid, tid))
                total += 1
    print(f"bookmark_tags:  {total:>9,}")


def report(cur):
    print("\nrow counts from the database:")
    for table in ("users", "tags", "bookmarks", "bookmark_tags"):
        cur.execute(f"SELECT count(*) AS n FROM {table}")
        print(f"  {table:<15} {cur.fetchone()['n']:>9,}")


# --- main ----------------------------------------------------------------

def main():
    random.seed(42)                       # reproducible runs
    start = time.time()

    pool.open()
    pool.wait()

    with get_cursor() as cur:
        if "--reset" in sys.argv:
            reset(cur)

        user_ids = seed_users(cur)
        tag_ids = seed_tags(cur)

        counts = bookmark_counts(user_ids)
        print(f"planned:        {sum(counts.values()):>9,} bookmarks")

        seed_bookmarks(cur, counts)
        seed_bookmark_tags(cur, tag_ids)
        report(cur)

    pool.close()
    print(f"\ntotal time: {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()