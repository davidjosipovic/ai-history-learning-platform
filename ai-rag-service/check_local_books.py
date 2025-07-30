#!/usr/bin/env python3

from app.core.local_books import scan_local_books

try:
    books = scan_local_books()
    print('Local books found:')
    for book in books:
        print(f'- {book["identifier"]}: {book["title"]}')
except Exception as e:
    print(f"Error: {e}")
