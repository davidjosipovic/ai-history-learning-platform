from fastapi import APIRouter, HTTPException
from app.schemas.ai import AIResponse
from app.core.local_books import scan_local_books, process_local_books_for_chromadb
from app.core.chroma_db import get_existing_book_ids, add_documents_with_embeddings
from app.core.text_chunking import chunk_text, ChunkStrategy, get_optimal_chunk_size
import json

router = APIRouter()

def chunk_book_text(book_id: str, book_title: str, full_text: str):
    """Chunk a single book's text with optimal strategy."""
    print(f"Chunking book: {book_id}")
    
    # Get optimal chunk size for this text
    optimal_size = get_optimal_chunk_size(full_text)
    
    # Use adaptive chunking strategy (instead of SENTENCE_AWARE)
    chunks = chunk_text(
        full_text, 
        chunk_size=optimal_size, 
        strategy=ChunkStrategy.ADAPTIVE,  # Changed from SENTENCE_AWARE
        overlap=200
    )
    
    # Create metadata for each chunk
    metadatas = []
    chunk_ids = []
    
    for i, chunk in enumerate(chunks):
        chunk_id = f"{book_id}_chunk_{i}"
        metadata = {
            "book_id": book_id,
            "title": book_title,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "source_type": "local_file"
        }
        
        metadatas.append(metadata)
        chunk_ids.append(chunk_id)
    
    print(f"Created {len(chunks)} chunks for {book_id}")
    return chunks, metadatas, chunk_ids

@router.post("/load-all-books")
async def load_all_books():
    """
    Load all books from the books/ directory into ChromaDB.
    This should be run once to initialize the database.
    """
    try:
        print("🔍 Scanning local books...")
        local_books = scan_local_books()
        
        if not local_books:
            return {"message": "No local books found", "books_processed": 0}
        
        print("📊 Checking existing books in ChromaDB...")
        existing_book_ids = get_existing_book_ids()
        
        # Filter out books that are already in ChromaDB
        books_to_process = []
        for book in local_books:
            if book["identifier"] not in existing_book_ids:
                books_to_process.append(book)
            else:
                print(f"📖 Book {book['identifier']} already in ChromaDB, skipping")
        
        if not books_to_process:
            return {
                "message": "All books already in ChromaDB", 
                "total_books": len(local_books),
                "books_processed": 0
            }
        
        print(f"📚 Processing {len(books_to_process)} new books...")
        
        # Extract text from all books
        book_texts = process_local_books_for_chromadb()
        
        # Process each book into chunks
        all_chunks = []
        all_metadatas = []
        all_chunk_ids = []
        processed_books = []
        
        for book in books_to_process:
            book_id = book["identifier"]
            book_title = book["title"]
            
            # Get text content
            full_text = book_texts.get(book_id, "")
            
            if not full_text or len(full_text.strip()) < 100:
                print(f"⚠️ Skipping {book_id}: No substantial text content")
                continue
            
            print(f"⚙️ Processing {book_id} - '{book_title}' ({len(full_text)} chars)")
            
            # Chunk the text
            chunks, metadatas, chunk_ids = chunk_book_text(book_id, book_title, full_text)
            
            all_chunks.extend(chunks)
            all_metadatas.extend(metadatas)
            all_chunk_ids.extend(chunk_ids)
            processed_books.append(book_id)
        
        if not all_chunks:
            return {"message": "No text content could be extracted from books", "books_processed": 0}
        
        print(f"💾 Adding {len(all_chunks)} chunks to ChromaDB...")
        add_documents_with_embeddings(all_chunks, all_metadatas, all_chunk_ids)
        
        return {
            "message": f"Successfully processed {len(processed_books)} books",
            "books_processed": len(processed_books),
            "total_chunks": len(all_chunks),
            "processed_books": processed_books
        }
        
    except Exception as e:
        print(f"❌ Error loading books: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load books: {str(e)}")

@router.get("/status")
async def books_status():
    """Get status of books in ChromaDB vs local books."""
    try:
        local_books = scan_local_books()
        existing_book_ids = get_existing_book_ids()
        
        books_in_db = []
        books_missing = []
        
        for book in local_books:
            if book["identifier"] in existing_book_ids:
                books_in_db.append({
                    "id": book["identifier"],
                    "title": book["title"]
                })
            else:
                books_missing.append({
                    "id": book["identifier"], 
                    "title": book["title"]
                })
        
        return {
            "total_local_books": len(local_books),
            "books_in_chromadb": len(books_in_db),
            "books_missing": len(books_missing),
            "books_in_db": books_in_db,
            "books_missing_from_db": books_missing
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@router.delete("/book/{book_id}")
async def delete_book(book_id: str):
    """Delete a specific book from ChromaDB."""
    try:
        from app.core.chroma_db import delete_book_chunks
        deleted_count = delete_book_chunks(book_id)
        
        return {
            "message": f"Deleted {deleted_count} chunks for book {book_id}",
            "deleted_chunks": deleted_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete book: {str(e)}")
