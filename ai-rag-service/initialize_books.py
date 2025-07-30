#!/usr/bin/env python3
"""
Simple script to initialize ChromaDB with all local books.
Run this once to load all books from the books/ directory.
"""

import requests
import json
import sys
import time

BASE_URL = "http://localhost:8000"

def load_all_books():
    """Load all books into ChromaDB."""
    print("🚀 Loading all books into ChromaDB...")
    
    try:
        response = requests.post(f"{BASE_URL}/books/load-all-books")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Success!")
            print(f"📚 Books processed: {result['books_processed']}")
            print(f"📄 Total chunks: {result['total_chunks']}")
            print(f"📖 Processed books: {', '.join(result['processed_books'])}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to AI RAG Service")
        print("Make sure the service is running on http://localhost:8000")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

def check_status():
    """Check the status of books in ChromaDB."""
    print("📊 Checking books status...")
    
    try:
        response = requests.get(f"{BASE_URL}/books/status")
        
        if response.status_code == 200:
            result = response.json()
            print(f"📚 Total local books: {result['total_local_books']}")
            print(f"✅ Books in ChromaDB: {result['books_in_chromadb']}")
            print(f"⏳ Books missing: {result['books_missing']}")
            
            if result['books_missing'] > 0:
                print("\n📋 Missing books:")
                for book in result['books_missing_from_db']:
                    print(f"  - {book['id']}: {book['title']}")
            
            return result['books_missing'] == 0
            
        else:
            print(f"❌ Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_simple_query():
    """Test the new simple AI endpoint."""
    print("🤔 Testing simple AI query...")
    
    test_question = "Tko je bio Nelson Mandela?"
    
    try:
        response = requests.post(
            f"{BASE_URL}/ai-simple/",
            json={"question": test_question}
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Query successful!")
            print(f"📝 Answer: {result['answer'][:200]}...")
            print(f"📚 Sources found: {len(result['sources'])}")
            
            if result['sources']:
                print("\n📖 Sources:")
                for i, source in enumerate(result['sources'][:3]):
                    print(f"  {i+1}. {source['title']}")
        else:
            print(f"❌ Query failed: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Main initialization flow."""
    print("🔧 AI History Learning Platform - Book Initialization")
    print("=" * 60)
    
    # Step 1: Check current status
    all_loaded = check_status()
    
    if all_loaded:
        print("\n✅ All books are already loaded!")
    else:
        print("\n⬇️ Loading missing books...")
        load_all_books()
        
        # Wait a moment and check again
        print("\n⏱️ Waiting for indexing to complete...")
        time.sleep(2)
        check_status()
    
    # Step 2: Test the system
    print("\n🧪 Testing the system...")
    test_simple_query()
    
    print("\n🎉 Initialization complete!")
    print("You can now use the AI service at:")
    print(f"  📖 Simple AI: {BASE_URL}/ai-simple/")
    print(f"  📚 Book management: {BASE_URL}/books/")
    print(f"  📄 API docs: {BASE_URL}/docs")

if __name__ == "__main__":
    main()
