"""
Refactored AI API - broken into smaller, manageable functions
"""
from fastapi import APIRouter, HTTPException
from app.schemas.ai import AIRequest, AIResponse
import openai
import os
from dotenv import load_dotenv

# Imports
from app.core.internet_archive import (
    generate_keywords_from_question,
    build_internet_archive_query_string,
    search_internet_archive_advanced
)
from app.core.internet_archive_downloader import InternetArchiveDownloader
from app.core.text_chunking import chunk_text, ChunkStrategy, analyze_chunking_quality, get_optimal_chunk_size
from app.core.chroma_db import (
    add_documents_with_embeddings, 
    query_similar_documents, 
    query_with_multiple_strategies, 
    get_existing_book_ids,
    delete_book_chunks
)
from app.core.local_books import scan_local_books, process_local_books_for_chromadb

# Initialize
load_dotenv()
try:
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception as e:
    print(f"ERROR: Could not initialize OpenAI client: {e}")
    client = None

router = APIRouter()

# ========================================
# HELPER FUNCTIONS (each under 50 lines)
# ========================================

def detect_people_in_question(question: str):
    """Extract people names from the question using multiple methods."""
    import re
    
    people_found = []
    question_lower = question.lower()
    
    # Known historical figures (expand this list as needed)
    known_people = {
        'barack obama': ['barack obama', 'obama'],
        'donald trump': ['donald trump', 'trump'], 
        'vladimir putin': ['vladimir putin', 'putin'],
        'winston churchill': ['winston churchill', 'churchill'],
        'napoleon bonaparte': ['napoleon', 'bonaparte'],
        'adolf hitler': ['hitler', 'adolf hitler'],
        'joseph stalin': ['stalin', 'joseph stalin'],
        'abraham lincoln': ['lincoln', 'abraham lincoln'],
        'george washington': ['washington', 'george washington'],
        'franklin roosevelt': ['roosevelt', 'franklin roosevelt', 'fdr'],
        'john kennedy': ['kennedy', 'john kennedy', 'jfk'],
        'bill clinton': ['clinton', 'bill clinton'],
        'joe biden': ['biden', 'joe biden'],
        'george bush': ['bush', 'george bush'],
        'nelson mandela': ['nelson mandela', 'mandela'],
        'martin luther king': ['martin luther king', 'mlk', 'king'],
        'malcolm x': ['malcolm x', 'malcolm'],
        'gandhi': ['gandhi', 'mahatma gandhi'],
        'ante pavelić': ['ante pavelić', 'pavelić', 'pavelic'],
        'josip broz tito': ['tito', 'josip broz', 'broz'],
        'franjo tuđman': ['tuđman', 'tudman', 'franjo tuđman'],
        'stipe mesić': ['mesić', 'mesic', 'stipe mesić'],
        'zoran milanović': ['milanović', 'milanovic', 'zoran milanović']
    }
    
    # Check for known people
    for full_name, variations in known_people.items():
        if any(var in question_lower for var in variations):
            people_found.append(full_name)
    
    # Pattern for capitalized names (First Last format)
    name_pattern = r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b'
    potential_names = re.findall(name_pattern, question)
    
    # Add names that look like person names
    for name in potential_names:
        name_lower = name.lower()
        if name_lower not in [p.lower() for p in people_found]:
            # Basic heuristic: avoid common words that might be capitalized
            common_words = ['World War', 'New York', 'United States', 'Roman Empire', 'Soviet Union']
            if not any(common in name for common in common_words):
                people_found.append(name_lower)
    
    return people_found

def detect_historical_events_in_question(question: str):
    """Detect specific historical events, wars, and conflicts in the question."""
    question_lower = question.lower()
    detected_events = []
    
    # Known historical events and conflicts
    historical_events = {
        'domovinski rat': ['domovinski rat', 'croatian war of independence', 'homeland war'],
        'drugi svjetski rat': ['drugi svjetski rat', 'world war ii', 'ww2', 'wwii'],
        'prvi svjetski rat': ['prvi svjetski rat', 'world war i', 'ww1', 'wwi'],
        'jugoslavenski ratovi': ['jugoslavenski ratovi', 'yugoslav wars', 'balkan wars'],
        'ndh': ['ndh', 'nezavisna država hrvatska', 'independent state of croatia'],
        'raspad jugoslavije': ['raspad jugoslavije', 'breakup of yugoslavia', 'yugoslav dissolution'],
        'srebrenica': ['srebrenica', 'genocide srebrenica'],
        'oluja': ['operacija oluja', 'operation storm'],
        'bljesak': ['operacija bljesak', 'operation flash'],
        'vukovar': ['vukovar', 'battle of vukovar'],
        'dubrovnik': ['opsada dubrovnika', 'siege of dubrovnik']
    }
    
    for event_name, variations in historical_events.items():
        if any(var in question_lower for var in variations):
            detected_events.append(event_name)
    
    return detected_events

