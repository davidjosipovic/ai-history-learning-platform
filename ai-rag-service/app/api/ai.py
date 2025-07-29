from fastapi import APIRouter, HTTPException
from app.schemas.ai import AIRequest, AIResponse
import openai
import os
import json # Dodano za json.loads
from dotenv import load_dotenv

# Uvozimo ispravljene funkcije
# Pretpostavljam da su ove funkcije u app.core.internet_archive modulu
from app.core.internet_archive import (
    generate_keywords_from_question,  # Sada generira listu ključnih riječi
    build_internet_archive_query_string, # Sada gradi URL-kodirani query za 'q'
    search_internet_archive_advanced    # Koristi advanced search endpoint
)

# Import downloader for full text extraction
from app.core.internet_archive_downloader import InternetArchiveDownloader

# Pretpostavljam da su ove funkcije ispravno implementirane
from app.core.text_chunking import chunk_text 
from app.core.chroma_db import add_documents_with_embeddings, query_similar_documents, query_with_multiple_strategies, get_chroma_client # Dodana get_chroma_client

# Import local books processor
from app.core.local_books import scan_local_books, process_local_books_for_chromadb

# Inicijalizacija OpenAI klijenta
load_dotenv()
try:
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception as e:
    print(f"ERROR: Could not initialize OpenAI client. Please check OPENAI_API_KEY: {e}")
    client = None # Postavite None ako inicijalizacija ne uspije

router = APIRouter()

