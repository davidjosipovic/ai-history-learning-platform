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

# Pretpostavljam da su ove funkcije ispravno implementirane
from app.core.text_chunking import chunk_text 
from app.core.chroma_db import add_documents_with_embeddings, query_similar_documents, get_chroma_client # Dodana get_chroma_client

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
        return AIResponse(answer=f"Nije pronađena nijedna relevantna knjiga na Internet Archive za upit: '{' '.join(keywords)}'.")

    # Pripremamo sve chunkove iz svih knjiga za dodavanje u ChromaDB
    all_chunks_to_add = []
    all_metadatas_to_add = []
    all_chunk_ids_to_add = []
    
    # Lista za praćenje originalnih podataka o knjigama
    book_info_map = {} 

    # 3. Process each found book description for chunking and indexing
    for book in books:
        book_id = book.get("identifier", "")
        book_title = book.get("title", "N/A")
        book_desc = book.get("description", "")
        
        # Pohrani podatke o knjizi za kasnije
        book_info_map[book_id] = {
            "title": book_title,
            "link": f"https://archive.org/details/{book_id}" if book_id else ""
        }
        
        print(f"Processing book: {book_id} - '{book_title}' (Desc length: {len(book_desc) if book_desc else 0})")
        
        # Ako nema opisa, preskoči
        if not book_desc:
            print(f"Skipping {book_id}: No description available.")
            continue
        
        # Opis knjige je rijetko jako dug. Umjesto chunkinga, možda je bolje koristiti cijeli opis
        # kao jedan dokument, osim ako opisi nisu iznenađujuće dugi.
        # Primjer s chunkingom (ako je potrebno):
        chunks = chunk_text(book_desc) # Pretpostavljam da je chunk_text ispravan
        
        if not chunks:
            print(f"No chunks generated for {book_id}. Skipping.")
            continue

        for i, chunk in enumerate(chunks):
            chunk_id = f"{book_id}_chunk_{i}"
            metadata = {
                "book_id": book_id,
                "title": book_title,
                "chunk_index": i
            }
            all_chunks_to_add.append(chunk)
            all_metadatas_to_add.append(metadata)
            all_chunk_ids_to_add.append(chunk_id)
            
    if not all_chunks_to_add:
        return AIResponse(answer=f"Nijedan opis knjige nije bio relevantan ili dovoljno dug za obradu.")

    # 4. Add all collected chunks to ChromaDB (or update existing)
    print(f"Adding {len(all_chunks_to_add)} chunks to ChromaDB.")
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

    # 5. Find the MOST relevant chunks from CURRENT books only
    print(f"Querying ChromaDB for relevant chunks for question: '{request.question}'")
    # Get book IDs from current search to filter results
    current_book_ids = set(book_info_map.keys())
    print(f"Current book IDs: {current_book_ids}")
    
    try:
        # Query more results to filter for current books
        results = query_similar_documents(request.question, n_results=20) 
        
        retrieved_documents = []
        if results.get("documents") and results["documents"][0]:
            print(f"ChromaDB returned {len(results['documents'][0])} total chunks")
            
            # Filter to only include chunks from current books
            for i in range(len(results["documents"][0])):
                doc_content = results["documents"][0][i]
                doc_metadata = results["metadatas"][0][i]
                doc_distance = results["distances"][0][i] if results.get("distances") and results["distances"][0] else None
                
                book_id = doc_metadata.get("book_id", "unknown")
                
                # Only include chunks from books we just indexed
                if book_id in current_book_ids:
                    # Additional filtering: Skip obviously irrelevant content
                    content_lower = doc_content.lower()
                    
                    # Skip American letters and non-historical content
                    if any(term in content_lower for term in ["baraboo, wi", "cumberland gap", "american civil war", "hackett letters"]):
                        print(f"  ✗ Skipping irrelevant content from: {book_id}")
                        continue
                    
                    # Skip medical/scientific content unless it's historical
                    if any(term in content_lower for term in ["bone mineral density", "judo training", "high-school boys"]):
                        print(f"  ✗ Skipping non-historical content from: {book_id}")
                        continue
                    
                    chunk_index = doc_metadata.get("chunk_index", "unknown")
                    print(f"  ✓ Chunk {len(retrieved_documents)+1}: Book={book_id}, ChunkIndex={chunk_index}, Distance={doc_distance}")
                    print(f"    Content preview: {doc_content[:100]}...")
                    
                    retrieved_documents.append({
                        "content": doc_content,
                        "metadata": doc_metadata,
                        "score": doc_distance
                    })
                    
                    # Get all available chunks from current books, up to 5
                    if len(retrieved_documents) >= 5:
                        break
                else:
                    print(f"  ✗ Skipping chunk from old book: {book_id}")
            
            # If we have very few chunks, add ALL chunks from current books regardless of relevance
            if len(retrieved_documents) < 2:
                print(f"Only {len(retrieved_documents)} relevant chunks found. Adding all chunks from current books...")
                for i in range(len(results["documents"][0])):
                    doc_content = results["documents"][0][i]
                    doc_metadata = results["metadatas"][0][i]
                    doc_distance = results["distances"][0][i] if results.get("distances") and results["distances"][0] else None
                    book_id = doc_metadata.get("book_id", "unknown")
                    
                    if book_id in current_book_ids and not any(d["metadata"]["book_id"] == book_id and d["metadata"]["chunk_index"] == doc_metadata.get("chunk_index") for d in retrieved_documents):
                        # Apply same content filtering in fallback
                        content_lower = doc_content.lower()
                        if any(term in content_lower for term in ["baraboo, wi", "cumberland gap", "american civil war", "hackett letters", "bone mineral density", "judo training", "high-school boys"]):
                            print(f"  ✗ Skipping irrelevant fallback content from: {book_id}")
                            continue
                        
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
        return AIResponse(answer=f"Nije pronađen dovoljno relevantan kontekst u opisima knjiga za odgovor na vaše pitanje.")

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
    except Exception as e:
        final_answer = f"Greška u generiranju konačnog odgovora: {str(e)}"
        print(f"Error generating final LLM answer: {e}")


    # 7. Priprema source_documents za odgovor
    # Jedinstveni izvori na temelju book_id
    unique_source_docs = {}
    for doc in retrieved_documents:
        book_id = doc["metadata"].get("book_id")
        if book_id and book_id not in unique_source_docs:
            book_info = book_info_map.get(book_id, {})
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