import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from db.database import get_conn

def list_ingested() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT title, url, COUNT(*) as chunks, SUM(tokens) as total_tokens
        FROM wiki_chunks GROUP BY title, url ORDER BY title
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]