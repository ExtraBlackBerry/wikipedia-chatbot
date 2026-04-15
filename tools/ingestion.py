import sys

from pathlib import Path
from .helpers import make_doc_id, is_valid_chunk, already_ingested, serialize
from .docling_processing import url_to_chunks
from .embedding import embed_batch
from .qna_generator import generate_qna_from_chunks 

sys.path.append(str(Path(__file__).parent.parent))
from db.database import get_conn, setup_db
from config import BATCH_SIZE, SAVE_MD

#dataclass
from dataclasses import dataclass

@dataclass
class InsertedChunk:
    """
    Returned by ingest() for every chunk successfully written to the DB.
    Passed directly to the QnA generator — no DB round-trip needed.
    """
    chunk_id: int
    title:    str
    section:  str
    text:     str   
    url:      str
    tokens:   int

def ingest(url: str, save_md: bool = False) -> list[InsertedChunk]:
    """
    Full ingestion pipeline.
 
    Returns a list of InsertedChunk — every chunk successfully written to the DB.
    Pass this list directly to generate_qna_from_chunks() to avoid a DB round-trip.
    Returns an empty list if the article was already fully ingested.
    """
    conn = get_conn()
    setup_db(conn)
 
    title, chunks = url_to_chunks(url, save_md=SAVE_MD)
    print(f"  [chunks] {len(chunks)} total")
 
    valid = [c for c in chunks if is_valid_chunk(c)]
    print(f"  [filter] {len(valid)} after removing boilerplate sections")
 
    new_chunks = [
        c for c in valid
        if not already_ingested(conn, make_doc_id(url, c.text))
    ]
    print(f"  [dedup]  {len(new_chunks)} new chunks to embed and store")
 
    if not new_chunks:
        print("  [skip]   Already fully ingested.\n")
        conn.close()
        return []
 
    inserted_chunks: list[InsertedChunk] = []
 
    for i in range(0, len(new_chunks), BATCH_SIZE):
        batch      = new_chunks[i : i + BATCH_SIZE]
        texts      = [c.text for c in batch]
        embeddings = embed_batch(texts)
 
        for chunk, emb in zip(batch, embeddings):
            doc_id  = make_doc_id(url, chunk.text)
            section = chunk.meta.headings[-1] if chunk.meta.headings else ""
            tokens  = len(chunk.text.split())
 
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO wiki_chunks
                    (doc_id, title, section, text, url, tokens)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (doc_id, title, section, chunk.text, url, tokens),
            )
            chunk_id = cur.lastrowid
            if chunk_id:
                conn.execute(
                    "INSERT INTO wiki_embeddings (chunk_id, embedding) VALUES (?, ?)",
                    (chunk_id, serialize(emb)),
                )
                inserted_chunks.append(InsertedChunk(
                    chunk_id = chunk_id,
                    title    = title,
                    section  = section,
                    text     = chunk.text,
                    url      = url,
                    tokens   = tokens,
                ))
 
        conn.commit()
        print(f"  [embed]  Batch {i // BATCH_SIZE + 1} done — {len(inserted_chunks)} inserted so far")
 
    conn.close()
    print(f"  [done]   {len(inserted_chunks)} chunks stored for '{title}'\n")
    return inserted_chunks
 
 
# ── Convenience: ingest + QnA in one call ────────────────────────────────────
def ingest_with_qna(
    url:                str,
    save_md:            bool = False,
    num_pairs_per_chunk: int = 3,
) -> dict:
    """
    Full pipeline: ingest → generate QnA pairs from the fresh chunks.
 
    Chunks flow in memory from ingest() → generate_qna_from_chunks()
    with no DB round-trip. QnA generation is skipped if nothing was
    newly ingested (article already existed).
    """

 
    inserted = ingest(url, save_md=save_md)
 
    if not inserted:
        return {
            "ingested_chunks": 0,
            "qna_pairs":       0,
            "message":         "Article already ingested — QnA generation skipped.",
        }
 
    print(f"  [qna]    Generating QnA pairs for {len(inserted)} chunks...")
    qna_result = generate_qna_from_chunks(
        chunks             = inserted,
        num_pairs_per_chunk = num_pairs_per_chunk,
    )
 
    return {
        "ingested_chunks": len(inserted),
        "qna_pairs":       qna_result["pairs_generated"],
        "errors":          qna_result["errors"],
        "message":         (
            f"Ingested {len(inserted)} chunks and generated "
            f"{qna_result['pairs_generated']} QnA pairs."
        ),
    }