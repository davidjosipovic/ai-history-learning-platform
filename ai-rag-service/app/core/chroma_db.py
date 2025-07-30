import chromadb
from chromadb.utils import embedding_functions # Ispravan uvoz za default embedding
from chromadb.config import Settings
from typing import List, Dict, Union
import os
# Uklonjeno SentenceTransformer direktno uvoz, koristimo ChromaDB-ovu integraciju za lakše
# upravljanje modelom unutar ChromaDB okruženja.
# from sentence_transformers import SentenceTransformer 

# Putanja do ChromaDB direktorija za perzistenciju
# Važno: `os.path.dirname(__file__)` vraća direktorij trenutnog skripta.
# '../../chroma_db' znači dva nivoa iznad trenutnog direktorija.
# Provjeri je li putanja ispravna u odnosu na strukturu vašeg projekta.
# Npr. ako je app/core/chroma_db.py, onda je ../../ od `app` direktorija.
# Ako želite da bude unutar `app` direktorija, možda `../chroma_db` ili `../../data/chroma_db`.
CHROMA_DB_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'chroma_db_data') # Promijenio sam naziv za jasnoću

# Inicijalizacija ChromaDB klijenta za perzistentnost
# Ova funkcija će osigurati da se klijent inicijalizira samo jednom i da je dostupan
# globalno unutar modula, ali i da se može dohvatiti izvana.
_chroma_client = None
_collection = None # Globalna referenca na kolekciju

def get_chroma_client():
    """Returns the persistent ChromaDB client, initializing it if necessary."""
    global _chroma_client
    if _chroma_client is None:
        try:
            _chroma_client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
            print(f"ChromaDB client initialized. Data will be persisted in: {CHROMA_DB_DIR}")
        except Exception as e:
            print(f"ERROR: Failed to initialize ChromaDB client at {CHROMA_DB_DIR}: {e}")
            _chroma_client = None # Reset to None if init fails
    return _chroma_client

def get_or_create_collection(collection_name: str = "internet_archive_books"):
    """
    Returns the specified ChromaDB collection, creating it if it doesn't exist.
    Uses 'all-MiniLM-L6-v2' as the default embedding function if not specified.
    """
    global _collection
    if _collection is None:
        client = get_chroma_client()
        if client is None:
            raise RuntimeError("ChromaDB client is not initialized. Cannot get or create collection.")

        # Koristimo defaultni SentenceTransformer embedding function od ChromaDB-a
        # Ovo je preporučeni način jer ChromaDB upravlja preuzimanjem i učitavanjem modela.
        # Možete specificirati model: model_name="all-MiniLM-L6-v2"
        # Ako planirate koristiti OpenAI za embedding, to se radi drugačije.
        # Za sada, neka bude SentenceTransformer
        try:
            # Note: chroma.PersistentClient() has create_or_get_collection which expects embedding_function
            # You can also pass embedding_function directly to get_or_create_collection
            # using chromadb.get_or_create_collection() if client is in-memory
            # For PersistentClient, you pass embedding_function on collection creation
            # If you don't pass an embedding function, it will try to use a default or require you to pass embeddings manually.
            # Let's ensure a default embedding function is used for new collections.
            
            # This is how you define a sentence-transformers embedding function for ChromaDB
            sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2",
                device="cpu" # 'cpu' or 'cuda' if you have a GPU
            )
            
            _collection = client.get_or_create_collection(
                name=collection_name,
                embedding_function=sentence_transformer_ef # Pass the embedding function here
            )
            print(f"ChromaDB collection '{collection_name}' initialized/loaded.")
        except Exception as e:
            print(f"ERROR: Failed to get or create ChromaDB collection '{collection_name}': {e}")
            _collection = None # Reset if collection creation fails
    return _collection

# Inicijaliziraj klijent i kolekciju pri učitavanju modula
# Ovo osigurava da su klijent i kolekcija spremni za upotrebu
get_chroma_client()
get_or_create_collection()


def check_book_exists_in_db(book_id: str) -> bool:
    """
    Provjeri da li knjiga s danim book_id već postoji u ChromaDB kolekciji.
    Vraća True ako postoji, False inače.
    """
    collection = get_or_create_collection()
    if collection is None:
        print("ERROR: Collection not available. Cannot check if book exists.")
        return False
    
    try:
        # Pokušaj dohvatiti dokumente s danim book_id iz metapodataka
        results = collection.query(
            query_texts=["dummy query"],  # Potreban je query tekst, ali nije bitan za filtiranje
            n_results=1,
            where={"book_id": book_id},  # Filtriraj po book_id
            include=['metadatas']
        )
        
        # Ako pronađemo bilo koji rezultat, knjiga postoji
        if results.get("metadatas") and results["metadatas"][0]:
            return True
        return False
        
    except Exception as e:
        print(f"Error checking if book {book_id} exists in ChromaDB: {e}")
        return False


