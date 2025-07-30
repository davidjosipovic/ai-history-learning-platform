from pydantic import BaseModel
from typing import Optional

class SearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5

class SearchResult(BaseModel):
    document_id: str
    title: Optional[str] = None
    link: Optional[str] = None
    content: str
    score: float
    source_type: Optional[str] = None  # "local" or "internet_archive"