def find_books_for_people(local_books: list, people_names: list):
    """Find local books relevant to the detected people."""
    relevant_books = []
    
    for book in local_books:
        book_title = book.get('title', '').lower()
        book_author = book.get('creator', '').lower() if book.get('creator') else ''
        book_description = book.get('description', '').lower() if book.get('description') else ''
        
        # Check if any person name appears in title, author, or description
        for person in people_names:
            person_parts = person.split()
            
            # Check for full name or parts of name
            if (person in book_title or 
                person in book_author or 
                person in book_description or
                any(part in book_title for part in person_parts if len(part) > 3)):
                
                if book not in relevant_books:
                    relevant_books.append(book)
                    print(f"  Found relevant book for '{person}': {book['title']}")
                break
    
    return relevant_books

def find_books_for_events(local_books: list, events: list):
    """Find local books relevant to specific historical events."""
    relevant_books = []
    
    # Event keywords mapping
    event_keywords = {
        'domovinski rat': ['domovinski', 'homeland', 'war', 'independence', 'croatia', 'tuđman', 'vukovar', 'dubrovnik'],
        'drugi svjetski rat': ['world war', 'wwii', 'ww2', 'nazi', 'hitler', 'holocaust'],
        'prvi svjetski rat': ['world war', 'wwi', 'ww1', 'great war'],
        'jugoslavenski ratovi': ['yugoslav', 'balkan', 'bosnia', 'serbia', 'kosovo'],
        'ndh': ['ndh', 'nezavisna', 'država', 'hrvatska', 'ustaše', 'pavelić'],
        'raspad jugoslavije': ['yugoslavia', 'breakup', 'dissolution', 'tito'],
        'srebrenica': ['srebrenica', 'genocide', 'bosnia'],
        'oluja': ['storm', 'oluja', 'krajina'],
        'bljesak': ['flash', 'bljesak', 'western slavonia'],
        'vukovar': ['vukovar', 'battle'],
        'dubrovnik': ['dubrovnik', 'siege']
    }
    
    for book in local_books:
        book_title = book.get('title', '').lower()
        book_author = book.get('creator', '').lower() if book.get('creator') else ''
        book_description = book.get('description', '').lower() if book.get('description') else ''
        combined_text = f"{book_title} {book_author} {book_description}"
        
        # Check if any event keywords appear in the book metadata
        for event in events:
            if event in event_keywords:
                keywords = event_keywords[event]
                if any(keyword in combined_text for keyword in keywords):
                    if book not in relevant_books:
                        relevant_books.append(book)
                        print(f"  Found relevant book for '{event}': {book['title']}")
                    break
    
    return relevant_books

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

def generate_search_keywords(question: str):
    """Generate keywords from user question."""
    try:
        keywords = generate_keywords_from_question(question)
        if not keywords or keywords == [question]:
            print("LLM failed to generate specific keywords, falling back to original question.")
            keywords = [question]
        
        archive_query_string = build_internet_archive_query_string(keywords)
        print(f"Generated Internet Archive query: {archive_query_string}")
        return keywords, archive_query_string
        
    except Exception as e:
        print(f"Error generating search keywords: {e}")
        archive_query_string = build_internet_archive_query_string([question])
        return [question], archive_query_string

