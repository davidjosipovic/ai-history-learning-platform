#!/usr/bin/env python3
"""
Script to check which books are actually loaded in ChromaDB
"""

from app.core.chroma_db import get_or_create_collection, get_existing_book_ids

def check_chromadb_books():
    """Check what books are actually in ChromaDB"""
    collection = get_or_create_collection()
    
    if collection is None:
        print("ERROR: Could not get ChromaDB collection")
        return
    
    total_docs = collection.count()
    print(f"Total documents in ChromaDB: {total_docs}")
    
    # Get sample of documents to see book distribution
    sample_results = collection.query(
        query_texts=["test"],
        n_results=min(100, total_docs),
        include=['metadatas']
    )
    
    book_counts = {}
    if sample_results.get("metadatas") and sample_results["metadatas"][0]:
        for metadata in sample_results["metadatas"][0]:
            book_id = metadata.get("book_id", "UNKNOWN")
            book_counts[book_id] = book_counts.get(book_id, 0) + 1
    
    print("\nBook distribution in ChromaDB (sample of 100 docs):")
    for book_id, count in sorted(book_counts.items()):
        print(f"  {book_id}: {count} chunks")
    
    # Get all existing book IDs
    print("\nAll book IDs in ChromaDB:")
    existing_ids = get_existing_book_ids()
    for book_id in sorted(existing_ids):
        print(f"  - {book_id}")
    
    print(f"\nTotal unique books: {len(existing_ids)}")

if __name__ == "__main__":
    check_chromadb_books()
