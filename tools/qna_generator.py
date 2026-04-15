import sys, os, json
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from db.database import get_conn as _get_conn
from config import GOOGLE_API_KEY as gemini_api_key

#import google gemini
from google import genai
from google.genai import types

_gemini = None
 
def get_gemini():
    global _gemini
    if _gemini is None:
        _gemini = genai.Client(api_key="AIzaSyCDDkJ1gU5AZXpOkxZrNyiwS21b6EBABqE")
    return _gemini
 

def _generate_pairs(chunk_text: str, source: str, num_pairs: int) -> list[dict]:
    prompt = f"""
        You are given a chunk of text from a Wikipedia article.
        Generate exactly {num_pairs} question and answer pairs based ONLY on the information in this chunk.
        
        Rules:
        - Questions must be answerable solely from the chunk text.
        - Answers must be concise (1-3 sentences).
        - Questions should cover different aspects of the chunk.
        - Do not generate duplicate or very similar questions.
        - Return ONLY a valid JSON array, no explanation, no markdown fences.
 
        Format:
        [
        {{"question": "...", "answer": "..."}},
        {{"question": "...", "answer": "..."}}
        ]
        
        Chunk:
        \"\"\"{chunk_text}\"\"\"
        
        JSON:
"""
 
    response = get_gemini().models.generate_content(
        model    = "gemini-2.5-flash-lite",
        contents = prompt,
        config   = types.GenerateContentConfig(
            temperature     = 0.3,
            max_output_tokens = 1024,
        ),
    )
 
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
 
    try:
        pairs = json.loads(raw)
        return [
            p for p in pairs
            if isinstance(p, dict) and "question" in p and "answer" in p
        ]
    except json.JSONDecodeError:
        return []
 
 
def generate_qna_from_chunks(
    chunks:              list,   # list[InsertedChunk] from ingest()
    num_pairs_per_chunk: int = 3,
) -> dict:
    conn = _get_conn()
 
    generated = 0
    errors    = 0
 
    for chunk in chunks:
        source = f"{chunk.title} > {chunk.section} — {chunk.url}"
        try:
            pairs = _generate_pairs(
                chunk_text = chunk.text,
                source     = source,
                num_pairs  = num_pairs_per_chunk,
            )
            for pair in pairs:
                conn.execute(
                    """
                    INSERT INTO qna (question, answer, source, chunk_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (pair["question"], pair["answer"], source, chunk.chunk_id),
                )
                generated += 1
 
            conn.commit()
            print(f"  [qna_gen] chunk {chunk.chunk_id} ({chunk.section or 'intro'}) → {len(pairs)} pairs")
 
        except Exception as e:
            errors += 1
            print(f"  [qna_gen] ERROR chunk {chunk.chunk_id}: {e}")
 
    conn.close()
    return {
        "pairs_generated": generated,
        "errors":          errors,
        "message":         f"Generated {generated} QnA pairs from {len(chunks)} chunks.",
    }
 