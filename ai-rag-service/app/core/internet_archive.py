import requests
from typing import List, Dict

INTERNET_ARCHIVE_SEARCH_URL = "https://archive.org/advancedsearch.php"


def search_internet_archive_metadata(query: str, rows: int = 5) -> List[Dict]:
    """
    Search Internet Archive metadata for books relevant to the query.
    Returns a list of metadata dicts for the top results.
    """
    params = {
        "q": query,
        "fl[]": ["identifier", "title", "creator", "year", "description"],
        "rows": rows,
        "output": "json"
    }
    response = requests.get(INTERNET_ARCHIVE_SEARCH_URL, params=params)
    response.raise_for_status()
    docs = response.json().get("response", {}).get("docs", [])
    return docs
