import spacy, sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent.parent.parent))

from config import QNA_SPACY_MODEL
from db.database import get_conn as _get_conn

_nlp = None
 
def get_nlp():
    global _nlp
    if _nlp is None:
        print(f"[spacy] Loading: {QNA_SPACY_MODEL}")
        _nlp = spacy.load(QNA_SPACY_MODEL)
    return _nlp

def _spacy_score(query_doc, question: str) -> float:
    nlp   = get_nlp()
    q_doc = nlp(question)
 
    # Entity overlap (weight 0.5)
    q_ents     = {e.text.lower() for e in query_doc.ents}
    s_ents     = {e.text.lower() for e in q_doc.ents}
    ent_score  = len(q_ents & s_ents) / len(q_ents | s_ents) if (q_ents or s_ents) else 0.0
 
    # Noun chunk overlap (weight 0.3)
    q_chunks    = {c.lemma_.lower() for c in query_doc.noun_chunks}
    s_chunks    = {c.lemma_.lower() for c in q_doc.noun_chunks}
    chunk_score = len(q_chunks & s_chunks) / len(q_chunks | s_chunks) if (q_chunks or s_chunks) else 0.0
 
    # Lemma token overlap (weight 0.2)
    q_lemmas    = {t.lemma_.lower() for t in query_doc if not t.is_stop and not t.is_punct and t.is_alpha}
    s_lemmas    = {t.lemma_.lower() for t in q_doc    if not t.is_stop and not t.is_punct and t.is_alpha}
    lemma_score = len(q_lemmas & s_lemmas) / len(q_lemmas | s_lemmas) if (q_lemmas or s_lemmas) else 0.0
 
    return round(0.5 * ent_score + 0.3 * chunk_score + 0.2 * lemma_score, 4)
 
 
def search_qna_spacy(query: str, top_k: int = 3, min_score: float = 0.3) -> dict:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, question, answer, source FROM qna"
    ).fetchall()
    conn.close()
 
    if not rows:
        return {
            "results":           [],
            "total_qna_pairs":   0,
            "message":           "QnA table is empty. Run ingest_with_qna() first.",
            "query_entities":    [],
            "query_noun_chunks": [],
        }
 
    nlp       = get_nlp()
    query_doc = nlp(query)
 
    scored = []
    for row in rows:
        score = _spacy_score(query_doc, row["question"])
        if score >= min_score:
            scored.append({
                "id":       row["id"],
                "question": row["question"],
                "answer":   row["answer"],
                "source":   row["source"],
                "score":    score,
            })
 
    scored.sort(key=lambda x: x["score"], reverse=True)
 
    return {
        "results":           scored[:top_k],
        "total_qna_pairs":   len(rows),
        "query_entities":    [e.text for e in query_doc.ents],
        "query_noun_chunks": [c.text for c in query_doc.noun_chunks],
        "message":           f"Found {len(scored[:top_k])} relevant QnA pairs.",
    }