import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from tools.ingestion import ingest_with_qna as _ingest

def ingest(url: str):
    chunks, qna_result, errors, message = _ingest(url)