#!/usr/bin/env python3
"""
Test script for Internet Archive full text downloading and RAG processing.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.core.internet_archive_downloader import InternetArchiveDownloader
from app.core.text_chunking import chunk_text
from app.core.chroma_db import add_documents_with_embeddings, query_similar_documents

def test_full_text_processing():
    """Test downloading and processing full text from Internet Archive."""
    
    print("=== Testing Internet Archive Full Text Download ===\n")
    
    # Initialize downloader
    downloader = InternetArchiveDownloader()
    
    # Test with NDH-related books
    test_books = [
        "35-mucenika-hrvatske-vojske-ndh",
        "genocideincroatia19411945_201907"
    ]
    
    for book_id in test_books:
        print(f"\n--- Processing: {book_id} ---")
        
        # Get available files
        files = downloader.get_item_files(book_id)
        print(f"Available files: {len(files)}")
        for file_info in files:
            print(f"  - {file_info['name']} ({file_info['format']}, {file_info['size']} bytes)")
        
        # Download and extract text
        full_text = downloader.download_and_extract_text(book_id, max_files=1)
        
        if full_text:
            print(f"\nExtracted text length: {len(full_text)} characters")
            print(f"Text preview:\n{full_text[:500]}...")
            
            # Test chunking
            chunks = chunk_text(full_text)
            print(f"Generated chunks: {len(chunks)}")
            
            if chunks:
                print(f"First chunk preview:\n{chunks[0][:200]}...")
        else:
            print("No text extracted")
    
    print("\n=== Test completed ===")

if __name__ == "__main__":
    test_full_text_processing()