def search_for_books(archive_query_string: str, existing_book_ids: set, question: str = ""):
    """Search Internet Archive and fallback to local books if needed."""
    books = []
    
    # Detect people and historical events in the question
    detected_people = detect_people_in_question(question)
    detected_events = detect_historical_events_in_question(question)
    
    if detected_people or detected_events:
        if detected_people:
            print(f"Detected people in question: {detected_people}")
        if detected_events:
            print(f"Detected historical events in question: {detected_events}")
        
        print("Checking for relevant local books...")
        try:
            local_books = scan_local_books()
            relevant_books = []
            
            # Find books for people
            if detected_people:
                people_books = find_books_for_people(local_books, detected_people)
                relevant_books.extend(people_books)
            
            # Find books for events
            if detected_events:
                event_books = find_books_for_events(local_books, detected_events)
                relevant_books.extend(event_books)
            
            # Remove duplicates
            unique_relevant_books = []
            seen_ids = set()
            for book in relevant_books:
                if book['identifier'] not in seen_ids:
                    unique_relevant_books.append(book)
                    seen_ids.add(book['identifier'])
            
            if unique_relevant_books:
                print(f"Found {len(unique_relevant_books)} relevant local books: {[book['title'] for book in unique_relevant_books]}")
                # Return relevant books directly if they're not in DB yet
                new_relevant_books = [book for book in unique_relevant_books if book['identifier'] not in existing_book_ids]
                if new_relevant_books:
                    print(f"Using {len(new_relevant_books)} new relevant books for processing")
                    return new_relevant_books
        except Exception as e:
            print(f"Error checking for relevant books: {e}")
    
    # Try Internet Archive first
    try:
        books = search_internet_archive_advanced(archive_query_string, rows=5)
        print(f"Found {len(books)} books from Internet Archive.")
    except Exception as e:
        print(f"Error searching Internet Archive: {e}")
    
    # Fallback to local books if no results
    if not books:
        print("No books found from Internet Archive. Checking local books...")
        try:
            local_books = get_local_books_not_in_db(existing_book_ids)
            if local_books:
                print(f"Found {len(local_books)} new local books as fallback")
                books = local_books
        except Exception as e:
            print(f"Error scanning local books: {e}")
    
    return books

def filter_relevant_books(books: list, existing_book_ids: set):
    """Filter books to only include those not already in ChromaDB."""
    relevant_books = []
    book_info_map = {}
    
    for book in books:
        book_id = book.get("identifier", "")
        book_title = book.get("title", "N/A")
        
        # Determine if this is a local book
        is_local_book = book.get("source") == "local" or book_id.startswith("local_")
        
        # Add to info map with appropriate link
        if is_local_book:
            book_info_map[book_id] = {
                "title": book_title,
                "link": f"📁 Lokalna knjiga: {book_title}",
                "source_type": "local"
            }
        else:
            book_info_map[book_id] = {
                "title": book_title,
                "link": f"https://archive.org/details/{book_id}" if book_id else "",
                "source_type": "internet_archive"
            }
        
        # Only process if not in DB
        if book_id not in existing_book_ids:
            relevant_books.append(book)
            print(f"Selected for processing: {book_id} - {book_title}")
        else:
            print(f"Book {book_id} already exists in ChromaDB, skipping")
    
    return relevant_books, book_info_map

def download_and_process_books(relevant_books: list, existing_book_ids: set):
    """Download books and handle fallback logic."""
    downloader = InternetArchiveDownloader()
    is_local_books = any(book.get("source") == "local" for book in relevant_books)
    
    if is_local_books:
        # Process local books
        print("Processing local books...")
        book_texts = process_local_books_for_chromadb()
        relevant_book_ids = [book.get("identifier") for book in relevant_books]
        book_texts = {k: v for k, v in book_texts.items() if k in relevant_book_ids}
    else:
        # Download from Internet Archive
        book_identifiers = [book.get("identifier") for book in relevant_books[:3]]
        print(f"Downloading from Internet Archive: {book_identifiers}")
        book_texts = downloader.download_multiple_books(book_identifiers)
        
        # Check if key books are missing and fallback if needed
        book_texts = handle_download_fallback(book_texts, book_identifiers, existing_book_ids)
    
    return book_texts

def handle_download_fallback(book_texts: dict, book_identifiers: list, existing_book_ids: set):
    """Handle fallback to local books if downloads fail."""
    successful_downloads = [book_id for book_id, text in book_texts.items() if text and len(text.strip()) > 50]
    
    if not successful_downloads:
        print("Internet Archive downloads failed. Falling back to local books...")
        try:
            local_books = get_local_books_not_in_db(existing_book_ids)
            if local_books:
                print(f"Found {len(local_books)} new local books as fallback")
                return process_local_books_for_chromadb()
        except Exception as e:
            print(f"Error accessing local books: {e}")
    
    return book_texts

