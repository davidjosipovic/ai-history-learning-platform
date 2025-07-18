import re
from typing import List, Dict

def chunk_text(text: str, chunk_size: int = 500) -> List[str]:
    """
    Split text into chunks of approximately chunk_size characters, on sentence boundaries if possible.
    """
    # Split by sentence
    sentences = re.split(r'(?<=[.!?]) +', text)
    chunks = []
    current_chunk = ''
    for sentence in sentences:
        if len(current_chunk) + len(sentence) < chunk_size:
            current_chunk += ' ' + sentence if current_chunk else sentence
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks
