"""
Kratki patch za rješavanje problema duplog dodavanja lokalnih knjiga.

Problem: Sistem ponovno dodaje iste lokalne knjige pri svakom pozivu.

Rješenje: Dodati provjeru postojanja lokalnih knjiga prije procesiranja.
"""

# U ai.py, dodati ovu funkciju:

def get_local_books_not_in_db(existing_book_ids):
    """Get local books that are not yet in ChromaDB."""
    try:
        local_books = scan_local_books()
        books_to_process = []
        
        for book in local_books:
            book_id = book["identifier"]
            if book_id not in existing_book_ids:
                books_to_process.append(book)
            else:
                print(f"Local book {book_id} already exists in ChromaDB, skipping")
        
        return books_to_process
    except Exception as e:
        print(f"Error checking local books: {e}")
        return []

# I zamijeniti u fallback logici oko linije 380:

# Staro:
# local_books = scan_local_books()

# Novo:
# local_books = get_local_books_not_in_db(existing_book_ids)

# Također, varijablu existing_book_ids staviti na početak funkcije da bude dostupna svugdje
