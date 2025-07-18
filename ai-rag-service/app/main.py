from fastapi import FastAPI
from app.api import search, parse, ai

app = FastAPI(title="AI RAG Service", description="Retrieval-Augmented Generation and AI logic for search, parsing, and answer generation.")

app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(parse.router, prefix="/parse", tags=["parse"])
app.include_router(ai.router, prefix="/ai", tags=["ai"])
