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


def add_documents_with_embeddings(docs: List[str], metadatas: List[Dict], ids: List[str]):
    """
    Adds documents to the ChromaDB collection.
    Automatically generates embeddings using the collection's defined embedding function.
    Handles existing IDs by attempting to update.
    """
    collection = get_or_create_collection() # Get the collection instance
    if collection is None:
        print("ERROR: Collection not available. Cannot add documents.")
        return

    try:
        # ChromaDB `add` can handle updates by attempting to add an existing ID.
        # It will either add a new document or replace an existing one.
        # However, for explicit updates, `upsert` is more clear.
        # Let's use `upsert` for explicit control over updates.
        
        # Split into new and existing IDs to use `add` for new and `upsert` for existing,
        # or simply use `upsert` for all if you want to update on every call.
        
        # Simple upsert for all (will add if not exists, update if exists)
        # Note: If your collection has an embedding function, you don't need to pass 'embeddings' here.
        collection.upsert(
            documents=docs,
            metadatas=metadatas,
            ids=ids
        )
        print(f"Successfully added/updated {len(docs)} documents to ChromaDB.")
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
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            include=['documents', 'metadatas', 'distances'] # Explicitly request what you need
        )
        # ChromaDB's query method returns results in a specific format:
        # {'ids': [[]], 'embeddings': [[]], 'documents': [[]], 'metadatas': [[]], 'distances': [[]]}
        # The inner lists correspond to query_texts, so we usually take the first element if querying with one text.
        
        return results
    except Exception as e:
        print(f"ERROR: Failed to query ChromaDB: {e}")
        return {"ids": [], "embeddings": [], "documents": [], "metadatas": [], "distances": []}

# --- Testni blok ---
if __name__ == "__main__":
    # Očistite ChromaDB za svježi start tijekom testiranja
    # OPREZ: Ovo će obrisati sve podatke u kolekciji!
    # client = get_chroma_client()
    # if client:
    #     try:
    #         client.delete_collection(name="internet_archive_books")
    #         print("Existing collection 'internet_archive_books' deleted for fresh test.")
    #     except Exception as e:
    #         print(f"Could not delete collection (maybe it didn't exist): {e}")

    # Provjera inicijalizacije
    collection = get_or_create_collection()
    if collection:
        print(f"Current collection count: {collection.count()} documents.")

        # Primjer dodavanja dokumenata
        test_docs = [
            "Prvi svjetski rat trajao je od 1914. do 1918. godine.",
            "Bitka kod Staljingrada bila je prekretnica u Drugom svjetskom ratu.",
            "Napoleon Bonaparte je bio francuski vojskovođa i car.",
            "Rimsko Carstvo je palo 476. godine nakon Krista.",
            "Industrijska revolucija donijela je velike promjene u društvu."
        ]
        test_metadatas = [
            {"topic": "WW1", "year": 1914},
            {"topic": "WW2", "year": 1942},
            {"topic": "Napoleon", "year": 1804},
            {"topic": "Roman Empire", "year": 476},
            {"topic": "Industrial Revolution", "year": 1760}
        ]
        test_ids = [f"doc{i}" for i in range(len(test_docs))]

        print(f"\nAdding {len(test_docs)} test documents...")
        add_documents_with_embeddings(test_docs, test_metadatas, test_ids)
        print(f"Collection count after adding: {collection.count()} documents.")

        # Primjer upita
        test_query = "Tko je bio car Napoleon?"
        print(f"\nQuerying for: '{test_query}'")
        results = query_similar_documents(test_query, n_results=1)

        print("\nQuery Results:")
        if results.get("documents") and results["documents"][0]:
            for i in range(len(results["documents"][0])):
                doc_content = results["documents"][0][i]
                doc_metadata = results["metadatas"][0][i]
                doc_distance = results["distances"][0][i] if results.get("distances") and results["distances"][0] else "N/A"
                print(f"  Result {i+1}:")
                print(f"    Content: {doc_content}")
                print(f"    Metadata: {doc_metadata}")
                print(f"    Distance (score): {doc_distance}")
        else:
            print("  No similar documents found.")

        test_query_2 = "Kada je počeo Prvi svjetski rat?"
        print(f"\nQuerying for: '{test_query_2}'")
        results_2 = query_similar_documents(test_query_2, n_results=1)
        if results_2.get("documents") and results_2["documents"][0]:
            print(f"  Result: {results_2['documents'][0][0]}")
        else:
            print("  No similar documents found.")

    else:
        print("ChromaDB client could not be initialized. Test aborted.")