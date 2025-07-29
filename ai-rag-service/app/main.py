from fastapi import FastAPI
from app.api import search, parse, ai

app = FastAPI(title="AI RAG Service", description="Retrieval-Augmented Generation and AI logic for search, parsing, and answer generation.")

@app.get("/")
async def root():
    return {"message": "AI RAG Service is running!", "docs": "/docs", "endpoints": ["/search", "/parse", "/ai", "/local-books", "/reset-chromadb"]}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/local-books")
async def list_local_books():
    """Debug endpoint to list all local books found in the books directory."""
    try:
        from app.core.local_books import scan_local_books
        books = scan_local_books()
        return {
            "status": "success",
            "total_books": len(books),
            "books": books
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "books": []
        }

@app.delete("/reset-chromadb")
async def reset_chromadb():
    """Reset ChromaDB by deleting all documents."""
    try:
        from app.core.chroma_db import get_or_create_collection
        collection = get_or_create_collection()
        if collection:
            # Get all IDs and delete them
            results = collection.get(include=["metadatas"])
            if results.get("ids"):
                collection.delete(ids=results["ids"])
                return {"status": "success", "message": f"Deleted {len(results['ids'])} documents from ChromaDB"}
            else:
                return {"status": "success", "message": "ChromaDB was already empty"}
        else:
            return {"status": "error", "message": "Could not access ChromaDB collection"}
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Error resetting ChromaDB: {str(e)}"
        }

app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(parse.router, prefix="/parse", tags=["parse"])
app.include_router(ai.router, prefix="/ai", tags=["ai"])
