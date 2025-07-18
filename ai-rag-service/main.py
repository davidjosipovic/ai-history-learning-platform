from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import openai
import os
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI(title="AI RAG Service", description="Retrieval-Augmented Generation and AI logic for search, parsing, and answer generation.")

class SearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5

class SearchResult(BaseModel):
    document_id: str
    content: str
    score: float

class ParseRequest(BaseModel):
    text: str

class AIRequest(BaseModel):
    question: str
    context: Optional[str] = None

class AIResponse(BaseModel):
    answer: str
    source_documents: Optional[List[SearchResult]] = None

@app.post("/search", response_model=List[SearchResult])
def search(request: SearchRequest):
    # TODO: Implement real search logic (vector DB, etc.)
    # Dummy results for now
    return [
        SearchResult(document_id="doc1", content="Dummy content about history.", score=0.95),
        SearchResult(document_id="doc2", content="Another dummy document.", score=0.90)
    ]

@app.post("/parse")
def parse(request: ParseRequest):
    # TODO: Implement parsing logic (extract entities, dates, etc.)
    return {"parsed": f"Parsed: {request.text}"}

@app.post("/ai", response_model=AIResponse)
def ai_generate(request: AIRequest):
    prompt = f"Answer the following question using the provided context.\nContext: {request.context}\nQuestion: {request.question}"
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful history assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )
        answer = completion.choices[0].message.content
        return AIResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
