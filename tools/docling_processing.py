import re, sys
from pathlib import Path
from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config import MAX_TOKENS

root = Path(__file__).parent.parent

def url_to_chunks(url: str, save_md: bool = False) -> tuple[str, list]:
    print(f"  [docling] Converting: {url}")
    converter = DocumentConverter()
    result    = converter.convert(url)
    doc       = result.document
    title     = doc.name or url.split("/wiki/")[-1].replace("_", " ")
 
    if save_md:
        out = Path(root, r"documents/parsed_files")
        out.mkdir(exist_ok=True)
        safe = re.sub(r"[^\w\-]", "_", title)
        (out / f"{safe}.md").write_text(doc.export_to_markdown(), encoding="utf-8")
        print(f"  [md]     Saved {out}/{safe}.md")
 
    chunker = HybridChunker(max_tokens=MAX_TOKENS, merge_peers=True)
    chunks  = list(chunker.chunk(doc))
    return title, chunks
