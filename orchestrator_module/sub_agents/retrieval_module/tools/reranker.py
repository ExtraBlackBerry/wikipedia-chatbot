import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from config import RERANK_MODEL
from sentence_transformers import CrossEncoder

_reranker = None
 
def get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        print(f"[reranker] Loading model: {RERANK_MODEL}")
        _reranker = CrossEncoder(RERANK_MODEL)
    return _reranker

def _rerank(query: str, candidates: list[dict]) -> list[dict]:
    reranker = get_reranker()
 
    pairs  = [[query, c["text"]] for c in candidates]
    scores = reranker.predict(pairs).tolist()
 
    for candidate, score in zip(candidates, scores):
        candidate["rerank_score"] = round(score, 4)
 
    return sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)