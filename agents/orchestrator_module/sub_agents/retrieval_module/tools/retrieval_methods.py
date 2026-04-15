import sqlite3,sys, re
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))
from tools.helpers import serialize
from tools.embedding import embed_batch

def _sanitise_fts_query(query: str) -> str:

    cleaned = re.sub(r'[()"\*\^\-]', " ", query)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def _ensure_fts(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
            title,
            section,
            text,
            content='wiki_chunks',
            content_rowid='id',
            tokenize='porter ascii'
        );

        INSERT OR IGNORE INTO wiki_fts(rowid, title, section, text)
            SELECT id, title, section, text FROM wiki_chunks
            WHERE id NOT IN (SELECT rowid FROM wiki_fts);
    """)
    conn.commit()


def _fts_search(conn: sqlite3.Connection, query: str, k: int) -> list[dict]:
    _ensure_fts(conn)

    raw = _sanitise_fts_query(query)
    if not raw:
        return []

    terms = raw.split()

    def run_fts(fts_query: str) -> list:
        try:
            return conn.execute(
                """
                SELECT w.id, w.title, w.section, w.text, w.url, w.tokens,
                       bm25(wiki_fts) AS bm25_score
                FROM wiki_fts
                JOIN wiki_chunks w ON w.id = wiki_fts.rowid
                WHERE wiki_fts MATCH ?
                ORDER BY bm25_score
                LIMIT ?
                """,
                (fts_query, k),
            ).fetchall()
        except sqlite3.OperationalError:
            return []

    rows = run_fts(f'"{raw}"') if len(terms) > 1 else []
    if not rows:
        rows = run_fts(" OR ".join(terms))
    if not rows and terms:
        rows = run_fts(terms[0]) 

    return [
        {
            "id":           r["id"],
            "title":        r["title"],
            "section":      r["section"],
            "text":         r["text"],
            "url":          r["url"],
            "tokens":       r["tokens"],
            "fts_score":    min(abs(r["bm25_score"]) / 10.0, 1.0),
            "vector_score": None,
        }
        for r in rows
    ]
    
def _vector_search(conn: sqlite3.Connection, query: str, k: int) -> list[dict]:
    q_emb = embed_batch([query])[0]
 
    rows = conn.execute(
        """
        SELECT w.id, w.title, w.section, w.text, w.url, w.tokens, e.distance
        FROM wiki_embeddings e
        JOIN wiki_chunks w ON w.id = e.chunk_id
        WHERE embedding MATCH ?
          AND k = ?
        ORDER BY e.distance
        """,
        (serialize(q_emb), k),
    ).fetchall()
 
    return [
        {
            "id":           r["id"],
            "title":        r["title"],
            "section":      r["section"],
            "text":         r["text"],
            "url":          r["url"],
            "tokens":       r["tokens"],
            "fts_score":    None,
            "vector_score": round(1 - r["distance"], 4),
        }
        for r in rows
    ]
 