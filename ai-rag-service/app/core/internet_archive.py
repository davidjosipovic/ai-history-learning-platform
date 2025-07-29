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

    # Ažurirani prompt za LLM s fokusom na glavne entitete i strategijsko pretraživanje
    system_prompt = (
        "Ti si stručnjak za obradu prirodnog jezika i pretraživanje povijesnih materijala. "
        "Tvoj zadatak je izdvojiti **ključne entitete** iz korisničkog pitanja za strategijsko pretraživanje. "
        "Fokusiraj se na **glavne povijesne entitete** (države, organizacije, pokreti) i **puna imena osoba**. "
        "**STRATEGIJA**: "
        "1. Glavni entitet (država/organizacija): koristi puni naziv (npr. 'Nezavisna Država Hrvatska', 'Soviet Union', 'Roman Empire') "
        "2. Ključne osobe: UVIJEK puno ime i prezime (npr. 'Napoleon Bonaparte', 'Winston Churchill', 'Ante Pavelić') "
        "3. Specifični kontekst: organizacije, regije, godine ako su ključne "
        "4. Za vremenska/detaljka pitanja: uključi kontekst (npr. 'church sunday morning', 'arrived time') "
        "**IZBJEGAVAJ** općenite termine kao 'World War II' - fokusiraj se na specifične entitete. "
        "**JEZIK**: Koristi jezik koji će dati najbolje rezultate na Internet Archive (često engleski za internacionalne teme). "
        "Rezultat mora biti JSON array stringova (maksimalno 4 termina). "
        "PRIMJERI: "
        "- Za 'Koji su uzroci osnivanja NDH?' → [\"Nezavisna Država Hrvatska\", \"Ante Pavelić\", \"ustaše\", \"Croatia 1941\"] "
        "- Za 'Tko je vodio NDH?' → [\"Nezavisna Država Hrvatska\", \"Ante Pavelić\", \"ustaše\"] "
        "- Za 'What caused Roman Empire fall?' → [\"Roman Empire\", \"barbarian invasions\", \"Constantinople\"] "
        "- Za 'Who was Napoleon?' → [\"Napoleon Bonaparte\", \"French Empire\", \"Waterloo\"] "
        "- Za 'Stalin policies?' → [\"Joseph Stalin\", \"Soviet Union\", \"collectivization\"] "
        "**Važno:** Uvijek koristi pune nazive i imena. Izbjegavaj kratke akronime."
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
    Builds the 'q' parameter string for Internet Archive Advanced Search API
    from a list of keywords. Uses strategic grouping with AND/OR operators:
    - Groups related terms (synonyms) with OR
    - Combines different concepts with AND for precision
    - Adds contextual terms to avoid false positives
    Returns a raw, unencoded query string.
    """
    if not keywords:
        return "mediatype:(texts)"

    # Categorize keywords into groups
    main_entities = []  # Main historical entities (countries, organizations, etc.)
    people_names = []   # Full names of people
    other_terms = []    # Other historical terms
    
    # Check if this requires special handling (look for known historical entities)
    has_historical_entities = any(
        term.lower() in ' '.join(keywords).lower() 
        for term in ['empire', 'kingdom', 'republic', 'union', 'state', 'dynasty', 
                     'war', 'revolution', 'battle', 'treaty', 'alliance', 'party',
                     'ndh', 'nezavisna država', 'hrvatska', 'croatia', 'yugoslavia',
                     'roman', 'byzantine', 'ottoman', 'soviet', 'british', 'french']
    )
    
    for keyword in keywords:
        keyword_lower = keyword.lower()
        
        # Detect main entities (countries, organizations, movements) - general approach
        if any(entity in keyword_lower for entity in [
            # General historical entities
            'empire', 'kingdom', 'republic', 'union', 'state', 'dynasty',
            'party', 'movement', 'alliance', 'confederation', 'federation',
            # Specific known entities (expandable)
            'ndh', 'nezavisna država', 'hrvatska', 'croatia', 
            'yugoslavia', 'soviet union', 'roman empire', 'byzantine',
            'ottoman', 'british empire', 'french republic', 'third reich',
            'ustaše', 'ustase', 'partizani', 'partisan', 'nazi', 'communist'
        ]):
            main_entities.append(keyword)
        # Detect people names (containing both first and last name)
        elif len(keyword.split()) >= 2 and any(char.isupper() for char in keyword):
            people_names.append(keyword)
        else:
            other_terms.append(keyword)
    
    query_parts = []
    
    # Build main entity group with OR (synonyms) and add context for historical topics
    if main_entities:
        entity_parts = []
        for entity in main_entities:
            if " " in entity:
                entity_parts.append(f'"{entity}"')
            else:
                # For known problematic short terms, use full forms
                if entity.lower() == 'ndh':
                    # Use full form instead of just NDH to avoid medical/other false positives
                    entity_parts.append('"Nezavisna Država Hrvatska"')
                else:
                    entity_parts.append(entity)
        
        # Combine entity parts with OR
        if len(entity_parts) > 1:
            query_parts.append(f"({' OR '.join(entity_parts)})")
        else:
            query_parts.append(entity_parts[0])
    
    # Add people names with AND (must have specific person)
    if people_names:
        for person in people_names:
            if " " in person:
                query_parts.append(f'"{person}"')
            else:
                query_parts.append(person)
    
    # Add minimal contextual terms for better precision (avoid over-specification)
    if has_historical_entities and len(query_parts) < 2:
        # Only add very general contextual terms if we don't have enough specific ones
        if any('empire' in kw.lower() or 'kingdom' in kw.lower() for kw in keywords):
            # Don't add extra terms for empire/kingdom queries - they're specific enough
            pass
        elif any('war' in kw.lower() for kw in keywords):
            # Don't add extra terms for war queries - they're specific enough  
            pass
    
    # Add other terms if we don't have enough specific terms
    if not main_entities and not people_names and other_terms:
        for term in other_terms[:2]:  # Limit to 2 terms to avoid over-specification
            if " " in term:
                query_parts.append(f'"{term}"')
            else:
                query_parts.append(term)
    
    # Combine with AND for precision
    if query_parts:
        combined_keywords = " AND ".join(query_parts)
    else:
        # Fallback to simple OR if categorization fails
        simple_parts = []
        for keyword in keywords[:3]:  # Limit to 3 keywords
            if " " in keyword:
                simple_parts.append(f'"{keyword}"')
            else:
                simple_parts.append(keyword)
        combined_keywords = " OR ".join(simple_parts)
    
    # UVIJEK dodaj mediatype:(texts) filter za fokus na knjige/tekstove
    if combined_keywords:
        final_query = f"mediatype:(texts) AND ({combined_keywords})"
    else:
        # Ako nema ključnih riječi, pretraži samo tekstove
        final_query = "mediatype:(texts)"
    
    print(f"Built strategic search query: {final_query}")
    return final_query


def search_internet_archive_advanced(query_string: str, rows: int = 50) -> List[Dict]:
    """
    Search Internet Archive using the advanced search endpoint.
    The query_string should be a raw, unencoded string. 'requests' will handle encoding.
    Returns a list of metadata dicts for the top results.
    Automatically adds mediatype:(texts) filter.
    """
    params = {
        "q": query_string,
        "fl[]": ["identifier", "title", "creator", "description", "publicdate", "date"],  # Dodaj potrebne metapodatke
        "rows": rows,
        "page": 1,
        "output": "json",
        "save": "yes"
    }
    
    try:
        resp = requests.get(INTERNET_ARCHIVE_ADVANCED_SEARCH_URL, params=params, timeout=15)
        
        # Debug: Print the actual URL being called to verify encoding
        print(f"DEBUG: Request URL: {resp.url}")
        
        resp.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        data = resp.json()
        
        docs = data.get("response", {}).get("docs", [])
        print(f"Internet Archive advanced search found {len(docs)} raw documents.")
        
        # Improved fallback strategy if no results
        if not docs and " AND " in query_string:
            print("No results found, trying simplified search with main entity only...")
            # Extract main entities for fallback
            try:
                # Look for main entity patterns in the query - general approach
                if "ndh" in query_string.lower() or "nezavisna" in query_string.lower():
                    fallback_query = 'mediatype:(texts) AND ("Nezavisna Država Hrvatska" OR "Independent State Croatia")'
                elif "napoleon" in query_string.lower():
                    fallback_query = 'mediatype:(texts) AND ("Napoleon Bonaparte" OR "Napoleon")'
                elif "stalin" in query_string.lower():
                    fallback_query = 'mediatype:(texts) AND ("Joseph Stalin" OR "Stalin")'
                elif "churchill" in query_string.lower():
                    fallback_query = 'mediatype:(texts) AND ("Winston Churchill" OR "Churchill")'
                elif "tito" in query_string.lower():
                    fallback_query = 'mediatype:(texts) AND ("Josip Broz Tito" OR "Tito")'
                elif "hitler" in query_string.lower():
                    fallback_query = 'mediatype:(texts) AND ("Adolf Hitler" OR "Hitler")'
                elif "roman empire" in query_string.lower():
                    fallback_query = 'mediatype:(texts) AND ("Roman Empire" OR "Rome")'
                elif "soviet" in query_string.lower():
                    fallback_query = 'mediatype:(texts) AND ("Soviet Union" OR "USSR")'
                else:
                    # Generic fallback - use first quoted term or first word
                    if '"' in query_string:
                        first_quoted = query_string.split('"')[1]
                        fallback_query = f'mediatype:(texts) AND "{first_quoted}"'
                    else:
                        first_term = query_string.split("(")[1].split()[0]
                        fallback_query = f'mediatype:(texts) AND {first_term}'
                
                print(f"Fallback query: {fallback_query}")
                params["q"] = fallback_query
                
                resp = requests.get(INTERNET_ARCHIVE_ADVANCED_SEARCH_URL, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                docs = data.get("response", {}).get("docs", [])
                print(f"Fallback search found {len(docs)} documents.")
                
            except (IndexError, AttributeError) as e:
                print(f"Could not parse fallback query: {e}")
                # Ultimate fallback - search for general historical terms, uvijek s mediatype:(texts)
                params["q"] = 'mediatype:(texts) AND ("history" OR "historical" OR "empire" OR "war")'
                try:
                    resp = requests.get(INTERNET_ARCHIVE_ADVANCED_SEARCH_URL, params=params, timeout=10)
                    resp.raise_for_status()
                    data = resp.json()
                    docs = data.get("response", {}).get("docs", [])
                    print(f"Ultimate fallback search found {len(docs)} documents.")
                except Exception:
                    print("All fallback attempts failed.")
                    docs = []


        results = []
        for doc in docs[:rows]: # Iterate only up to 'rows' requested
            results.append({
                "identifier": doc.get("identifier", ""),
                "title": doc.get("title", ""),
                "creator": doc.get("creator", ""),
                "public_date": doc.get("publicdate", doc.get("date", "")), # Use publicdate as it's more reliable
                "description": doc.get("description", "")
            })
        return results
    except requests.exceptions.RequestException as req_err:
        print(f"ERROR: Network or HTTP error during Internet Archive search: {req_err}")
        return []
    except json.JSONDecodeError as json_err:
        print(f"ERROR: JSON decoding error from Internet Archive response: {json_err}")
        print(f"Response content (first 500 chars): {resp.text[:500]}")
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
        "Who was Napoleon Bonaparte?", 
        "What caused the fall of Roman Empire?",
        "Stalin's policies in Soviet Union?",
        "Tko je bio Tito?",
        "Winston Churchill World War II role?",
        "French Revolution causes?",
        "Byzantine Empire history?",
        "American Civil War",
        "Ancient Egypt pharaohs"
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
        # Koristimo search_internet_archive_advanced s novom zadanom vrijednošću rows=50
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