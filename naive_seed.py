import time, random
from db import pool, get_cursor

pool.open(); pool.wait()
with get_cursor() as cur:
    cur.execute("INSERT INTO users (email, name) VALUES ('t@t.com','t') RETURNING id")
    uid = cur.fetchone()["id"]
    start = time.time()
    for i in range(10_000):
        cur.execute(
            "INSERT INTO bookmarks (user_id, url, title) VALUES (%s, %s, %s)",
            (uid, f"https://example.com/{i}", f"title {i}"),
        )
    print(f"10,000 rows in {time.time() - start:.1f}s")
pool.close()