def process_books_to_chunks(relevant_books: list, book_texts: dict, book_info_map: dict):
    """Process downloaded books into chunks for ChromaDB."""
    all_chunks_to_add = []
    all_metadatas_to_add = []
    all_chunk_ids_to_add = []
    
    for book in relevant_books:
        book_id = book.get("identifier", "")
        book_title = book.get("title", "N/A")
        
        # Get text content
        full_text = book_texts.get(book_id, "")
        
        if not full_text:
            # Fallback to description
            description = book.get("description", "")
            full_text = " ".join(description) if isinstance(description, list) else str(description)
        
        if not full_text or len(full_text.strip()) < 50:
            print(f"Skipping {book_id}: No substantial text content")
            continue
        
        print(f"Processing book: {book_id} - '{book_title}' (Text length: {len(full_text)} chars)")
        
        # Chunk the text
        chunks, metadata_list, chunk_ids = chunk_book_text(book_id, book_title, full_text)
        
        all_chunks_to_add.extend(chunks)
        all_metadatas_to_add.extend(metadata_list)
        all_chunk_ids_to_add.extend(chunk_ids)
    
    return all_chunks_to_add, all_metadatas_to_add, all_chunk_ids_to_add

def chunk_book_text(book_id: str, book_title: str, full_text: str):
    """Chunk a single book's text with optimal strategy."""
    # Determine optimal settings
    optimal_chunk_size = get_optimal_chunk_size(full_text, max_chunk_size=800)
    
    # Choose strategy based on content type
    if "biography" in book_title.lower() or "memoir" in book_title.lower():
        strategy = ChunkStrategy.ADAPTIVE
    elif len(full_text) > 50000:
        strategy = ChunkStrategy.PARAGRAPH_BASED
    else:
        strategy = ChunkStrategy.SENTENCE_BASED
    
    print(f"Using chunking strategy: {strategy.value}, chunk size: {optimal_chunk_size}")
    
    # Create chunks
    chunks = chunk_text(full_text, chunk_size=optimal_chunk_size, strategy=strategy)
    
    if not chunks:
        print(f"No chunks generated for {book_id}")
        return [], [], []
    
    # Analyze quality
    quality_metrics = analyze_chunking_quality(chunks, full_text)
    print(f"Generated {len(chunks)} chunks from {book_id}")
    print(f"Chunking quality - Avg length: {quality_metrics.get('avg_chunk_length', 0):.0f}")
    
    # Create metadata
    chunks_list = []
    metadata_list = []
    chunk_ids = []
    
    for i, chunk in enumerate(chunks):
        chunk_id = f"{book_id}_fulltext_chunk_{i}"
        metadata = {
            "book_id": book_id,
            "title": book_title,
            "chunk_index": i,
            "source_type": "full_text"
        }
        chunks_list.append(chunk)
        metadata_list.append(metadata)
        chunk_ids.append(chunk_id)
    
    return chunks_list, metadata_list, chunk_ids

def add_chunks_to_chromadb(chunks: list, metadatas: list, chunk_ids: list):
    """Add chunks to ChromaDB and report status."""
    if not chunks:
        print("No new chunks to add to ChromaDB")
        return
    
    chunk_book_ids = set(metadata.get("book_id", "MISSING") for metadata in metadatas)
    print(f"Adding {len(chunks)} chunks from books: {chunk_book_ids}")
    
    try:
        add_documents_with_embeddings(chunks, metadatas, chunk_ids)
        print("Successfully added chunks to ChromaDB")
    except Exception as e:
        print(f"Error adding documents to ChromaDB: {e}")
        raise HTTPException(status_code=500, detail="Database indexing failed.")

def query_relevant_chunks(question: str):
    """Query ChromaDB for relevant chunks."""
    print(f"Querying ChromaDB for: '{question}'")
    
    # Detect if detailed question needs multi-strategy search
    detail_keywords = ["sati", "time", "kada", "when", "kako", "how", "što", "what", "gdje", "where"]
    is_detailed_question = any(keyword in question.lower() for keyword in detail_keywords)
    
    try:
        if is_detailed_question:
            print("Using multi-strategy search for detailed question...")
            results = query_with_multiple_strategies(question, n_results=30)
        else:
            results = query_similar_documents(question, n_results=20)
        
        return process_query_results(results, question)
        
    except Exception as e:
        print(f"Error querying ChromaDB: {e}")
        return []

