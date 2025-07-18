
from fastapi import APIRouter, HTTPException
from app.schemas.ai import AIRequest, AIResponse
import openai
import os
from dotenv import load_dotenv

from app.core.internet_archive import search_internet_archive_metadata
from app.core.text_chunking import chunk_text
from app.core.chroma_db import add_documents_with_embeddings, query_similar_documents

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
 
router = APIRouter()

@router.post("/", response_model=AIResponse)
def ai_generate(request: AIRequest):
    # 1. Search Internet Archive for relevant books
    try:
        books = search_internet_archive_metadata(request.question, rows=1)
    except Exception as e:
        books = []

    if not books:
        return AIResponse(answer="Nije pronađena nijedna relevantna knjiga.")

    # 2. Use the first book's description as the text to chunk and embed
    book = books[0]
    book_id = book.get("identifier", "")
    book_title = book.get("title", "N/A")
    book_desc = book.get("description", "")
    if not book_desc:
        return AIResponse(answer="Nema dostupnog opisa za pronađenu knjigu.")

    # 3. Chunk the description
    chunks = chunk_text(book_desc)
    chunk_ids = [f"{book_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"book_id": book_id, "title": book_title, "chunk_index": i} for i in range(len(chunks))]

    # 4. Add to ChromaDB (idempotent: ChromaDB will skip duplicates)
    add_documents_with_embeddings(chunks, metadatas, chunk_ids)

    # 5. Query ChromaDB for the most similar chunk to the user's question
    results = query_similar_documents(request.question, n_results=1)
    if not results["documents"] or not results["documents"][0]:
        return AIResponse(answer="Nije pronađen relevantan odlomak u knjizi.")
    best_chunk = results["documents"][0][0]

    # 6. Pass the best chunk to OpenAI for answer refinement
    prompt = f"Korisničko pitanje: {request.question}\nRelevantni odlomak iz knjige: {best_chunk}\n\nOdgovori na pitanje koristeći samo informacije iz odlomka."
    try:
        response = openai.responses.create(
            model="gpt-4.1-nano",
            input=[
                {"role": "system", "content": "Ti si povijesni asistent. Odgovaraj samo na temelju dostavljenog odlomka."},
                {"role": "user", "content": prompt}
            ]
        )
        answer = response.output_text
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return AIResponse(
        answer=answer,
        source_documents=[
            {
                "document_id": book_id,
                "content": best_chunk,
                "score": 1.0
            }
        ]
    )
