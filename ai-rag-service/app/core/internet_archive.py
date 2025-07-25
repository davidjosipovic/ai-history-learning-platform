import requests
import openai
import os
import json # Dodano za json.loads
import urllib.parse # Dodano za URL kodiranje
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# INTERNET_ARCHIVE_SEARCH_URL se odnosi na napredni API, stoga preimenujmo ga za jasnoću
INTERNET_ARCHIVE_ADVANCED_SEARCH_URL = "https://archive.org/advancedsearch.php"

# Inicijalizacija OpenAI klijenta
# Preporučeno: Koristite varijable okruženja za API ključ
# Npr. export OPENAI_API_KEY='your_api_key_here'
# client se inicijalizira direktno, a ne preko openai.api_key
try:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable is not set or empty in internet_archive.py")
        client = None
    else:
        client = openai.OpenAI(api_key=api_key)
        print("OpenAI client initialized successfully in internet_archive.py")
except Exception as e:
    print(f"ERROR: Failed to initialize OpenAI client in internet_archive.py. Please check OPENAI_API_KEY environment variable. Error: {e}")
    client = None # Postavite na None ako inicijalizacija ne uspije

def generate_keywords_from_question(question: str) -> List[str]:
    """
    Uses LLM to generate a list of relevant keywords/phrases from the user's historical question.
    Emphasizes generating a concise, highly relevant set of terms.
    """
    if not client:
        print("OpenAI client is not initialized. Cannot generate keywords.")
        return [question] # Fallback: return original question as a single keyword

    # Ažurirani prompt za LLM kako bi generirao manji, precizniji skup ključnih riječi
    system_prompt = (
        "Ti si stručnjak za obradu prirodnog jezika i pretraživanje povijesnih materijala. "
        "Tvoj zadatak je izdvojiti **minimalan, ali najrelevantniji set ključnih riječi i fraza** iz korisničkog pitanja. "
        "Fokusiraj se na **jednu do tri ključne fraze/pojma** koje najpreciznije opisuju povijesni događaj, osobu ili koncept. "
        "Za hrvatska povijesna pitanja, uključi sinonime i punu formu kratica. "
        "Rezultat mora biti JSON array stringova. "
        "PRIMJERI: "
        "- Za 'Što je bila NDH?' → [\"NDH\", \"Nezavisna Država Hrvatska\", \"Croatia 1941-1945\"] "
        "- Za 'Tko je bio Napoleon?' → [\"Napoleon Bonaparte\", \"French Emperor\"] "
        "- Za 'Što je bio Holokaust?' → [\"Holocaust\", \"World War II genocide\"] "
        "Izbjegavaj opće riječi poput 'koje', 'knjige', 'o', 'što', 'kako'."
        "**Važno:** Za kraćice kao NDH, uvijek dodaj i punu formu naziva."
    )
    user_prompt = f"Ekstrahiraj ključne riječi iz pitanja: '{question}'"

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # Preporučeno za brži i jeftiniji pristup, ili "gpt-4" za bolju kvalitetu
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0 # Niska temperatura za dosljedne rezultate
        )
        
        # Ispravno dohvaćanje sadržaja odgovora
        json_string = response.choices[0].message.content.strip()
        
        try:
            keywords = json.loads(json_string)
            if isinstance(keywords, list) and all(isinstance(k, str) for k in keywords):
                return [k.lower() for k in keywords if k.strip()] # Vrati mala slova i filtriraj prazne
            else:
                print(f"WARNING: LLM did not return a valid JSON array of strings. Raw response: {json_string}")
                return [question] # Fallback
        except json.JSONDecodeError:
            print(f"WARNING: Could not parse JSON from LLM response. Raw response: {json_string}")
            return [question] # Fallback

    except Exception as e:
        print(f"ERROR: Failed to generate keywords via LLM: {e}")
        return [question] # Fallback to original question

def build_internet_archive_query_string(keywords: List[str]) -> str:
    """
    Builds the URL-encoded 'q' parameter string for Internet Archive Advanced Search API
    from a list of keywords. It automatically adds the mediatype:(texts) filter.
    Uses OR logic to find documents containing any of the keywords.
    """
    if not keywords:
        # Default query: search for all texts if no keywords are provided
        return urllib.parse.quote_plus("mediatype:(texts)")

    query_parts = []
    for keyword in keywords:
        # Put multi-word phrases in quotes for exact matching
        if " " in keyword:
            query_parts.append(f'"{keyword}"')
        else:
            query_parts.append(keyword)

    # Combine keywords with OR operator for broader search
    # This will find documents that contain ANY of the keywords
    combined_keywords = " OR ".join(query_parts)
    
    # Add mediatype filter to focus on books/texts
    final_query = f"mediatype:(texts) AND ({combined_keywords})"
    
    print(f"Built search query: {final_query}")
    
    # URL encode the entire query string
    return urllib.parse.quote_plus(final_query)


