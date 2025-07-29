import re
from typing import List, Dict, Optional, Tuple
from enum import Enum

class ChunkStrategy(Enum):
    """Different chunking strategies for different types of content."""
    SENTENCE_BASED = "sentence"
    PARAGRAPH_BASED = "paragraph"
    SEMANTIC_BASED = "semantic"
    SLIDING_WINDOW = "sliding"
    ADAPTIVE = "adaptive"

def chunk_text(text: str, chunk_size: int = 500, strategy: ChunkStrategy = ChunkStrategy.ADAPTIVE, overlap: int = 50) -> List[str]:
    """
    Advanced text chunking with multiple strategies.
    
    Args:
        text: Input text to chunk
        chunk_size: Target size for each chunk (in characters)
        strategy: Chunking strategy to use
        overlap: Number of characters to overlap between chunks (for sliding window)
    
    Returns:
        List of text chunks
    """
    if not text or not text.strip():
        return []
    
    # Clean and normalize text
    text = clean_text(text)
    
    try:
        if strategy == ChunkStrategy.SENTENCE_BASED:
            return chunk_by_sentences(text, chunk_size)
        elif strategy == ChunkStrategy.PARAGRAPH_BASED:
            return chunk_by_paragraphs(text, chunk_size)
        elif strategy == ChunkStrategy.SEMANTIC_BASED:
            return chunk_by_semantic_breaks(text, chunk_size)
        elif strategy == ChunkStrategy.SLIDING_WINDOW:
            return chunk_with_sliding_window(text, chunk_size, overlap)
        elif strategy == ChunkStrategy.ADAPTIVE:
            return chunk_adaptive(text, chunk_size)
        else:
            return chunk_by_sentences(text, chunk_size)  # fallback
    except Exception as e:
        print(f"Error in chunking strategy {strategy.value}: {e}")
        # Fallback to simple character-based chunking
        return simple_character_chunk(text, chunk_size)

def clean_text(text: str) -> str:
    """Clean and normalize text before chunking."""
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    # Fix common OCR errors and formatting issues
    text = re.sub(r'([.!?])\s*([A-Z])', r'\1 \2', text)
    # Ensure proper sentence endings
    text = re.sub(r'([.!?])([A-Za-z])', r'\1 \2', text)
    return text.strip()

def chunk_by_sentences(text: str, chunk_size: int) -> List[str]:
    """Original sentence-based chunking with improvements."""
    # Fixed sentence splitting pattern - using simpler approach to avoid lookbehind issues
    # Split on sentence endings followed by whitespace and capital letter
    sentences = re.split(r'([.!?]+)\s+(?=[A-Z])', text)
    
    # Rejoin sentence endings with their sentences
    processed_sentences = []
    for i in range(0, len(sentences), 2):
        if i + 1 < len(sentences):
            # Combine sentence with its ending punctuation
            sentence = sentences[i] + sentences[i + 1]
        else:
            sentence = sentences[i]
        
        sentence = sentence.strip()
        if sentence:
            processed_sentences.append(sentence)
    
    chunks = []
    current_chunk = ''
    
    for sentence in processed_sentences:
        if not sentence:
            continue
            
        # Check if adding this sentence would exceed chunk size
        potential_chunk = current_chunk + ' ' + sentence if current_chunk else sentence
        
        if len(potential_chunk) <= chunk_size:
            current_chunk = potential_chunk
        else:
            # If current chunk is not empty, save it
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            # If single sentence is too long, split it further
            if len(sentence) > chunk_size:
                sub_chunks = split_long_sentence(sentence, chunk_size)
                chunks.extend(sub_chunks[:-1])  # Add all but last
                current_chunk = sub_chunks[-1] if sub_chunks else ""
            else:
                current_chunk = sentence
    
    if current_chunk and current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return [chunk for chunk in chunks if chunk.strip()]

def chunk_by_paragraphs(text: str, chunk_size: int) -> List[str]:
    """Chunk by paragraphs, combining small ones and splitting large ones."""
    paragraphs = re.split(r'\n\s*\n', text)
    chunks = []
    current_chunk = ''
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
            
        if len(current_chunk) + len(para) + 2 <= chunk_size:  # +2 for \n\n
            current_chunk = current_chunk + '\n\n' + para if current_chunk else para
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            # If paragraph is too long, split by sentences
            if len(para) > chunk_size:
                para_chunks = chunk_by_sentences(para, chunk_size)
                chunks.extend(para_chunks[:-1])
                current_chunk = para_chunks[-1] if para_chunks else ""
            else:
                current_chunk = para
    
    if current_chunk and current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return [chunk for chunk in chunks if chunk.strip()]

def chunk_by_semantic_breaks(text: str, chunk_size: int) -> List[str]:
    """Chunk based on semantic breaks (topic changes, dialogue, etc.)."""
    # Look for semantic indicators - using simpler patterns to avoid regex issues
    semantic_breaks = [
        r'\nChapter\s+\d+',        # Chapter breaks
        r'\n\s*\*\s*\*\s*\*',     # Section breaks
        r'\n\s*---+',             # Horizontal rules
        r'"\s*\n\s*"',            # Dialogue breaks
        r'\n\s*\d+\.\s+',         # Numbered lists
        r'\n\s*[IVX]+\.\s+',      # Roman numerals
    ]
    
    # Find potential break points
    break_points = [0]
    for pattern in semantic_breaks:
        try:
            matches = re.finditer(pattern, text)
            for match in matches:
                break_points.append(match.start())
        except re.error:
            # Skip problematic patterns
            continue
    
    break_points.append(len(text))
    break_points = sorted(set(break_points))
    
    # Create chunks respecting semantic breaks
    chunks = []
    for i in range(len(break_points) - 1):
        segment = text[break_points[i]:break_points[i + 1]].strip()
        if not segment:
            continue
            
        if len(segment) <= chunk_size:
            chunks.append(segment)
        else:
            # If segment is too long, fall back to sentence chunking
            sub_chunks = chunk_by_sentences(segment, chunk_size)
            chunks.extend(sub_chunks)
    
    return [chunk for chunk in chunks if chunk.strip()]

