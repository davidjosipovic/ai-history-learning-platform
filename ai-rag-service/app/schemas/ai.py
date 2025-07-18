from pydantic import BaseModel
from typing import Optional, List
from app.schemas.search import SearchResult

class AIRequest(BaseModel):
    question: str
    context: Optional[str] = None

class AIResponse(BaseModel):
    answer: str
    source_documents: Optional[List[SearchResult]] = None
