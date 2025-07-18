from fastapi import APIRouter, HTTPException
from app.schemas.search import SearchRequest, SearchResult
from typing import List

router = APIRouter()

@router.post("/search", response_model=List[SearchResult])
def search(request: SearchRequest):
    # TODO: Implement real search logic (vector DB, etc.)
    return [
        SearchResult(document_id="doc1", content="Dummy content about history.", score=0.95),
        SearchResult(document_id="doc2", content="Another dummy document.", score=0.90)
    ]
