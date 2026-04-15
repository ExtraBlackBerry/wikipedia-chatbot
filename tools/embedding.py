import sys
from sentence_transformers import SentenceTransformer
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import EMBED_MODEL


model = SentenceTransformer(f"{EMBED_MODEL}")

def embed_batch(texts: list[str]) -> list[list[float]]:
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embeddings.tolist()