def process_query_results(results: dict, question: str = ""):
    """Process ChromaDB query results into document list with smart filtering."""
    retrieved_documents = []
    
    if not results.get("documents") or not results["documents"][0]:
        return retrieved_documents
    
    # Detect entities in question to prioritize relevant sources
    detected_people = detect_people_in_question(question)
    detected_events = detect_historical_events_in_question(question)
    
    print(f"ChromaDB returned {len(results['documents'][0])} total chunks")
    
    # Collect all documents with metadata
    all_docs = []
    for i in range(len(results["documents"][0])):
        doc_content = results["documents"][0][i]
        doc_metadata = results["metadatas"][0][i]
        doc_distance = results["distances"][0][i] if results.get("distances") and results["distances"][0] else None
        
        # Skip chunks that are too short or empty
        if not doc_content or len(doc_content.strip()) < 10:
            print(f"  Skipping short/empty chunk from {doc_metadata.get('book_id', 'unknown')}: '{doc_content}'")
            continue
        
        book_id = doc_metadata.get("book_id", "unknown")
        chunk_index = doc_metadata.get("chunk_index", "unknown")
        
        all_docs.append({
            "content": doc_content,
            "metadata": doc_metadata,
            "score": doc_distance,
            "book_id": book_id,
            "chunk_index": chunk_index
        })
    
    # Prioritize documents from relevant books
    relevant_docs = []
    other_docs = []
    
    for doc in all_docs:
        book_id_lower = doc["book_id"].lower()
        book_title_lower = doc["metadata"].get("title", "").lower()
        is_relevant = False
        
        # Check if book is relevant to detected people
        if detected_people:
            for person in detected_people:
                person_parts = person.split()
                # Check for full name or significant parts in book_id OR title
                if (person in book_id_lower or person in book_title_lower or
                    any(part in book_id_lower for part in person_parts if len(part) > 3) or
                    any(part in book_title_lower for part in person_parts if len(part) > 3) or
                    # Special handling for compound names like "nelson mandela"
                    (len(person_parts) >= 2 and (
                        all(part in book_id_lower for part in person_parts) or
                        all(part in book_title_lower for part in person_parts)
                    ))):
                    is_relevant = True
                    print(f"  Found relevant book for '{person}': {doc['book_id']} - {doc['metadata'].get('title', 'N/A')}")
                    break
        
        # Check if book is relevant to detected events
        if detected_events and not is_relevant:
            event_keywords = {
                'domovinski rat': ['domovinski', 'homeland', 'war', 'independence', 'croatia', 'hrvatski', 'agresija', 'jna'],
                'ndh': ['ndh', 'nezavisna', 'država', 'hrvatska', 'ustaše', 'pavelić'],
                'drugi svjetski rat': ['world war', 'wwii', 'ww2', 'nazi', 'hitler'],
                'jugoslavenski ratovi': ['yugoslav', 'balkan', 'bosnia', 'serbia'],
            }
            
            for event in detected_events:
                if event in event_keywords:
                    keywords = event_keywords[event]
                    if any(keyword in book_id_lower for keyword in keywords):
                        is_relevant = True
                        break
        
        if is_relevant:
            relevant_docs.append(doc)
        else:
            other_docs.append(doc)
    
    # Take top relevant docs first, then fill with others if needed
    final_docs = relevant_docs[:10]  # Top 10 from relevant sources
    if len(final_docs) < 5:
        # Add some from other sources if we don't have enough relevant ones
        final_docs.extend(other_docs[:5-len(final_docs)])
    
    # Convert to expected format and limit to 5 for display
    for i, doc in enumerate(final_docs[:5]):
        content_preview = doc['content'][:100] if doc['content'] else "[EMPTY CONTENT]"
        print(f"  ✓ Chunk {i+1}: Book={doc['book_id']}, ChunkIndex={doc['chunk_index']}, Distance={doc['score']}")
        print(f"    Content length: {len(doc['content'])}, Preview: {content_preview}...")
        
        retrieved_documents.append({
            "content": doc["content"],
            "metadata": doc["metadata"],
            "score": doc["score"]
        })
    
    return retrieved_documents

