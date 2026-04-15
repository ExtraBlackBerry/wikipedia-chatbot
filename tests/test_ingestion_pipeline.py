import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from tools.ingestion import ingest, ingest_with_qna

if __name__ == "__main__":
    result = ingest_with_qna(
        "https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
        num_pairs_per_chunk=3,
    )
    print(result)