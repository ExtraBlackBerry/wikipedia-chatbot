def _rrf_fusion(
    fts_results: list[dict],
    vec_results: list[dict],
    k: int = 60,
    fts_weight: float = 0.5,
    vec_weight: float = 0.5,
) -> list[dict]:
    scores: dict[int, dict] = {}
 
    for rank, result in enumerate(fts_results, start=1):
        cid = result["id"]
        if cid not in scores:
            scores[cid] = {**result, "rrf_score": 0.0}
        scores[cid]["rrf_score"]   += fts_weight / (k + rank)
        scores[cid]["fts_score"]    = result["fts_score"]
 
    for rank, result in enumerate(vec_results, start=1):
        cid = result["id"]
        if cid not in scores:
            scores[cid] = {**result, "rrf_score": 0.0}
        scores[cid]["rrf_score"]    += vec_weight / (k + rank)
        scores[cid]["vector_score"]  = result["vector_score"]
 
    return sorted(scores.values(), key=lambda x: x["rrf_score"], reverse=True)