def handle_local_books_fallback(question: str, retrieved_documents: list, existing_book_ids: set):
    """Handle fallback to local books if needed."""
    # Check if we need fallback based on results quality and detected entities
    detected_people = detect_people_in_question(question)
    detected_events = detect_historical_events_in_question(question)
    
    # Check if we have good content for detected people
    has_good_content_for_people = False
    if detected_people:
        for doc in retrieved_documents:
            doc_book_id = doc["metadata"].get("book_id", "").lower()
            doc_content = doc["content"].lower()
            for person in detected_people:
                person_parts = person.split()
                # Check if person is mentioned in book_id AND content
                if (any(part in doc_book_id for part in person_parts if len(part) > 3) and 
                    (person in doc_content or any(part in doc_content for part in person_parts if len(part) > 3)) and
                    len(doc["content"]) > 50):  # Check for substantial content
                    has_good_content_for_people = True
                    print(f"  Found substantial content for '{person}' in {doc_book_id}")
                    break
            if has_good_content_for_people:
                break
    
    need_fallback = (
        len(retrieved_documents) < 3 or 
        (detected_people and not has_good_content_for_people) or
        (detected_events and not any(
            any(event_keyword in doc["metadata"].get("book_id", "").lower() 
                for event in detected_events 
                for event_keyword in event.split())
            for doc in retrieved_documents
        ))
    )
    
    if not need_fallback:
        return retrieved_documents
    
    if detected_people or detected_events:
        print(f"Activating local books fallback for entities: people={detected_people}, events={detected_events}")
        if detected_people and not has_good_content_for_people:
            print(f"  Reason: No substantial content found for detected people in retrieved documents")
    else:
        print("Activating local books fallback due to insufficient results...")
    
    try:
        # Check if we need to reprocess existing books with poor quality chunks
        books_to_reprocess = []
        if detected_people and not has_good_content_for_people:
            print("Checking if relevant books need reprocessing...")
            for person in detected_people:
                person_parts = person.split()
                # Look for books that should contain this person but have poor chunks
                for book_id in existing_book_ids:
                    if any(part in book_id.lower() for part in person_parts if len(part) > 3):
                        print(f"  Found book '{book_id}' that should contain '{person}' - checking quality...")
                        # This book should be relevant but may have poor chunks
                        books_to_reprocess.append(book_id)
        
        if books_to_reprocess:
            print(f"Reprocessing books with poor chunks: {books_to_reprocess}")
            # Try to get the local book and reprocess it
            local_books = scan_local_books()
            for local_book in local_books:
                local_book_id = local_book["identifier"]
                if local_book_id in books_to_reprocess:
                    print(f"Reprocessing local book: {local_book_id}")
                    # Delete existing chunks and reprocess
                    try:
                        deleted_count = delete_book_chunks(local_book_id)
                        print(f"Deleted {deleted_count} existing chunks for {local_book_id}")
                    except Exception as e:
                        print(f"Error deleting chunks for {local_book_id}: {e}")
                    
                    # Reprocess the book
                    local_book_texts = process_local_books_for_chromadb()
                    if local_book_id in local_book_texts:
                        process_and_add_local_books([local_book], local_book_texts)
                        
                        # Query again with reprocessed book
                        print("Querying ChromaDB again with reprocessed book...")
                        results = query_similar_documents(question, n_results=10)
                        additional_docs = process_query_results(results, question)
                        retrieved_documents.extend(additional_docs)
                        return retrieved_documents
        
        # If no reprocessing needed, try regular fallback
        local_books = get_local_books_not_in_db(existing_book_ids)
        if not local_books:
            print("No new local books found")
            return retrieved_documents
        
        # Find relevant books for people and events
        relevant_books = []
        if detected_people:
            people_books = find_books_for_people(local_books, detected_people)
            relevant_books.extend(people_books)
        
        if detected_events:
            event_books = find_books_for_events(local_books, detected_events)
            relevant_books.extend(event_books)
        
        # Remove duplicates and use relevant books if found
        if relevant_books:
            unique_relevant_books = []
            seen_ids = set()
            for book in relevant_books:
                if book['identifier'] not in seen_ids:
                    unique_relevant_books.append(book)
                    seen_ids.add(book['identifier'])
            local_books = unique_relevant_books
            print(f"Found {len(unique_relevant_books)} books relevant to detected entities")
        
        print(f"Processing {len(local_books)} local books:")
        for book in local_books:
            print(f"  - {book['identifier']}: {book['title']}")
        
        # Process and add local books
        local_book_texts = process_local_books_for_chromadb()
        if local_book_texts:
            process_and_add_local_books(local_books, local_book_texts)
            
            # Query again with local books
            print("Querying ChromaDB again with local books...")
            results = query_similar_documents(question, n_results=10)
            additional_docs = process_query_results(results, question)
            retrieved_documents.extend(additional_docs)
    
    except Exception as e:
        print(f"Error in local books fallback: {e}")
    
    return retrieved_documents

