from datetime import datetime
from pydantic import BaseModel



class BookMarkBase(BaseModel):
    url:str
    title:str
    tags:list[str] = []


class CreateBookMark(BookMarkBase):
    user_id:int


class BookMarkResponse(CreateBookMark):
    id: int
    created_at: datetime