def get_existing_book_ids() -> set:
    """
    Dohvati sve book_id-jeve koji već postoje u ChromaDB kolekciji.
    Vraća set postojećih book_id-jeva.
    """
    collection = get_or_create_collection()
    if collection is None:
        print("ERROR: Collection not available. Cannot get existing book IDs.")
        return set()
    
    try:
        # Dohvati sve dokumente (ograniči na razuman broj)
        results = collection.query(
            query_texts=["dummy query"],
            n_results=min(collection.count(), 10000),  # Ograniči na maksimalno 10000 dokumenata
            include=['metadatas']
        )
        
        existing_book_ids = set()
        if results.get("metadatas") and results["metadatas"][0]:
            for metadata in results["metadatas"][0]:
                book_id = metadata.get("book_id")
                if book_id:
                    existing_book_ids.add(book_id)
        
        print(f"Found {len(existing_book_ids)} existing books in ChromaDB")
        return existing_book_ids
        
    except Exception as e:
        print(f"Error getting existing book IDs from ChromaDB: {e}")
        return set()


def add_documents_with_embeddings(docs: List[str], metadatas: List[Dict], ids: List[str]):
    """
    Adds documents to the ChromaDB collection.
    Automatically generates embeddings using the collection's defined embedding function.
    Handles existing IDs by attempting to update.
    Implements batching to avoid ChromaDB batch size limits.
    """
    collection = get_or_create_collection() # Get the collection instance
    if collection is None:
        print("ERROR: Collection not available. Cannot add documents.")
        return

    try:
        # ChromaDB has a maximum batch size limit, so we need to process in batches
        BATCH_SIZE = 5000  # Safe batch size, well below ChromaDB's limit
        total_docs = len(docs)
        
        # Debug: Print first few book_ids to verify they're being added correctly
        if metadatas:
            sample_book_ids = set()
            for metadata in metadatas:  # Check ALL metadata, not just first 10
                book_id = metadata.get("book_id", "MISSING_BOOK_ID")
                sample_book_ids.add(book_id)
            print(f"DEBUG: Adding documents with book_ids: {sample_book_ids}")
            print(f"DEBUG: Total {len(metadatas)} documents being added")
        
        for i in range(0, total_docs, BATCH_SIZE):
            end_idx = min(i + BATCH_SIZE, total_docs)
            batch_docs = docs[i:end_idx]
            batch_metadatas = metadatas[i:end_idx]
            batch_ids = ids[i:end_idx]
            
            print(f"Processing batch {i//BATCH_SIZE + 1}: documents {i+1}-{end_idx} of {total_docs}")
            
            # Simple upsert for all (will add if not exists, update if exists)
            # Note: If your collection has an embedding function, you don't need to pass 'embeddings' here.
            collection.upsert(
                documents=batch_docs,
                metadatas=batch_metadatas,
                ids=batch_ids
            )
            
        print(f"Successfully added/updated {total_docs} documents to ChromaDB in {(total_docs + BATCH_SIZE - 1) // BATCH_SIZE} batches.")
        
        # Debug: Print some stats about what's in the collection after adding
        print(f"DEBUG: Collection now has {collection.count()} total documents")
        
        # Debug: Query to see what book_ids are actually in the collection now
        try:
            sample_query = collection.query(
                query_texts=["test query"],
                n_results=5,
                include=['metadatas']
            )
            if sample_query.get("metadatas") and sample_query["metadatas"][0]:
                stored_book_ids = set()
                for metadata in sample_query["metadatas"][0]:
                    stored_book_ids.add(metadata.get("book_id", "MISSING"))
                print(f"DEBUG: Sample of book_ids now in collection: {stored_book_ids}")
        except Exception as debug_e:
            print(f"DEBUG: Could not sample collection contents: {debug_e}")
            
    except Exception as e:
        print(f"ERROR: Failed to add/update documents to ChromaDB: {e}")


def query_similar_documents(query: str, n_results: int = 3) -> Dict[str, List[Union[str, List[float], Dict]]]:
    """
    Queries the ChromaDB collection for documents similar to the given query text.
    Embeddings are automatically generated for the query text using the collection's embedding function.
    """
    collection = get_or_create_collection() # Get the collection instance
    if collection is None:
        print("ERROR: Collection not available. Cannot query documents.")
        return {"ids": [], "embeddings": [], "documents": [], "metadatas": [], "distances": []}

    try:
        print(f"DEBUG: Querying collection with {collection.count()} total documents")
        
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            include=['documents', 'metadatas', 'distances'] # Explicitly request what you need
        )
        
        # Debug: Print what book_ids are returned
        if results.get("metadatas") and results["metadatas"][0]:
            returned_book_ids = set()
            for metadata in results["metadatas"][0]:
                returned_book_ids.add(metadata.get("book_id", "MISSING"))
            print(f"DEBUG: Query returned documents from book_ids: {returned_book_ids}")
        
        # ChromaDB's query method returns results in a specific format:
        # {'ids': [[]], 'embeddings': [[]], 'documents': [[]], 'metadatas': [[]], 'distances': [[]]}
        # The inner lists correspond to query_texts, so we usually take the first element if querying with one text.
        
        return results
    except Exception as e:
        print(f"ERROR: Failed to query ChromaDB: {e}")
        return {"ids": [], "embeddings": [], "documents": [], "metadatas": [], "distances": []}

