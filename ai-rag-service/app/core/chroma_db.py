
import chromadb
from chromadb.config import Settings
from typing import List
import os
from sentence_transformers import SentenceTransformer

# Set up ChromaDB client and collection
CHROMA_DB_DIR = os.path.join(os.path.dirname(__file__), '../../chroma_db')

client = chromadb.Client(Settings(
    persist_directory=CHROMA_DB_DIR,
    anonymized_telemetry=False
))


# You can use the default collection or create a new one for each book or topic
COLLECTION_NAME = "internet_archive_books"
collection = client.get_or_create_collection(COLLECTION_NAME)

# Load SentenceTransformer model (all-MiniLM-L6-v2 is fast and good for general use)
_embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

def embed_texts(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a list of texts using SentenceTransformers."""
    return _embedding_model.encode(texts, show_progress_bar=False).tolist()

# Example: Add documents with embeddings (to be used in your pipeline)

def add_documents_with_embeddings(docs: List[str], metadatas: List[dict], ids: List[str], embedding_fn=embed_texts):
    collection.add(
        documents=docs,
        metadatas=metadatas,
        ids=ids,
        embeddings=embedding_fn(docs) if embedding_fn else None
    )

# Example: Query similar documents

def query_similar_documents(query: str, n_results: int = 3, embedding_fn=embed_texts):
    return collection.query(
        query_texts=[query],
        n_results=n_results
    )
