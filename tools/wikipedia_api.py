import requests, re, sys

def extract_wiki_text(url: str) -> dict:
    match = re.search(r"wikipedia\.org/wiki/([^?#]+)", url)
    if not match:
        raise ValueError("Not a valid Wikipedia URL. Must contain /wiki/")
 
    title = requests.utils.unquote(match.group(1))
 
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts",
        "explaintext": True,
        "exsectionformat": "plain",
        "format": "json",
    }
 
    headers = {"User-Agent": "WikiExtractor/1.0 (https://github.com/example; contact@example.com)"}
    response = requests.get("https://en.wikipedia.org/w/api.php", params=params, headers=headers)
    response.raise_for_status()
    data = response.json()
 
    pages = data["query"]["pages"]
    page = next(iter(pages.values()))
 
    if "missing" in page:
        raise ValueError(f"Page not found: '{title}'")
 
    text = page.get("extract", "")
 
    return {
        "title": page["title"],
        "text": text,
        "words": len(text.split()),
        "characters": len(text),
        "sections": text.count("\n\n"),
    }
    