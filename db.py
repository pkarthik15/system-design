import os
from contextlib import contextmanager

from psycopg_pool import ConnectionPool
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "bookmarker")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

CONNINFO = make_conninfo(
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
)

# --- pool ----------------------------------------------------------------
# max_size is deliberately small. In week 3 you will exhaust this under load
# and watch requests queue with no errors and no crash — just latency.

pool = ConnectionPool(
    conninfo=CONNINFO,
    min_size=2,
    max_size=10,
    open=False,                              # opened on app startup
    kwargs={"row_factory": dict_row},        # rows come back as dicts
)


# --- helpers -------------------------------------------------------------

@contextmanager
def get_cursor():
    """Borrow a connection, yield a cursor, commit on clean exit.

    Use this directly when you need several queries on ONE connection —
    which is what you want when you deliberately build the N+1 in week 1.
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            yield cur


def query_all(sql: str, params: tuple = ()) -> list[dict]:
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def query_one(sql: str, params: tuple = ()) -> dict | None:
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql: str, params: tuple = ()) -> int:
    """Run a write. Returns rows affected."""
    with get_cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


# --- smoke test ----------------------------------------------------------
# if __name__ == "__main__":
#     pool.open()
#     pool.wait()
#     print(query_one("SELECT 1 AS ok, version() AS pg"))
#     pool.close()

if __name__ == "__main__":
    pool.open(); pool.wait()
    print(pool.get_stats())          # note pool_available
    with get_cursor() as cur:
        cur.execute("SELECT 1")
        print("inside:", pool.get_stats())
    print("after:", pool.get_stats())
    pool.close()