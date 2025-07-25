import requests
import os
import time
from typing import List, Dict, Optional
import PyPDF2
import zipfile
import tempfile
from io import BytesIO

class InternetArchiveDownloader:
    """
    Downloads full text content from Internet Archive items.
    Supports PDF, TXT, and other text-based formats.
    """
    
    def __init__(self, download_dir: str = "downloaded_books"):
        self.download_dir = download_dir
        self.base_url = "https://archive.org"
        os.makedirs(download_dir, exist_ok=True)
    
    def get_item_files(self, identifier: str) -> List[Dict]:
        """
        Get list of available files for an Internet Archive item.
        """
        try:
            metadata_url = f"{self.base_url}/metadata/{identifier}"
            response = requests.get(metadata_url, timeout=10)
            response.raise_for_status()
            
            metadata = response.json()
            files = metadata.get("files", [])
            
            # Filter for text-based files
            text_files = []
            for file in files:
                name = file.get("name", "").lower()
                format_type = file.get("format", "").lower()
                
                # Look for PDF, TXT, or other readable formats
                if any(ext in name for ext in [".pdf", ".txt", ".epub"]) or \
                   any(fmt in format_type for fmt in ["pdf", "text", "epub"]):
                    text_files.append({
                        "name": file.get("name"),
                        "format": file.get("format"),
                        "size": file.get("size", "0"),
                        "url": f"{self.base_url}/download/{identifier}/{file.get('name')}"
                    })
            
            return text_files
            
        except Exception as e:
            print(f"Error getting files for {identifier}: {e}")
            return []
    
    def download_file(self, identifier: str, filename: str) -> Optional[str]:
        """
        Download a specific file from Internet Archive.
        Returns path to downloaded file or None if failed.
        """
        try:
            url = f"{self.base_url}/download/{identifier}/{filename}"
            local_path = os.path.join(self.download_dir, f"{identifier}_{filename}")
            
            # Skip if already downloaded
            if os.path.exists(local_path):
                print(f"File already exists: {local_path}")
                return local_path
            
            print(f"Downloading: {url}")
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"Downloaded: {local_path} ({os.path.getsize(local_path)} bytes)")
            return local_path
            
        except Exception as e:
            print(f"Error downloading {filename} from {identifier}: {e}")
            return None
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extract text from PDF file.
        """
        try:
            text = ""
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n"
            return text
        except Exception as e:
            print(f"Error extracting text from PDF {pdf_path}: {e}")
            return ""
    
    def extract_text_from_txt(self, txt_path: str) -> str:
        """
        Extract text from TXT file.
        """
        try:
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
            for encoding in encodings:
                try:
                    with open(txt_path, 'r', encoding=encoding) as file:
                        return file.read()
                except UnicodeDecodeError:
                    continue
            return ""
        except Exception as e:
            print(f"Error reading text file {txt_path}: {e}")
            return ""
    
    def download_and_extract_text(self, identifier: str, max_files: int = 2) -> str:
        """
        Download and extract text content from an Internet Archive item.
        Returns combined text content.
        """
        print(f"Processing Internet Archive item: {identifier}")
        
        # Get available files
        files = self.get_item_files(identifier)
        if not files:
            print(f"No text files found for {identifier}")
            return ""
        
        # Sort by file size (prefer smaller files for faster processing)
        files.sort(key=lambda x: int(x.get("size", "0")))
        
        combined_text = ""
        downloaded_count = 0
        
        for file_info in files[:max_files]:
            filename = file_info["name"]
            file_format = file_info.get("format", "").lower()
            file_size = int(file_info.get("size", "0"))
            
            # Skip very large files (>50MB) to avoid timeout
            if file_size > 50 * 1024 * 1024:
                print(f"Skipping large file: {filename} ({file_size} bytes)")
                continue
            
            # Download file
            local_path = self.download_file(identifier, filename)
            if not local_path:
                continue
            
            # Extract text based on file type
            text_content = ""
            if filename.lower().endswith('.pdf') or 'pdf' in file_format:
                text_content = self.extract_text_from_pdf(local_path)
            elif filename.lower().endswith('.txt') or 'text' in file_format:
                text_content = self.extract_text_from_txt(local_path)
            
            if text_content:
                combined_text += f"\n\n=== Content from {filename} ===\n\n"
                combined_text += text_content
                downloaded_count += 1
                print(f"Extracted {len(text_content)} characters from {filename}")
            
            # Clean up downloaded file to save space
            try:
                os.remove(local_path)
            except:
                pass
            
            # Small delay to be respectful to Internet Archive
            time.sleep(1)
        
        print(f"Total text extracted for {identifier}: {len(combined_text)} characters from {downloaded_count} files")
        return combined_text
    
    def download_multiple_books(self, book_identifiers: List[str]) -> Dict[str, str]:
        """
        Download and extract text from multiple books.
        Returns dict mapping identifier to extracted text.
        """
        results = {}
        
        for identifier in book_identifiers:
            try:
                text = self.download_and_extract_text(identifier)
                if text:
                    results[identifier] = text
                else:
                    print(f"No text extracted for {identifier}")
            except Exception as e:
                print(f"Error processing {identifier}: {e}")
                
            # Delay between books
            time.sleep(2)
        
        return results


# Test function
if __name__ == "__main__":
    downloader = InternetArchiveDownloader()
    
    # Test with NDH-related book
    test_identifier = "35-mucenika-hrvatske-vojske-ndh"
    text = downloader.download_and_extract_text(test_identifier)
    
    if text:
        print(f"\nExtracted text preview (first 500 chars):")
        print(text[:500])
        print(f"\nTotal length: {len(text)} characters")
    else:
        print("No text extracted")
