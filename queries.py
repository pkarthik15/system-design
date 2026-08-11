LIST_BOOKMARKS = """
    SELECT id, url, title, created_at, user_id
    FROM bookmarks
    WHERE user_id = %s
    ORDER BY created_at DESC
    LIMIT %s OFFSET %s
"""


LIST_BOOKMARKS_BY_TITLE = """
    SELECT id, url, title, created_at, user_id
    FROM bookmarks
    WHERE user_id = %s
    AND title ILIKE %s 
    ORDER BY created_at DESC
    LIMIT %s OFFSET %s
"""



LIST_BOOKMARKS_TAG = """
    SELECT b.id, b.url, b.title, b.created_at, user_id
    FROM bookmarks b
    JOIN bookmark_tags bt ON bt.bookmark_id = b.id
    JOIN tags t ON t.id = bt.tag_id
    WHERE b.user_id = %s
    AND t.name = %s
    ORDER BY b.created_at DESC
    LIMIT %s OFFSET %s
"""


INSERT_BOOKMARK = """
    INSERT INTO bookmarks (user_id, url, title)
    VALUES (%s, %s, %s)
    RETURNING id, url, title, created_at, user_id
"""

DELETE_BOOKMARK = """
    DELETE FROM bookmarks WHERE id = %s
"""

DELETE_BOOKMARK_TAG = """
    DELETE FROM bookmark_tags WHERE bookmark_id = %s
"""

INSERT_BOOKMARK_TAG = """
    INSERT INTO bookmark_tags (bookmark_id, tag_id)
    VALUES (%s, %s)
    RETURNING bookmark_id, tag_id
"""

TAGS_FOR_BOOKMARK = """
    SELECT t.name
    FROM tags t
    JOIN bookmark_tags bt ON bt.tag_id = t.id
    WHERE bt.bookmark_id = %s
"""

INSERT_TAG = """
    INSERT INTO tags (name)
    VALUES (%s)
    RETURNING id, name
"""

GET_TAG = """
    SELECT id, name
    FROM tags
    WHERE name= %s
"""