@router.post("/", response_model=AIResponse)
async def ai_generate(request: AIRequest):
    if not client:
        raise HTTPException(status_code=500, detail="OpenAI service not available.")

    # 1. Generate keywords from user's question using LLM
    print(f"User question: {request.question}")
    try:
        # get_keywords_from_question vraća listu stringova
        keywords = generate_keywords_from_question(request.question)
        if not keywords or keywords == [request.question]: # Provjeri da nije fallback na originalno pitanje
            print(f"LLM failed to generate specific keywords, falling back to original question.")
            keywords = [request.question] # Osiguraj da imamo barem jednu ključnu riječ
        
        # build_internet_archive_query_string kreira 'q' parametar string
        archive_query_string = build_internet_archive_query_string(keywords)
        print(f"Generated Internet Archive 'q' parameter: {archive_query_string}")

    except Exception as e:
        print(f"Error in generating search keywords/query: {e}")
        # Fallback ako generiranje upita ne uspije u potpunosti
        archive_query_string = build_internet_archive_query_string([request.question])
        print(f"Fallback to simple Internet Archive query: {archive_query_string}")

    # 2. Search Internet Archive with optimized query
    books = []
    try:
        # Koristimo search_internet_archive_advanced koja filtrira po mediatype (texts)
        # i vraća specifična polja
        books = search_internet_archive_advanced(archive_query_string, rows=5)
        print(f"Found {len(books)} books from Internet Archive.")
    except Exception as e:
        print(f"Error searching Internet Archive: {e}")
        # books ostaje prazna lista

    if not books:
        print("No books found from Internet Archive. Checking local books directory...")
        
        # Fallback to local books
        try:
            local_books = scan_local_books()
            if local_books:
                print(f"Found {len(local_books)} local books as fallback")
                books = local_books
            else:
                return AIResponse(answer=f"Nije pronađena nijedna relevantna knjiga na Internet Archive ili u lokalnoj kolekciji za upit: '{' '.join(keywords)}'.")
        except Exception as e:
            print(f"Error scanning local books: {e}")
            return AIResponse(answer=f"Nije pronađena nijedna relevantna knjiga na Internet Archive za upit: '{' '.join(keywords)}'.")

    # Pripremamo sve chunkove iz svih knjiga za dodavanje u ChromaDB
    all_chunks_to_add = []
    all_metadatas_to_add = []
    all_chunk_ids_to_add = []
    
    # Lista za praćenje originalnih podataka o knjigama
    book_info_map = {} 

    # 3. Download and process full text content from relevant books
    downloader = InternetArchiveDownloader()
    
    # Provjeri koje knjige već postoje u ChromaDB
    from app.core.chroma_db import get_existing_book_ids
    existing_book_ids = get_existing_book_ids()
    
    # Determine if we're working with local or Internet Archive books
    is_local_books = any(book.get("source") == "local" for book in books)
    
    # Filter books to only include those not already in DB
    relevant_books = []
    for book in books:
        book_id = book.get("identifier", "")
        book_title = book.get("title", "").lower()
        
        # Provjeri da li knjiga već postoji u bazi
        if book_id in existing_book_ids:
            print(f"Book {book_id} already exists in ChromaDB, skipping download")
            continue
        
        # Trust Internet Archive's search relevance - no additional filtering needed
        relevant_books.append(book)
        print(f"Selected for processing: {book_id} - {book.get('title')}")
    
    if not relevant_books:
        print("No new books to download. Checking if we have existing books for this query...")
        # Dodaj sve postojeće knjige u book_info_map za query
        for book in books:
            book_id = book.get("identifier", "")
            if book_id in existing_book_ids:
                book_title = book.get("title", "N/A")
                book_info_map[book_id] = {
                    "title": book_title,
                    "link": f"https://archive.org/details/{book_id}" if book_id else ""
                }
                print(f"Using existing book from ChromaDB: {book_id} - {book_title}")
        
        if not book_info_map:
            return AIResponse(answer="Nisu pronađene relevantne knjige za preuzimanje i analizu.")
    else:
        # Download full text content from top 2-3 most relevant NEW books
        if is_local_books:
            # Process local books
            print("Processing local books...")
            try:
                book_texts = process_local_books_for_chromadb()
                # Filter to only include books that were selected as relevant
                relevant_book_ids = [book.get("identifier") for book in relevant_books]
                book_texts = {k: v for k, v in book_texts.items() if k in relevant_book_ids}
                print(f"Processed {len(book_texts)} local books")
            except Exception as e:
                print(f"Error processing local books: {e}")
                book_texts = {}
        else:
            # Download from Internet Archive
            book_identifiers = [book.get("identifier") for book in relevant_books[:3]]
            print(f"Downloading full text from Internet Archive books: {book_identifiers}")
            book_texts = downloader.download_multiple_books(book_identifiers)
            
            # Check if downloads failed - if so, fallback to local books
            successful_downloads = [book_id for book_id, text in book_texts.items() if text and len(text.strip()) > 50]
            if not successful_downloads:
                print("Internet Archive downloads failed. Falling back to local books...")
                try:
                    local_books = scan_local_books()
                    if local_books:
                        print(f"Found {len(local_books)} local books as fallback")
                        # Use local books instead
                        book_texts = process_local_books_for_chromadb()
                        relevant_books = local_books  # Switch to local books
                        is_local_books = True
                        print(f"Switched to local books: {list(book_texts.keys())}")
                    else:
                        print("No local books found either")
                except Exception as e:
                    print(f"Error accessing local books: {e}")
        
        if not book_texts:
            # Ako nema novih knjiga, provjeri postojeće
            for book in books:
                book_id = book.get("identifier", "")
                if book_id in existing_book_ids:
                    book_title = book.get("title", "N/A")
                    book_info_map[book_id] = {
                        "title": book_title,
                        "link": f"https://archive.org/details/{book_id}" if book_id else ""
                    }
            
            if not book_info_map:
                return AIResponse(answer="Nije moguće preuzeti sadržaj knjiga za analizu.")
        else:
            # Proces novih downloadiranih knjiga
            process_new_books = True

    # 4. Process downloaded texts for chunking and indexing (samo ako ima novih knjiga)
    all_chunks_to_add = []
    all_metadatas_to_add = []
    all_chunk_ids_to_add = []
    
    # book_info_map je već inicijaliziran iznad - ne smijemo ga ponovno postavljati na {}
    
    # Obradi samo nove knjige ako ima downloadiranih tekstova
    if 'book_texts' in locals() and book_texts:
        for book in relevant_books:
            book_id = book.get("identifier", "")
            book_title = book.get("title", "N/A")
            
            # Pohrani podatke o knjizi za kasnije
            book_info_map[book_id] = {
                "title": book_title,
                "link": f"https://archive.org/details/{book_id}" if book_id else ""
            }
            
            # Get downloaded text for this book
            full_text = book_texts.get(book_id, "")
            
            if not full_text:
                print(f"No text content available for {book_id}, using description fallback")
                description = book.get("description", "")
                if isinstance(description, list):
                    full_text = " ".join(description)
                else:
                    full_text = str(description)
            
            if not full_text or len(full_text.strip()) < 50:
                print(f"Skipping {book_id}: No substantial text content")
                continue
            
            print(f"Processing book: {book_id} - '{book_title}' (Text length: {len(full_text)} chars)")
            
            # Chunk the full text content
            chunks = chunk_text(full_text)
            
            if not chunks:
                print(f"No chunks generated for {book_id}. Skipping.")
                continue
                
            print(f"Generated {len(chunks)} chunks from {book_id}")
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{book_id}_fulltext_chunk_{i}"
                metadata = {
                    "book_id": book_id,
                    "title": book_title,
                    "chunk_index": i,
                    "source_type": "full_text"  # Mark as full text vs description
                }
                all_chunks_to_add.append(chunk)
                all_metadatas_to_add.append(metadata)
                all_chunk_ids_to_add.append(chunk_id)
    
    # Dodaj sve postojeće knjige u book_info_map za pretraživanje
    for book in books:
        book_id = book.get("identifier", "")
        if book_id in existing_book_ids and book_id not in book_info_map:
            book_title = book.get("title", "N/A")
            book_info_map[book_id] = {
                "title": book_title,
                "link": f"https://archive.org/details/{book_id}" if book_id else ""
            } 

    
    # 5. Add all collected chunks to ChromaDB (or update existing) - samo ako ima novih chunkova
    if all_chunks_to_add:
        # Debug: Print what book_ids we're about to add
        chunk_book_ids = set()
        for metadata in all_metadatas_to_add:
            chunk_book_ids.add(metadata.get("book_id", "MISSING"))
        print(f"DEBUG: About to add {len(all_chunks_to_add)} chunks from books: {chunk_book_ids}")

        print(f"Adding {len(all_chunks_to_add)} full-text chunks to ChromaDB.")
        try:
            add_documents_with_embeddings(all_chunks_to_add, all_metadatas_to_add, all_chunk_ids_to_add)
            
            # Check total number of documents in ChromaDB after adding
            from app.core.chroma_db import get_or_create_collection
            collection = get_or_create_collection()
            if collection:
                total_docs = collection.count()
                print(f"Total documents in ChromaDB after adding: {total_docs}")
            
        except Exception as e:
            print(f"Error adding documents to ChromaDB: {e}")
            # Možete ovdje baciti HTTPException ako je to kritična greška
            raise HTTPException(status_code=500, detail="Database indexing failed.")
    else:
        print("No new chunks to add to ChromaDB, using existing data.")

    # 6. Find the MOST relevant chunks from ALL books in ChromaDB
    print(f"Querying ChromaDB for relevant chunks for question: '{request.question}'")
    # Get book IDs from current search for additional metadata
    current_book_ids = set(book_info_map.keys())
    print(f"Current book IDs: {current_book_ids}")
    
    try:
        # Check if this is a detailed/specific question that needs multi-strategy search
        detail_keywords = ["sati", "time", "kada", "when", "kako", "how", "što", "what", "gdje", "where"]
        is_detailed_question = any(keyword in request.question.lower() for keyword in detail_keywords)
        
        if is_detailed_question:
            print("Detected detailed question, using multi-strategy search...")
            results = query_with_multiple_strategies(request.question, n_results=30) 
        else:
            # Query all relevant documents, not just current ones
            results = query_similar_documents(request.question, n_results=20) 
        
        retrieved_documents = []
        if results.get("documents") and results["documents"][0]:
            print(f"ChromaDB returned {len(results['documents'][0])} total chunks")
            
            # Include ALL relevant chunks regardless of which search indexed them
            for i in range(len(results["documents"][0])):
                doc_content = results["documents"][0][i]
                doc_metadata = results["metadatas"][0][i]
                doc_distance = results["distances"][0][i] if results.get("distances") and results["distances"][0] else None
                
                book_id = doc_metadata.get("book_id", "unknown")
                
                # Include all relevant chunks - trust ChromaDB similarity scoring
                chunk_index = doc_metadata.get("chunk_index", "unknown")
                print(f"  ✓ Chunk {len(retrieved_documents)+1}: Book={book_id}, ChunkIndex={chunk_index}, Distance={doc_distance}")
                print(f"    Content preview: {doc_content[:100]}...")
                
                retrieved_documents.append({
                    "content": doc_content,
                    "metadata": doc_metadata,
                    "score": doc_distance
                })
                
                # Get all available chunks from relevant books, up to 5
                if len(retrieved_documents) >= 5:
                    break
            
            # If we have very few chunks, add more chunks regardless of distance
            if len(retrieved_documents) < 2:
                print(f"Only {len(retrieved_documents)} relevant chunks found. Adding more chunks...")
                for i in range(len(results["documents"][0])):
                    doc_content = results["documents"][0][i]
                    doc_metadata = results["metadatas"][0][i]
                    doc_distance = results["distances"][0][i] if results.get("distances") and results["distances"][0] else None
                    book_id = doc_metadata.get("book_id", "unknown")
                    
                    # Check if we already have this chunk
                    if not any(d["metadata"]["book_id"] == book_id and d["metadata"]["chunk_index"] == doc_metadata.get("chunk_index") for d in retrieved_documents):
                        chunk_index = doc_metadata.get("chunk_index", "unknown")
                        print(f"  + Adding Chunk: Book={book_id}, ChunkIndex={chunk_index}, Distance={doc_distance}")
                        
                        retrieved_documents.append({
                            "content": doc_content,
                            "metadata": doc_metadata,
                            "score": doc_distance
                        })
                        
                        if len(retrieved_documents) >= 5:
                            break
            
            print(f"Retrieved {len(retrieved_documents)} relevant chunks from current books.")
        else:
            print("No relevant chunks found in ChromaDB.")
            
    except Exception as e:
        print(f"Error querying ChromaDB: {e}")
        # raise HTTPException(status_code=500, detail="Database query failed.")
        retrieved_documents = []


    if not retrieved_documents:
        print("No relevant chunks found. Trying local books as fallback...")
        
        # Fallback to local books if no good results from Internet Archive/ChromaDB
        try:
            local_books = scan_local_books()
            if local_books:
                print(f"Found {len(local_books)} local books as fallback")
                
                # Process local books
                local_book_texts = process_local_books_for_chromadb()
                
                if local_book_texts:
                    # Add local books to ChromaDB
                    local_chunks_to_add = []
                    local_metadatas_to_add = []
                    local_chunk_ids_to_add = []
                    local_book_info_map = {}
                    
                    for book in local_books:
                        book_id = book["identifier"]
                        book_title = book["title"]
                        
                        # Store book info
                        local_book_info_map[book_id] = {
                            "title": book_title,
                            "link": f"local_file://{book['file_path']}"
                        }
                        
                        # Get text content
                        full_text = local_book_texts.get(book_id, "")
                        if not full_text or len(full_text.strip()) < 50:
                            continue
                            
                        print(f"Processing local book: {book_id} - '{book_title}' (Text length: {len(full_text)} chars)")
                        
                        # Chunk the text
                        chunks = chunk_text(full_text)
                        if not chunks:
                            continue
                            
                        print(f"Generated {len(chunks)} chunks from local book {book_id}")
                        
                        for i, chunk in enumerate(chunks):
                            chunk_id = f"{book_id}_local_chunk_{i}"
                            metadata = {
                                "book_id": book_id,
                                "title": book_title,
                                "chunk_index": i,
                                "source_type": "local_file"
                            }
                            local_chunks_to_add.append(chunk)
                            local_metadatas_to_add.append(metadata)
                            local_chunk_ids_to_add.append(chunk_id)
                    
                    if local_chunks_to_add:
                        print(f"Adding {len(local_chunks_to_add)} chunks from local books to ChromaDB.")
                        add_documents_with_embeddings(local_chunks_to_add, local_metadatas_to_add, local_chunk_ids_to_add)
                        
                        # Query again with local books included
                        print("Querying ChromaDB again with local books included...")
                        results = query_similar_documents(request.question, n_results=10)
                        
                        if results.get("documents") and results["documents"][0]:
                            for i in range(min(5, len(results["documents"][0]))):
                                doc_content = results["documents"][0][i]
                                doc_metadata = results["metadatas"][0][i]
                                doc_distance = results["distances"][0][i] if results.get("distances") and results["distances"][0] else None
                                
                                book_id = doc_metadata.get("book_id", "unknown")
                                chunk_index = doc_metadata.get("chunk_index", "unknown")
                                print(f"  ✓ Local Chunk {len(retrieved_documents)+1}: Book={book_id}, ChunkIndex={chunk_index}, Distance={doc_distance}")
                                
                                retrieved_documents.append({
                                    "content": doc_content,
                                    "metadata": doc_metadata,
                                    "score": doc_distance
                                })
                            
                            # Update book_info_map with local books
                            book_info_map.update(local_book_info_map)
                            
                            print(f"Retrieved {len(retrieved_documents)} chunks including local books.")
                
        except Exception as e:
            print(f"Error processing local books fallback: {e}")
    
    if not retrieved_documents:
        return AIResponse(answer=f"Nije pronađen dovoljno relevantan kontekst ni u Internet Archive knjigama ni u lokalnoj kolekciji za odgovor na vaše pitanje.")

    # 6. Generate final answer using ALL relevant chunks as context
    # Sastavimo sav relevantan tekst iz retrieved_documents
    context_texts = [doc["content"] for doc in retrieved_documents]
    combined_context = "\n\n---\n\n".join(context_texts)

    prompt_for_llm = f"Korisničko pitanje: {request.question}\n\nRelevantni odlomci iz knjiga:\n{combined_context}\n\nOdgovori na pitanje koristeći SAMO informacije iz dostavljenih odlomaka. Ako informacije nisu dovoljne, navedi to."

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # Ili gpt-4 za bolju kvalitetu
            messages=[
                {"role": "system", "content": "Ti si povijesni asistent. Odgovaraj samo na temelju dostavljenog konteksta. Ako odgovor nije u kontekstu, reci da ne možeš odgovoriti."},
                {"role": "user", "content": prompt_for_llm}
            ],
            temperature=0.2 # Lagano povećaj temperaturu za malo više kreativnosti, ali zadrži fokus
        )
        final_answer = response.choices[0].message.content.strip()
        
        # Check if the answer is insufficient and we haven't tried local books yet
        insufficient_answers = [
            "ne mogu odgovoriti",
            "cannot answer",
            "informacije nisu dovoljne",
            "information is not sufficient",
            "nema dovoljno informacija",
            "not enough information"
        ]
        
        answer_is_insufficient = any(phrase in final_answer.lower() for phrase in insufficient_answers)
        has_local_sources = any(doc["metadata"].get("source_type") == "local_file" for doc in retrieved_documents)
        
        if answer_is_insufficient and not has_local_sources:
            print("Answer is insufficient and no local books used yet. Trying local books fallback...")
            
            # Try local books fallback
            try:
                local_books = scan_local_books()
                if local_books:
                    print(f"Found {len(local_books)} local books for insufficient answer fallback")
                    
                    # Process and add local books (same logic as above but as fallback)
                    local_book_texts = process_local_books_for_chromadb()
                    
                    if local_book_texts:
                        # Quick processing of local books
                        additional_chunks = []
                        additional_book_info = {}
                        
                        for book in local_books:
                            book_id = book["identifier"]
                            book_title = book["title"]
                            
                            additional_book_info[book_id] = {
                                "title": book_title,
                                "link": f"local_file://{book['file_path']}"
                            }
                            
                            full_text = local_book_texts.get(book_id, "")
                            if full_text and len(full_text.strip()) > 50:
                                # Add to ChromaDB and get relevant chunks immediately
                                chunks = chunk_text(full_text)
                                
                                if chunks:
                                    # Add to ChromaDB
                                    local_chunks_to_add = []
                                    local_metadatas_to_add = []
                                    local_chunk_ids_to_add = []
                                    
                                    for i, chunk in enumerate(chunks):
                                        chunk_id = f"{book_id}_fallback_chunk_{i}"
                                        metadata = {
                                            "book_id": book_id,
                                            "title": book_title,
                                            "chunk_index": i,
                                            "source_type": "local_file"
                                        }
                                        local_chunks_to_add.append(chunk)
                                        local_metadatas_to_add.append(metadata)
                                        local_chunk_ids_to_add.append(chunk_id)
                                    
                                    if local_chunks_to_add:
                                        add_documents_with_embeddings(local_chunks_to_add, local_metadatas_to_add, local_chunk_ids_to_add)
                                        print(f"Added {len(local_chunks_to_add)} chunks from local book: {book_title}")
                        
                        # Query again for better answer
                        if additional_book_info:
                            print("Re-querying with local books for better answer...")
                            new_results = query_similar_documents(request.question, n_results=10)
                            
                            if new_results.get("documents") and new_results["documents"][0]:
                                # Get best chunks including new local content
                                new_context_texts = []
                                
                                for i in range(min(5, len(new_results["documents"][0]))):
                                    doc_content = new_results["documents"][0][i]
                                    doc_metadata = new_results["metadatas"][0][i]
                                    
                                    # Prefer local content for better answers
                                    if doc_metadata.get("source_type") == "local_file":
                                        new_context_texts.append(doc_content)
                                        print(f"  ✓ Using local content from: {doc_metadata.get('book_id')}")
                                
                                # If we found good local content, re-generate answer
                                if new_context_texts:
                                    combined_context = "\n\n---\n\n".join(new_context_texts)
                                    new_prompt = f"Korisničko pitanje: {request.question}\n\nRelevantni odlomci iz knjiga:\n{combined_context}\n\nOdgovori na pitanje koristeći SAMO informacije iz dostavljenih odlomaka. Ako informacije nisu dovoljne, navedi to."
                                    
                                    new_response = client.chat.completions.create(
                                        model="gpt-3.5-turbo",
                                        messages=[
                                            {"role": "system", "content": "Ti si povijesni asistent. Odgovaraj samo na temelju dostavljenog konteksta. Ako odgovor nije u kontekstu, reci da ne možeš odgovoriti."},
                                            {"role": "user", "content": new_prompt}
                                        ],
                                        temperature=0.2
                                    )
                                    
                                    new_answer = new_response.choices[0].message.content.strip()
                                    
                                    # If new answer is better, use it
                                    if not any(phrase in new_answer.lower() for phrase in insufficient_answers):
                                        final_answer = new_answer
                                        book_info_map.update(additional_book_info)
                                        print("Using improved answer from local books!")
            except Exception as e:
                print(f"Error in local books fallback for insufficient answer: {e}")
        
    except Exception as e:
        final_answer = f"Greška u generiranju konačnog odgovora: {str(e)}"
        print(f"Error generating final LLM answer: {e}")


    # 7. Priprema source_documents za odgovor
    # Jedinstveni izvori na temelju book_id
    unique_source_docs = {}
    for doc in retrieved_documents:
        book_id = doc["metadata"].get("book_id")
        if book_id and book_id not in unique_source_docs:
            # Try to get book info from current map first
            book_info = book_info_map.get(book_id, {})
            
            # If not in current map, try to extract from metadata or use defaults
            if not book_info:
                book_title = doc["metadata"].get("title", "Historical Document")
                book_info = {
                    "title": book_title,
                    "link": f"https://archive.org/details/{book_id}" if book_id else "#"
                }
            
            unique_source_docs[book_id] = {
                "document_id": book_id,
                "title": book_info.get("title", "N/A"),
                "link": book_info.get("link", "#"),
                "content": doc["content"], # Možeš uključiti samo dio ili najbolje matchani chunk
                "score": doc.get("score", 0.0)
            }
    
    # Konvertiraj dictionary u listu
    source_documents_for_response = list(unique_source_docs.values())

    return AIResponse(
        answer=final_answer,
        source_documents=source_documents_for_response
    )