import os
import json
from typing import List, Dict, Optional
from pathlib import Path

# Try to import PyMuPDF, handle gracefully if not available
try:
    import fitz  # PyMuPDF for PDF processing
    PYMUPDF_AVAILABLE = True
except ImportError:
    print("Warning: PyMuPDF (fitz) not available. PDF processing will be limited.")
    PYMUPDF_AVAILABLE = False

import docx  # python-docx for Word documents
import zipfile
import xml.etree.ElementTree as ET

def get_local_books_directory() -> str:
    """Returns the path to the local books directory."""
    current_dir = os.path.dirname(__file__)
    books_dir = os.path.join(current_dir, '..', '..', 'books')
    return os.path.abspath(books_dir)

def scan_local_books() -> List[Dict]:
    """
    Scans the local books directory and returns metadata for all found books.
    Supports PDF, DOCX, TXT, and EPUB files.
    """
    books_dir = get_local_books_directory()
    
    if not os.path.exists(books_dir):
        print(f"Local books directory not found: {books_dir}")
        return []
    
    supported_extensions = ['.pdf', '.docx', '.txt', '.epub']
    books = []
    
    # Only log directory path once per scan if verbose mode is requested
    if not hasattr(scan_local_books, '_suppress_logs'):
        print(f"Scanning local books directory: {books_dir}")
    
    for root, dirs, files in os.walk(books_dir):
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            if file_ext in supported_extensions:
                # Generate book metadata
                book_id = f"local_{os.path.splitext(file)[0]}"
                book_title = os.path.splitext(file)[0].replace('_', ' ').replace('-', ' ').title()
                
                book_metadata = {
                    "identifier": book_id,
                    "title": book_title,
                    "creator": "Local Collection",
                    "description": f"Local book: {file}",
                    "file_path": file_path,
                    "file_type": file_ext[1:],  # Remove the dot
                    "public_date": "",
                    "source": "local"
                }
                
                books.append(book_metadata)
                # Only log individual books if not suppressed
                if not hasattr(scan_local_books, '_suppress_logs'):
                    print(f"Found local book: {book_title} ({file_ext})")
    
    # Only log summary if not suppressed
    if not hasattr(scan_local_books, '_suppress_logs'):
        print(f"Found {len(books)} local books")
    return books

def extract_text_from_local_book(file_path: str, file_type: str) -> str:
    """
    Extracts text content from a local book file.
    """
    try:
        if file_type == 'pdf':
            return extract_text_from_pdf(file_path)
        elif file_type == 'docx':
            return extract_text_from_docx(file_path)
        elif file_type == 'txt':
            return extract_text_from_txt(file_path)
        elif file_type == 'epub':
            return extract_text_from_epub(file_path)
        else:
            print(f"Unsupported file type: {file_type}")
            return ""
    except Exception as e:
        print(f"Error extracting text from {file_path}: {e}")
        return ""

def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF using PyMuPDF."""
    if not PYMUPDF_AVAILABLE:
        print(f"PyMuPDF not available, cannot extract text from PDF: {file_path}")
        return ""
    
    try:
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        print(f"Error reading PDF {file_path}: {e}")
        return ""

def extract_text_from_docx(file_path: str) -> str:
    """Extract text from DOCX using python-docx."""
    try:
        doc = docx.Document(file_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        print(f"Error reading DOCX {file_path}: {e}")
        return ""

def extract_text_from_txt(file_path: str) -> str:
    """Extract text from TXT file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading TXT {file_path}: {e}")
        return ""

def extract_text_from_epub(file_path: str) -> str:
    """Extract text from EPUB file."""
    try:
        text = ""
        with zipfile.ZipFile(file_path, 'r') as zip_file:
            # Find all HTML/XHTML files in the EPUB
            for file_info in zip_file.filelist:
                if file_info.filename.endswith(('.html', '.xhtml', '.htm')):
                    with zip_file.open(file_info.filename) as html_file:
                        try:
                            # Parse HTML and extract text
                            html_content = html_file.read().decode('utf-8', errors='ignore')
                            # Simple HTML tag removal (you might want to use BeautifulSoup for better parsing)
                            import re
                            text_content = re.sub('<[^<]+?>', '', html_content)
                            text += text_content + "\n"
                        except Exception:
                            continue
        return text
    except Exception as e:
        print(f"Error reading EPUB {file_path}: {e}")
        return ""

def process_local_books_for_chromadb() -> Dict[str, str]:
    """
    Process all local books and return a dictionary of book_id -> full_text.
    Similar to InternetArchiveDownloader but for local files.
    """
    books = scan_local_books()
    book_texts = {}
    
    for book in books:
        book_id = book["identifier"]
        file_path = book["file_path"]
        file_type = book["file_type"]
        
        print(f"Processing local book: {book_id}")
        text = extract_text_from_local_book(file_path, file_type)
        
        if text and len(text.strip()) > 100:  # Only include books with substantial content
            book_texts[book_id] = text
            print(f"Extracted {len(text)} characters from {book_id}")
        else:
            print(f"No substantial text found in {book_id}")
    
    return book_texts
