# Patch za local books fallback - dodati u ai.py

def check_local_books_exist_in_chromadb():
    """Check which local books already exist in ChromaDB to avoid re-adding them."""
    try:
        from app.core.chroma_db import get_existing_book_ids
        existing_book_ids = get_existing_book_ids()
        
        local_books = scan_local_books()
        local_books_in_db = []
        local_books_missing = []
        
        for book in local_books:
            book_id = book["identifier"]
            if book_id in existing_book_ids:
                local_books_in_db.append(book_id)
            else:
                local_books_missing.append(book)
        
        return {
            "books_in_db": local_books_in_db,
            "books_missing": local_books_missing,
            "has_local_content": len(local_books_in_db) > 0
        }
    except Exception as e:
        print(f"Error checking local books in ChromaDB: {e}")
        return {"books_in_db": [], "books_missing": [], "has_local_content": False}

# Jednostavno rješenje: dodati provjeru prije fallback-a
# U liniji oko 380-390 u ai.py, zamijeniti:

# if answer_is_insufficient and not has_local_sources:

# s:

# local_status = check_local_books_exist_in_chromadb()
# if answer_is_insufficient and not has_local_sources and not local_status["has_local_content"]:
