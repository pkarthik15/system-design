import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from db import pool, query_all, query_one, execute, get_cursor
from queries import INSERT_BOOKMARK, INSERT_TAG, GET_TAG, INSERT_BOOKMARK_TAG, LIST_BOOKMARKS, LIST_BOOKMARKS_TAG, LIST_BOOKMARKS_BY_TITLE, DELETE_BOOKMARK_TAG, DELETE_BOOKMARK, TAGS_FOR_BOOKMARK
from models import CreateBookMark, BookMarkResponse
from psycopg import Cursor



QUERY_PAGE_LIMIT = int(os.getenv("QUERY_PAGE_LIMIT", "20"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()
    pool.wait()
    print("DB Connection Successful")      # fail fast at boot if Postgres is unreachable
    yield
    pool.close()
    print("DB Connection Closed") 


app = FastAPI(lifespan=lifespan)


def get_tag_details_by_name(cursor:Cursor, tag:str):
    cursor.execute(GET_TAG, (tag.lower(),))
    response = cursor.fetchone()
    return response


def add_tag_to_bookmark(cursor:Cursor, bookmark_id:int, tag_id:int):
    cursor.execute(INSERT_BOOKMARK_TAG, (bookmark_id, tag_id))
    response = cursor.fetchone()
    return response


def add_tag(cursor:Cursor, tag:str):
    cursor.execute(INSERT_TAG, (tag.lower(), ))
    response = cursor.fetchone()
    return response


@app.post("/bookmarks")
def create_book_mark(bookmark_request:CreateBookMark):
    try:
        with get_cursor() as cur:
            cur.execute(INSERT_BOOKMARK, (bookmark_request.user_id, bookmark_request.url, bookmark_request.title, ))
            response = cur.fetchone()
            for tag in bookmark_request.tags:
                tag_detail = get_tag_details_by_name(cur, tag)
                if tag_detail is not None:
                    bookmark_tag_response = add_tag_to_bookmark(cur, response["id"], tag_detail["id"])
                else:
                    add_tag_response = add_tag(cur, tag)
                    bookmark_tag_response = add_tag_to_bookmark(cur, response["id"], add_tag_response["id"])
        return JSONResponse(
            status_code=200,
            content= jsonable_encoder({"status": "success", "message": f"", "data": BookMarkResponse(
                    id=response["id"],
                    user_id= response["user_id"],
                    url = response["url"],
                    title = response["title"],
                    tags=bookmark_request.tags,
                    created_at=response["created_at"],
                )
            })
        )
    except Exception as e:
        print(str(e))
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Internal server error"}
        )


@app.get("/bookmarks")
def get_bookmarks(user_id:int, page:int = Query(1, ge=1), tag:str|None = None,):
    try:
        response_out = []
        OFFSET = (page - 1) * QUERY_PAGE_LIMIT
        with get_cursor() as cur:
            if tag is not None:
                cur.execute(LIST_BOOKMARKS_TAG, (user_id, tag.lower(), QUERY_PAGE_LIMIT, OFFSET))
            else:
                cur.execute(LIST_BOOKMARKS, (user_id, QUERY_PAGE_LIMIT, OFFSET))
            response = cur.fetchall()
            
            for bookmark in response:
                cur.execute(TAGS_FOR_BOOKMARK, (bookmark["id"], ))
                tag_response = cur.fetchall()
                tags = [r["name"] for r in tag_response]
                response_out.append(BookMarkResponse(
                    id=bookmark["id"],
                    user_id= bookmark["user_id"],
                    url = bookmark["url"],
                    title = bookmark["title"],
                    created_at = bookmark["created_at"],
                    tags=tags,
                ))
        return JSONResponse(
                    status_code=200,
                    content= jsonable_encoder({
                        "status": "success",
                        "message": "",
                        "page": page,
                        "data": response_out,
                    })
                )
    except Exception as e:
        print(str(e))
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Internal server error"}
        )


@app.get("/bookmarks/search")
def search_bookmarks_by_title(user_id:int, q:str, page:int = Query(1, ge=1),):
    try:
        response_out = []
        OFFSET = (page - 1) * QUERY_PAGE_LIMIT
        with get_cursor() as cur:
            cur.execute(LIST_BOOKMARKS_BY_TITLE, (user_id, f"%{q}%", QUERY_PAGE_LIMIT, OFFSET))
            response = cur.fetchall()
            
            for bookmark in response:
                cur.execute(TAGS_FOR_BOOKMARK, (bookmark["id"], ))
                tag_response = cur.fetchall()
                tags = [r["name"] for r in tag_response]
                response_out.append(BookMarkResponse(
                    id=bookmark["id"],
                    user_id= bookmark["user_id"],
                    url = bookmark["url"],
                    title = bookmark["title"],
                    created_at = bookmark["created_at"],
                    tags=tags,
                ))
        return JSONResponse(
                    status_code=200,
                    content= jsonable_encoder({
                        "status": "success",
                        "message": "",
                        "page": page,
                        "data": response_out,
                    })
                )
    except Exception as e:
        print(str(e))
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Internal server error"}
        )



@app.delete("/bookmarks/{id}")
def delete_bookmark(id:int):
    try:
        response = execute(DELETE_BOOKMARK, (id, ))
        return JSONResponse(
            status_code=200,
            content={"status": "success", "message": f"Bookmark deleted successfully!"}
        )
    except Exception as e:
        print(str(e))
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Internal server error"}
        )