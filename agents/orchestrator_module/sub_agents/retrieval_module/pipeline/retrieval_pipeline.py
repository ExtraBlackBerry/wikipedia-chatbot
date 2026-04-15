import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from db.database import get_conn
from agents.orchestrator_module.sub_agents.retrieval_module.tools.retrieval_methods import _fts_search, _vector_search
from agents.orchestrator_module.sub_agents.retrieval_module.tools.reranker import _rerank
from agents.orchestrator_module.sub_agents.retrieval_module.tools.rrf_fusion import _rrf_fusion

def retrieve_simple(
    query: str,
    top_k: int = 5,
    fetch_k: int = 20,
    rerank: bool = True,
    fts_weight: float = 0.5,
    vec_weight: float = 0.5,
    title_filter: str | None = None,
    section_filter: str | None = None,
) -> list[dict]:

    conn = get_conn()
 
    fts_results = _fts_search(conn, query, k=fetch_k)
    vec_results = _vector_search(conn, query, k=fetch_k)
    conn.close()
 
    print(f"  [hybrid] FTS: {len(fts_results)} | Vector: {len(vec_results)}")
 
    fused = _rrf_fusion(fts_results, vec_results, fts_weight=fts_weight, vec_weight=vec_weight)
 
    if title_filter:
        fused = [c for c in fused if title_filter.lower() in c["title"].lower()]
    if section_filter:
        fused = [c for c in fused if section_filter.lower() in c["section"].lower()]
 
    if not fused:
        return []
 
    rerank_pool = fused[:fetch_k]
    if rerank:
        rerank_pool = _rerank(query, rerank_pool)
        score_key   = "rerank_score"
    else:
        score_key   = "rrf_score"
 
    return [
        {
            "title":        c["title"],
            "section":      c["section"],
            "text":         c["text"],
            "url":          c["url"],
            "tokens":       c["tokens"],
            "score":        round(c[score_key], 4),
            "rrf_score":    round(c.get("rrf_score", 0), 4),
            "vector_score": c.get("vector_score"),
            "fts_score":    c.get("fts_score"),
            "rerank_score": c.get("rerank_score"),
        }
        for c in rerank_pool[:top_k]
    ]