def process_and_add_local_books(local_books: list, local_book_texts: dict):
    """Process and add local books to ChromaDB."""
    local_chunks = []
    local_metadatas = []
    local_chunk_ids = []
    
    for book in local_books:
        book_id = book["identifier"]
        book_title = book["title"]
        full_text = local_book_texts.get(book_id, "")
        
        if not full_text or len(full_text.strip()) < 50:
            continue
        
        print(f"Processing local book: {book_id} - '{book_title}' ({len(full_text)} chars)")
        
        chunks, metadatas, chunk_ids = chunk_book_text(book_id, book_title, full_text)
        
        # Mark as local file
        for metadata in metadatas:
            metadata["source_type"] = "local_file"
        
        local_chunks.extend(chunks)
        local_metadatas.extend(metadatas)
        local_chunk_ids.extend(chunk_ids)
    
    if local_chunks:
        add_chunks_to_chromadb(local_chunks, local_metadatas, local_chunk_ids)

def generate_final_answer(question: str, retrieved_documents: list):
    """Generate final answer using LLM."""
    if not retrieved_documents:
        return "Nije pronađen dovoljno relevantan kontekst za odgovor na vaše pitanje."
    
    # Check if the content is actually relevant to the question
    detected_people = detect_people_in_question(question)
    detected_events = detect_historical_events_in_question(question)
    
    # If we detected specific entities, verify that the content is actually about them
    relevant_content = []
    for doc in retrieved_documents:
        content = doc["content"].lower()
        book_id = doc["metadata"].get("book_id", "").lower()
        title = doc["metadata"].get("title", "").lower()
        
        is_relevant = False
        
        # Check if content or metadata mentions the detected people/events
        if detected_people:
            for person in detected_people:
                person_parts = person.split()
                # Check if person is mentioned in content, book_id, or title
                if (person in content or 
                    any(part in content for part in person_parts if len(part) > 3) or
                    any(part in book_id for part in person_parts if len(part) > 3) or
                    any(part in title for part in person_parts if len(part) > 3)):
                    is_relevant = True
                    print(f"  Found relevant content for '{person}' in {doc['metadata'].get('book_id', 'unknown')}")
                    break
        
        if detected_events:
            for event in detected_events:
                event_keywords = {
                    'domovinski rat': ['domovinski', 'homeland', 'croatia', 'war', 'independence'],
                    'ndh': ['ndh', 'nezavisna', 'država', 'hrvatska', 'ustaše'],
                    'drugi svjetski rat': ['world war', 'wwii', 'ww2', 'nazi'],
                }
                if event in event_keywords:
                    keywords = event_keywords[event]
                    if any(keyword in content for keyword in keywords):
                        is_relevant = True
                        break
        
        # If no specific entities detected, consider all content relevant
        if not detected_people and not detected_events:
            is_relevant = True
        
        if is_relevant:
            relevant_content.append(doc["content"])
    
    # If no relevant content found, return appropriate message
    if not relevant_content:
        if detected_people:
            people_str = ", ".join(detected_people)
            return f"Nije pronađen relevantan sadržaj o: {people_str}. Molim vas pokušajte s drugim pitanjem."
        elif detected_events:
            events_str = ", ".join(detected_events)
            return f"Nije pronađen relevantan sadržaj o: {events_str}. Molim vas pokušajte s drugim pitanjem."
        else:
            return "Nije pronađen dovoljno relevantan kontekst za odgovor na vaše pitanje."
    
    combined_context = "\n\n---\n\n".join(relevant_content)
    
    prompt = f"""Korisničko pitanje: {question}

Relevantni odlomci iz knjiga:
{combined_context}

VAŽNO: Odgovori na pitanje koristeći SAMO informacije iz dostavljenih odlomaka koji su stvarno relevantni za pitanje. 
Ako odlomci ne sadrže informacije o temi pitanja, odgovori: "Na temelju dostavljenih odlomaka ne mogu pronaći informacije o ovoj temi."
Ne izmišljaj informacije koje nisu u odlomcima."""
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ti si povijesni asistent. Odgovaraj SAMO na temelju dostavljenog konteksta. Ako kontekst nije relevantan za pitanje, jasno to navedi."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1  # Lower temperature for more consistent responses
        )
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        return f"Greška u generiranju odgovora: {str(e)}"

