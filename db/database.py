import sqlite3, sqlite_vec, sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import DB_PATH, EMBED_DIM

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn

def setup_db(conn: sqlite3.Connection):
    conn.executescript(f"""
        CREATE TABLE IF NOT EXISTS wiki_chunks (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id    TEXT UNIQUE,
            title     TEXT,
            section   TEXT,
            text      TEXT,
            url       TEXT,
            tokens    INTEGER,
            created_at DATETIME DEFAULT (datetime('now'))
        );
 
        CREATE VIRTUAL TABLE IF NOT EXISTS wiki_embeddings USING vec0(
            chunk_id  INTEGER PRIMARY KEY,
            embedding FLOAT[{EMBED_DIM}]
        );
    """)

    conn.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
            title,
            section,
            text,
            content='wiki_chunks',
            content_rowid='id',
            tokenize='porter ascii'   -- porter stemming: "running" matches "run"
        );
 
        -- Populate from existing wiki_chunks rows
        INSERT OR IGNORE INTO wiki_fts(rowid, title, section, text)
            SELECT id, title, section, text FROM wiki_chunks
            WHERE id NOT IN (SELECT rowid FROM wiki_fts);
    """)
    conn.commit()

    conn.executescript(f"""
        -- Main QnA table (your existing schema)
        CREATE TABLE IF NOT EXISTS qna (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer   TEXT NOT NULL,
            chunk_id    TEXT,
            source   TEXT
        );
 
        -- Semantic search (separate vec0 — never stored in main table)
        CREATE VIRTUAL TABLE IF NOT EXISTS qna_embeddings USING vec0(
            qna_id    INTEGER PRIMARY KEY,
            embedding FLOAT[{EMBED_DIM}]
        );
 
        -- Keyword search (FTS5 over question + answer columns)
        CREATE VIRTUAL TABLE IF NOT EXISTS qna_fts USING fts5(
            question,
            answer,
            content='qna',
            content_rowid='id',
            tokenize='porter ascii'
        );
 
        -- Sync FTS from any existing rows not yet indexed
        INSERT OR IGNORE INTO qna_fts(rowid, question, answer)
            SELECT id, question, answer FROM qna
            WHERE id NOT IN (SELECT rowid FROM qna_fts);
    """)
    conn.commit()