def search_internet_archive_advanced(query_string: str, rows: int = 5) -> List[Dict]:
    """
    Search Internet Archive using the advanced search endpoint.
    The query_string parameter must be a URL-encoded string previously built by build_internet_archive_query_string.
    Returns a list of metadata dicts for the top results.
    """
    params = {
        "q": query_string,  # This is the URL-encoded query string
        # Specify fields to retrieve. 'publicdate' is more consistent than 'date' or 'year'.
        "fl[]": ["identifier", "title", "creator", "description", "publicdate"],
        "rows": rows,
        "output": "json"
    }
    
    try:
        resp = requests.get(INTERNET_ARCHIVE_ADVANCED_SEARCH_URL, params=params, timeout=10)
        resp.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        data = resp.json()
        
        results = []
        # The advanced search API usually returns 'response' -> 'docs'
        docs = data.get("response", {}).get("docs", [])
        
        # Debugging: print how many docs were found after initial parsing
        print(f"Internet Archive advanced search found {len(docs)} raw documents.") 
        
        # If no results with complex query, try simpler fallback
        if len(docs) == 0:
            print("No results found, trying simpler search...")
            # Extract just the first keyword for fallback
            decoded_query = urllib.parse.unquote_plus(query_string)
            # Find first keyword after mediatype filter
            if "(" in decoded_query and ")" in decoded_query:
                keywords_part = decoded_query.split("(", 2)[-1].split(")")[0]
                # Get first word/phrase
                first_keyword = keywords_part.split(" OR ")[0].strip().replace('"', '')
                fallback_query = f"mediatype:(texts) AND {first_keyword}"
                print(f"Fallback query: {fallback_query}")
                
                fallback_params = params.copy()
                fallback_params["q"] = urllib.parse.quote_plus(fallback_query)
                
                resp = requests.get(INTERNET_ARCHIVE_ADVANCED_SEARCH_URL, params=fallback_params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                docs = data.get("response", {}).get("docs", [])
                print(f"Fallback search found {len(docs)} documents.")
        
        for doc in docs[:rows]: # Iterate only up to 'rows' requested
            results.append({
                "identifier": doc.get("identifier", ""),
                "title": doc.get("title", ""),
                "creator": doc.get("creator", ""),
                "public_date": doc.get("publicdate", ""), # Use publicdate as it's more reliable
                "description": doc.get("description", "")
            })
        return results
    except requests.exceptions.RequestException as req_err:
        print(f"ERROR: Network or HTTP error during Internet Archive search: {req_err}")
        return []
    except json.JSONDecodeError as json_err:
        print(f"ERROR: JSON decoding error from Internet Archive response: {json_err}. Response content: {resp.text}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred during Internet Archive search: {e}")
        return []

# --- Primjer Korištenja za testiranje modula ---
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv() # Učitaj .env datoteku ako je ovaj modul pokrenut direktno

    if not os.getenv("OPENAI_API_KEY"):
        print("UPOZORENJE: OPENAI_API_KEY nije postavljen. LLM funkcije neće raditi.")
    
    test_questions = [
        "Što je bila NDH?",
        "Kako je završila Osmanlijsko carstvo?",
        "Tko je bio Napoleon?",
        "Knjige o Drugom svjetskom ratu",
        "Povijest svemira"
    ]

    for question in test_questions:
        print(f"\n--- Pitanje: '{question}' ---")
        
        print("1. Generiram ključne riječi putem LLM-a...")
        keywords = generate_keywords_from_question(question)
        print(f"  Ključne riječi: {keywords}")

        print("2. Gradim Internet Archive query string...")
        # Koristimo novu funkciju koja gradi 'q' parametar string
        ia_query_string = build_internet_archive_query_string(keywords)
        print(f"  IA Query String (URL-encoded 'q'): {ia_query_string}")

        print("3. Pretražujem Internet Archive...")
        # Koristimo search_internet_archive_advanced
        books_found = search_internet_archive_advanced(ia_query_string, rows=5)
        
        if books_found:
            print(f"  Pronađeno {len(books_found)} knjiga:")
            for i, book in enumerate(books_found):
                print(f"    {i+1}. Naslov: {book['title']}")
                print(f"       Autor: {book['creator']}")
                print(f"       Opis: {book['description'][:100]}...")
                print(f"       Link: https://archive.org/details/{book['identifier']}")
        else:
            print("  Nema pronađenih knjiga.")