from fastapi import APIRouter, HTTPException
from app.schemas.ai import AIRequest, AIResponse
import openai
import os
from dotenv import load_dotenv
from app.core.chroma_db import query_similar_documents, get_existing_book_ids
from app.core.internet_archive import (
    generate_keywords_from_question,
    build_internet_archive_query_string,
    search_internet_archive_advanced
)
from app.core.internet_archive_downloader import InternetArchiveDownloader

# Initialize OpenAI client
load_dotenv()
try:
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception as e:
    print(f"ERROR: Could not initialize OpenAI client. Please check OPENAI_API_KEY: {e}")
    client = None

router = APIRouter()

def format_documents_for_response(retrieved_documents: list) -> list:
    """Format documents for the API response with proper links and titles."""
    source_docs = []
    
    for doc in retrieved_documents[:5]:  # Limit to top 5
        book_id = doc["metadata"].get("book_id", "unknown")
        book_title = doc["metadata"].get("title", book_id)
        chunk_index = doc["metadata"].get("chunk_index", 0)
        
        # Determine source type and create appropriate link
        if book_id.startswith("local_"):
            # Local book
            clean_title = book_title.replace("local_", "").replace("-", " ").replace("_", " ")
            link = f"📁 Lokalna knjiga: {clean_title}"
        else:
            # Internet Archive book
            link = f"https://archive.org/details/{book_id}"
        
        # Create document preview
        content_preview = doc["content"][:200] + "..." if len(doc["content"]) > 200 else doc["content"]
        
        source_docs.append({
            "title": book_title,
            "link": link,
            "content_preview": content_preview,
            "chunk_info": f"Odlomak {chunk_index + 1}",
            "relevance_score": round(1 - doc.get("score", 0), 3)  # Convert distance to relevance
        })
    
    return source_docs

def generate_answer_with_context(question: str, retrieved_documents: list) -> str:
    """Generate answer using OpenAI with the retrieved context."""
    if not client:
        return "OpenAI klijent nije inicijaliziran. Molimo provjerite OPENAI_API_KEY."
    
    # Prepare context from documents
    context_parts = []
    for i, doc in enumerate(retrieved_documents[:5]):
        book_title = doc["metadata"].get("title", "Nepoznata knjiga")
        content = doc["content"]
        context_parts.append(f"[Izvor {i+1} - {book_title}]:\n{content}")
    
    context = "\n\n".join(context_parts)
    
    # Create prompt
    prompt = f"""Odgovori na pitanje koristeći isključivo informacije iz priloženih izvora. 

PITANJE: {question}

DOSTUPNI IZVORI:
{context}

INSTRUKCIJE:
- Odgovori na hrvatskom jeziku
- Koristi samo informacije iz priloženih izvora
- Ako nema dovoljno informacija u izvorima, reci da nema dovoljno podataka
- Budi precizan i objektivan
- Navedi koje izvore koristiš u odgovoru

ODGOVOR:"""

    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "Ti si stručnjak za povijest koji odgovara na pitanja koristeći samo dane izvore."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.1
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Error generating answer: {e}")
        return f"Greška pri generiranju odgovora: {str(e)}"