def get_book_info_for_existing_books(retrieved_documents: list):
    """Get book info for books that are already in ChromaDB."""
    book_info_map = {}
    
    for doc in retrieved_documents:
        book_id = doc["metadata"].get("book_id")
        if book_id and book_id not in book_info_map:
            book_title = doc["metadata"].get("title", book_id)
            is_local_book = book_id.startswith("local_")
            
            if is_local_book:
                # Clean up local book title
                clean_title = book_title.replace("local_", "").replace("-", " ").replace("_", " ")
                book_info_map[book_id] = {
                    "title": clean_title,
                    "link": f"📁 Lokalna knjiga: {clean_title}",
                    "source_type": "local"
                }
            else:
                book_info_map[book_id] = {
                    "title": book_title,
                    "link": f"https://archive.org/details/{book_id}",
                    "source_type": "internet_archive"
                }
    
    return book_info_map

def prepare_source_documents(retrieved_documents: list, book_info_map: dict):
    """Prepare source documents for response with proper links and titles."""
    unique_sources = {}
    
    for doc in retrieved_documents:
        book_id = doc["metadata"].get("book_id")
        if book_id and book_id not in unique_sources:
            book_info = book_info_map.get(book_id, {})
            
            # Determine if this is a local book or Internet Archive book
            is_local_book = book_id.startswith("local_")
            
            if is_local_book:
                # For local books, show file name and mark as local
                clean_title = book_info.get("title", book_id.replace("local_", "").replace("-", " ").replace("_", " "))
                document_link = f"📁 Lokalna knjiga: {clean_title}"
                display_title = f"Lokalna knjiga: {clean_title}"
            else:
                # For Internet Archive books, show proper link
                display_title = book_info.get("title", "Historical Document")
                document_link = f"🔗 {book_info.get('link', f'https://archive.org/details/{book_id}')}"
            
            unique_sources[book_id] = {
                "document_id": book_id,
                "title": display_title,
                "link": document_link,
                "content": doc["content"][:500] + "..." if len(doc["content"]) > 500 else doc["content"],  # Limit content preview
                "score": doc.get("score", 0.0),
                "source_type": "local" if is_local_book else "internet_archive"
            }
    
    return list(unique_sources.values())

# ========================================
# MAIN API ENDPOINT (now much simpler!)
# ========================================

@router.post("/", response_model=AIResponse)
async def ai_generate(request: AIRequest):
    """Main AI generation endpoint - now clean and readable!"""
    if not client:
        raise HTTPException(status_code=500, detail="OpenAI service not available.")
    
    print(f"User question: {request.question}")
    
    # 1. Get existing books to avoid duplicates
    existing_book_ids = get_existing_book_ids()
    print(f"Found {len(existing_book_ids)} existing books in ChromaDB")
    
    # 2. Generate search keywords
    keywords, archive_query_string = generate_search_keywords(request.question)
    
    # 3. Search for books
    books = search_for_books(archive_query_string, existing_book_ids, request.question)
    if not books:
        return AIResponse(answer="Nije pronađena nijedna relevantna knjiga za vaš upit.")
    
    # 4. Filter and prepare books for processing
    relevant_books, book_info_map = filter_relevant_books(books, existing_book_ids)
    
    # 5. Download and process new books (if any)
    if relevant_books:
        book_texts = download_and_process_books(relevant_books, existing_book_ids)
        chunks, metadatas, chunk_ids = process_books_to_chunks(relevant_books, book_texts, book_info_map)
        add_chunks_to_chromadb(chunks, metadatas, chunk_ids)
    
    # 6. Query for relevant chunks
    retrieved_documents = query_relevant_chunks(request.question)
    
    # 7. Handle local books fallback if needed
    retrieved_documents = handle_local_books_fallback(
        request.question, retrieved_documents, existing_book_ids
    )
    
    # 8. Generate final answer
    final_answer = generate_final_answer(request.question, retrieved_documents)
    
    # 9. Prepare response with complete book info
    # Merge book info from new books and existing books
    complete_book_info_map = book_info_map.copy()
    existing_book_info = get_book_info_for_existing_books(retrieved_documents)
    complete_book_info_map.update(existing_book_info)
    
    source_documents = prepare_source_documents(retrieved_documents, complete_book_info_map)
    
    return AIResponse(
        answer=final_answer,
        source_documents=source_documents
    )