def chunk_with_sliding_window(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Create overlapping chunks using sliding window approach."""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        
        # Try to end at sentence boundary
        if end < len(text):
            last_sentence_end = max(
                chunk.rfind('.'),
                chunk.rfind('!'),
                chunk.rfind('?')
            )
            if last_sentence_end > chunk_size * 0.7:  # At least 70% of chunk size
                chunk = chunk[:last_sentence_end + 1]
                end = start + last_sentence_end + 1
        
        chunks.append(chunk.strip())
        
        if end >= len(text):
            break
            
        # Move start position with overlap
        start = end - overlap
    
    return [chunk for chunk in chunks if chunk.strip()]

def chunk_adaptive(text: str, chunk_size: int) -> List[str]:
    """Adaptive chunking that chooses the best strategy based on text characteristics."""
    # Analyze text characteristics
    paragraph_count = len(re.split(r'\n\s*\n', text))
    sentence_count = len(re.split(r'[.!?]+', text))
    avg_paragraph_length = len(text) / max(paragraph_count, 1)
    avg_sentence_length = len(text) / max(sentence_count, 1)
    
    # Choose strategy based on characteristics
    if paragraph_count > 3 and avg_paragraph_length < chunk_size * 0.8:
        # Good paragraph structure
        return chunk_by_paragraphs(text, chunk_size)
    elif avg_sentence_length < chunk_size * 0.3:
        # Short sentences, use sliding window for better context
        return chunk_with_sliding_window(text, chunk_size, overlap=50)
    elif has_semantic_structure(text):
        # Text has clear structure
        return chunk_by_semantic_breaks(text, chunk_size)
    else:
        # Default to improved sentence chunking
        return chunk_by_sentences(text, chunk_size)

def has_semantic_structure(text: str) -> bool:
    """Check if text has clear semantic structure."""
    structure_indicators = [
        r'Chapter\s+\d+',
        r'\n\s*\d+\.\s+',
        r'\n\s*[A-Z][A-Z\s]+\n',  # ALL CAPS headings
        r'\n\s*\*\s*\*\s*\*',
    ]
    
    indicator_count = 0
    for pattern in structure_indicators:
        if re.search(pattern, text):
            indicator_count += 1
    
    return indicator_count >= 2

def split_long_sentence(sentence: str, max_size: int) -> List[str]:
    """Split a sentence that's too long into smaller parts."""
    if len(sentence) <= max_size:
        return [sentence]
    
    # Try to split on commas, semicolons, or conjunctions
    split_patterns = [r',\s+', r';\s+', r'\s+and\s+', r'\s+but\s+', r'\s+or\s+']
    
    for pattern in split_patterns:
        parts = re.split(pattern, sentence)
        if len(parts) > 1:
            chunks = []
            current = ""
            for part in parts:
                if len(current + part) <= max_size:
                    current = current + part if not current else current + ", " + part
                else:
                    if current:
                        chunks.append(current.strip())
                    current = part
            if current:
                chunks.append(current.strip())
            
            if all(len(chunk) <= max_size for chunk in chunks):
                return chunks
    
    # Last resort: split by character count
    chunks = []
    for i in range(0, len(sentence), max_size):
        chunks.append(sentence[i:i + max_size])
    
    return chunks

def analyze_chunking_quality(chunks: List[str], original_text: str) -> Dict[str, float]:
    """Analyze the quality of chunking results."""
    if not chunks:
        return {"error": "No chunks produced"}
    
    chunk_lengths = [len(chunk) for chunk in chunks]
    
    metrics = {
        "total_chunks": len(chunks),
        "avg_chunk_length": sum(chunk_lengths) / len(chunk_lengths),
        "min_chunk_length": min(chunk_lengths),
        "max_chunk_length": max(chunk_lengths),
        "length_std_dev": (sum((x - sum(chunk_lengths) / len(chunk_lengths)) ** 2 for x in chunk_lengths) / len(chunk_lengths)) ** 0.5,
        "coverage": sum(chunk_lengths) / len(original_text),  # Should be close to 1.0
        "empty_chunks": sum(1 for chunk in chunks if not chunk.strip()),
    }
    
    return metrics

def get_optimal_chunk_size(text: str, target_chunks: int = None, max_chunk_size: int = 1000) -> int:
    """Determine optimal chunk size based on text characteristics."""
    text_length = len(text)
    
    if target_chunks:
        # Calculate size to achieve target number of chunks
        estimated_size = text_length // target_chunks
        return min(estimated_size, max_chunk_size)
    
    # Default heuristics based on text length
    if text_length < 2000:
        return min(500, text_length // 2)
    elif text_length < 10000:
        return 800
    else:
        return max_chunk_size

def simple_character_chunk(text: str, chunk_size: int) -> List[str]:
    """Simple fallback chunking by character count with word boundary respect."""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        if end >= len(text):
            # Last chunk
            chunks.append(text[start:].strip())
            break
        
        # Try to find a good break point (space, punctuation)
        break_point = end
        for i in range(end, max(start, end - 100), -1):
            if text[i] in ' \n\t.!?;,':
                break_point = i + 1
                break
        
        chunk = text[start:break_point].strip()
        if chunk:
            chunks.append(chunk)
        
        start = break_point
    
    return [chunk for chunk in chunks if chunk.strip()]