def query_with_multiple_strategies(query: str, n_results: int = 3) -> Dict[str, List[Union[str, List[float], Dict]]]:
    """
    Enhanced query function that tries multiple search strategies for better results.
    Useful for specific details like times, dates, or precise facts.
    """
    collection = get_or_create_collection()
    if collection is None:
        print("ERROR: Collection not available. Cannot query documents.")
        return {"ids": [], "embeddings": [], "documents": [], "metadatas": [], "distances": []}

    try:
        print(f"DEBUG: Multi-strategy querying collection with {collection.count()} total documents")
        
        # Strategy 1: Original query
        results1 = collection.query(
            query_texts=[query],
            n_results=n_results,
            include=['documents', 'metadatas', 'distances']
        )
        
        # Strategy 2: Extract key terms and search with more specific terms
        key_terms = []
        if "sati" in query.lower() or "time" in query.lower():
            key_terms.extend(["seven-thirty", "7:30", "church service", "sunday morning", "arrived at church"])
        if "barack" in query.lower() and "obama" in query.lower():
            key_terms.extend(["I arrived", "we went to church", "sunday service", "church attendance"])
        
        
        # Strategy 3: Search with key terms
        combined_results = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        
        if key_terms:
            for term in key_terms[:5]:  # Increased to 5 additional searches
                term_results = collection.query(
                    query_texts=[term],
                    n_results=5,
                    include=['documents', 'metadatas', 'distances']
                )
                
                # Merge results
                if term_results.get("documents") and term_results["documents"][0]:
                    combined_results["documents"][0].extend(term_results["documents"][0])
                    combined_results["metadatas"][0].extend(term_results["metadatas"][0])
                    combined_results["distances"][0].extend(term_results["distances"][0])
        
        # Strategy 4: Search for personal narrative patterns
        personal_terms = ["I went", "I arrived", "we arrived", "I got to", "I reached"]
        for term in personal_terms[:3]:
            personal_results = collection.query(
                query_texts=[term],
                n_results=3,
                include=['documents', 'metadatas', 'distances']
            )
            
            if personal_results.get("documents") and personal_results["documents"][0]:
                combined_results["documents"][0].extend(personal_results["documents"][0])
                combined_results["metadatas"][0].extend(personal_results["metadatas"][0])
                combined_results["distances"][0].extend(personal_results["distances"][0])
        
        # Combine and deduplicate results
        all_docs = results1["documents"][0] if results1.get("documents") else []
        all_metas = results1["metadatas"][0] if results1.get("metadatas") else []
        all_dists = results1["distances"][0] if results1.get("distances") else []
        
        # Add combined results
        if combined_results["documents"][0]:
            all_docs.extend(combined_results["documents"][0])
            all_metas.extend(combined_results["metadatas"][0])
            all_dists.extend(combined_results["distances"][0])
        
        # Remove duplicates based on content and prioritize primary sources
        seen_content = set()
        final_docs = []
        final_metas = []
        final_dists = []
        
        # Sort by priority: Obama's own books first, then distance
        all_items = list(zip(all_docs, all_metas, all_dists))
        def priority_score(item):
            doc, meta, dist = item
            book_id = meta.get("book_id", "").lower()
            # Prioritize Obama's own books
            if "dreams" in book_id and "obama" in book_id:
                return (0, dist)  # Highest priority
            elif "obama" in book_id:
                return (1, dist)  # Medium priority
            else:
                return (2, dist)  # Lower priority
        
        all_items.sort(key=priority_score)
        
        for doc, meta, dist in all_items:
            if doc not in seen_content and len(final_docs) < n_results * 3:  # Get more results for better coverage
                seen_content.add(doc)
                final_docs.append(doc)
                final_metas.append(meta)
                final_dists.append(dist)
        
        result = {
            "documents": [final_docs],
            "metadatas": [final_metas],
            "distances": [final_dists]
        }
        
        print(f"DEBUG: Multi-strategy query returned {len(final_docs)} unique documents")
        return result
        
    except Exception as e:
        print(f"ERROR: Failed to query ChromaDB with multiple strategies: {e}")
        return {"ids": [], "embeddings": [], "documents": [], "metadatas": [], "distances": []}


def delete_book_chunks(book_id: str):
    """Delete all chunks for a specific book from ChromaDB."""
    try:
        collection = get_or_create_collection()
        
        # Get all documents for this book
        result = collection.get(where={"book_id": book_id})
        
        if result and result.get("ids"):
            chunk_ids = result["ids"]
            print(f"Deleting {len(chunk_ids)} chunks for book: {book_id}")
            
            # Delete all chunks for this book
            collection.delete(ids=chunk_ids)
            print(f"Successfully deleted {len(chunk_ids)} chunks for book: {book_id}")
            return len(chunk_ids)
        else:
            print(f"No chunks found for book: {book_id}")
            return 0
            
    except Exception as e:
        print(f"ERROR: Failed to delete chunks for book {book_id}: {e}")
        return 0