@router.post("/", response_model=AIResponse)
async def ai_generate(request: AIRequest):
    """
    Main AI endpoint with simplified logic:
    1. Search ChromaDB first (local books)
    2. If not enough results, search Internet Archive
    3. Generate answer with available context
    """
    question = request.question
    print(f"🤔 Simple AI Query: {question}")
    
    try:
        # Step 1: Search ChromaDB for relevant chunks
        print("🔍 Searching ChromaDB...")
        results = query_similar_documents(question, n_results=10)
        
        # Process results into document format
        retrieved_documents = []
        
        if results.get("documents") and results["documents"][0]:
            documents = results["documents"][0]
            metadatas = results["metadatas"][0] if results.get("metadatas") else []
            distances = results["distances"][0] if results.get("distances") else []
            
            for i, (doc_content, doc_metadata, doc_distance) in enumerate(zip(documents, metadatas, distances)):
                if not doc_content or len(doc_content.strip()) < 20:
                    continue
                
                retrieved_documents.append({
                    "content": doc_content,
                    "metadata": doc_metadata,
                    "score": doc_distance
                })
        
        print(f"📊 Found {len(retrieved_documents)} relevant chunks in ChromaDB")
        
        # Check if the found documents are actually relevant to the question
        question_lower = question.lower()
        relevant_content_found = False
        
        # Simple relevance check - look for key terms from question in content
        question_keywords = [word.lower() for word in question.split() if len(word) > 3]
        
        for doc in retrieved_documents[:5]:  # Check top 5 documents
            content_lower = doc["content"].lower()
            # If at least one keyword from question appears in content, consider it relevant
            if any(keyword in content_lower for keyword in question_keywords):
                relevant_content_found = True
                break
        
        print(f"🎯 Relevant content found in ChromaDB: {relevant_content_found}")
        
        # Step 2: If not enough results OR no relevant content, search Internet Archive
        if len(retrieved_documents) < 3 or not relevant_content_found:
            print("📚 Searching Internet Archive for additional content...")
            
            try:
                # Generate search keywords
                keywords = generate_keywords_from_question(question)
                print(f"🔍 Keywords: {keywords}")
                
                # Search Internet Archive
                query_string = build_internet_archive_query_string(keywords)
                books = search_internet_archive_advanced(query_string, rows=3)
                
                if books:
                    print(f"📖 Found {len(books)} additional books")
                    
                    # Download and process top 2 books
                    downloader = InternetArchiveDownloader()
                    book_identifiers = [book.get("identifier") for book in books[:2]]
                    
                    book_texts = downloader.download_multiple_books(book_identifiers)
                    
                    # Add successful downloads to response info
                    for book_id, text in book_texts.items():
                        if text and len(text.strip()) > 100:
                            # Create a simple document from Internet Archive content
                            book_info = next((b for b in books if b.get("identifier") == book_id), {})
                            book_title = book_info.get("title", book_id)
                            
                            # Take first 1000 characters as a "chunk"
                            content_chunk = text[:1000]
                            
                            retrieved_documents.append({
                                "content": content_chunk,
                                "metadata": {
                                    "book_id": book_id,
                                    "title": book_title,
                                    "chunk_index": 0,
                                    "source_type": "internet_archive"
                                },
                                "score": 0.5  # Neutral relevance score
                            })
                
            except Exception as e:
                print(f"⚠️ Internet Archive search failed: {e}")
        
        # Step 3: Filter and rank documents by relevance
        if retrieved_documents:
            # Score documents based on keyword matches
            scored_documents = []
            
            for doc in retrieved_documents:
                content_lower = doc["content"].lower()
                title_lower = doc["metadata"].get("title", "").lower()
                
                # Calculate relevance score
                relevance_score = 0
                for keyword in question_keywords:
                    # Higher score for keyword in title
                    if keyword in title_lower:
                        relevance_score += 3
                    # Score for keyword in content
                    content_matches = content_lower.count(keyword)
                    relevance_score += content_matches
                
                # Only keep documents with some relevance
                if relevance_score > 0:
                    doc["relevance_score"] = relevance_score
                    scored_documents.append(doc)
            
            # Sort by relevance and keep top documents
            scored_documents.sort(key=lambda x: x["relevance_score"], reverse=True)
            retrieved_documents = scored_documents[:5]
            
            print(f"🎯 After relevance filtering: {len(retrieved_documents)} relevant documents")
        
        # Step 4: Generate answer with available context
        if not retrieved_documents:
            # If no relevant content found, try Internet Archive before giving up
            if not relevant_content_found:
                print("🌐 No relevant content in ChromaDB, trying Internet Archive...")
                
                try:
                    # Generate search keywords
                    keywords = generate_keywords_from_question(question)
                    print(f"🔍 Internet Archive keywords: {keywords}")
                    
                    # Search Internet Archive
                    query_string = build_internet_archive_query_string(keywords)
                    books = search_internet_archive_advanced(query_string, rows=3)
                    
                    if books:
                        print(f"📖 Found {len(books)} books on Internet Archive")
                        
                        # Download and process top 2 books
                        downloader = InternetArchiveDownloader()
                        book_identifiers = [book.get("identifier") for book in books[:2]]
                        
                        book_texts = downloader.download_multiple_books(book_identifiers)
                        
                        # Add successful downloads to retrieved_documents
                        for book_id, text in book_texts.items():
                            if text and len(text.strip()) > 100:
                                book_info = next((b for b in books if b.get("identifier") == book_id), {})
                                book_title = book_info.get("title", book_id)
                                
                                # Take first 1000 characters as a "chunk"
                                content_chunk = text[:1000]
                                
                                retrieved_documents.append({
                                    "content": content_chunk,
                                    "metadata": {
                                        "book_id": book_id,
                                        "title": book_title,
                                        "chunk_index": 0,
                                        "source_type": "internet_archive"
                                    },
                                    "score": 0.5,
                                    "relevance_score": 1  # Default relevance for IA content
                                })
                                
                        print(f"📥 Added {len([d for d in retrieved_documents if d['metadata'].get('source_type') == 'internet_archive'])} documents from Internet Archive")
                    
                except Exception as e:
                    print(f"⚠️ Internet Archive search failed: {e}")
            
            # Final check after Internet Archive attempt
            if not retrieved_documents:
                return AIResponse(
                    answer="Nažalost, nisam pronašao relevantne informacije za vaše pitanje ni u lokalnoj bazi ni na Internet Archive. Molimo pokušajte s drugim pitanjem ili dodajte više knjiga u bazu.",
                    sources=[]
                )
        
        print(f"✅ Generating answer with {len(retrieved_documents)} documents")
        
        # Generate answer
        answer = generate_answer_with_context(question, retrieved_documents)
        
        # Format sources for response
        source_documents = format_documents_for_response(retrieved_documents)
        
        return AIResponse(
            answer=answer,
            sources=source_documents
        )
        
    except Exception as e:
        print(f"❌ Error in AI processing: {e}")
        raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)}")

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "ai-rag-service"}
