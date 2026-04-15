import struct, hashlib, sqlite3

SKIP_SECTIONS = {
    "references", "external links", "see also",
    "further reading", "notes", "bibliography", "footnotes",
}

def serialize(embedding: list[float]) -> bytes:
    return struct.pack(f"{len(embedding)}f", *embedding)
 
 
def make_doc_id(url: str, text: str) -> str:
    return hashlib.md5(f"{url}:{text[:120]}".encode()).hexdigest()
 
 
def is_valid_chunk(chunk) -> bool:
    section = (chunk.meta.headings[-1] if chunk.meta.headings else "").lower()
    return section not in SKIP_SECTIONS and len(chunk.text.strip()) > 80
 
 
def already_ingested(conn: sqlite3.Connection, doc_id: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM wiki_chunks WHERE doc_id = ?", (doc_id,)
    ).fetchone() is not None