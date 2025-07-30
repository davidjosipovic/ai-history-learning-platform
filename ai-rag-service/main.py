from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import openai
import os
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI(title="AI RAG Service", description="Retrieval-Augmented Generation and AI logic for search, parsing, and answer generation.")

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
