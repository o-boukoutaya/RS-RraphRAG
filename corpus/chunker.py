# corpus/chunker.py
from __future__ import annotations
import json, re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, List, Optional, Sequence, Tuple, Dict

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.resources import get_storage
from corpus.models import Document, TextBlock, Chunk


# -----------------------------
# Options & helpers
# -----------------------------
@dataclass
class ChunkOptions:
    # NB: corrige la double définition dans la version précédente
    strategy: str = "sentence"         # 'char'|'word'|'sentence'|'paragraph'|'line'|'recursive'|'tokens'|'llm'
    size: int = 800                    # taille cible d'un chunk
    overlap: int = 150                 # chevauchement
    # pour 'recursive'
    separators: Sequence[str] = ("\n\n", "\n", ".", "•", "،")
    # Pour 'llm'
    use_llm: bool = False
    llm_max_preview_chars: int = 5000  # fenêtre de texte que le LLM observe


def _merge(parts: List[str], size: int, overlap: int) -> List[str]:
    """Fusionne des fragments en chunks d'environ 'size' avec chevauchement 'overlap'."""
    chunks: List[str] = []
    buf = ""
    for part in parts:
        if not part:
            continue
        if len(buf) + len(part) + 1 <= size:
            buf = (buf + " " + part).strip()
        else:
            if buf:
                chunks.append(buf)
            buf = part
    if buf:
        chunks.append(buf)

    # appliquer l'overlap (par concat de fin/début)
    if overlap and overlap > 0 and len(chunks) > 1:
        out: List[str] = []
        for i, ch in enumerate(chunks):
            if i == 0:
                out.append(ch)
            else:
                prev = out[-1]
                tail = prev[-overlap:] if overlap < len(prev) else prev
                out.append((tail + " " + ch).strip())
        return out
    return chunks


# -----------------------------
# Chunker
# -----------------------------
class Chunker:
    def __init__(self, opts: Optional[ChunkOptions] = None, llm: Any = None) -> None:
        self.opts = opts or ChunkOptions()
        self.llm = llm  # objet libre ; si None → heuristiques locales

        # registre des stratégies
        self._strategies: dict[str, Callable[[str], List[str]]] = {
            "char": self.character_split,
            "word": self.word_split,
            "sentence": self.sentence_split,
            "paragraph": self.paragraph_split,
            "line": self.line_split,
            "recursive": self.recursive_split,
            "tokens": self.token_split,  # approximation "mots" (remplaçable par tiktoken)
        }

    # ---------- Stratégies de split ----------
    def character_split(self, text: str) -> List[str]:
        """Divise le texte en chunks de caractères."""
        chunks: List[str] = []
        i = 0
        step = max(1, self.opts.size - self.opts.overlap)
        while i < len(text):
            chunks.append(text[i:i + self.opts.size])
            i += step
        return [c.strip() for c in chunks if c.strip()]

    def word_split(self, text: str) -> List[str]:
        """Divise le texte en chunks de mots."""
        words = re.findall(r"\S+", text)
        parts: List[str] = []
        start = 0
        while start < len(words):
            end = min(start + self.opts.size, len(words))
            parts.append(" ".join(words[start:end]))
            start = end - self.opts.overlap if end < len(words) else end
        return [p.strip() for p in parts if p.strip()]

    def sentence_split(self, text: str) -> List[str]:
        """Divise le texte en chunks de phrases."""
        sentences = re.split(r"(?<=[\.\!\?])\s+", text)
        return _merge([s.strip() for s in sentences if s.strip()], self.opts.size, self.opts.overlap)

    def paragraph_split(self, text: str) -> List[str]:
        """Divise le texte en chunks de paragraphes."""
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        return _merge(paragraphs, self.opts.size, self.opts.overlap)

    def line_split(self, text: str) -> List[str]:
        """Divise le texte en chunks de lignes."""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return _merge(lines, self.opts.size, self.opts.overlap)

    def recursive_split(self, text: str) -> List[str]:
        """Divise le texte en chunks de manière récursive."""
        # on descend les séparateurs jusqu’à atteindre une granularité proche de size
        splits = [text]
        for sep in self.opts.separators:
            tmp: List[str] = []
            for part in splits:
                tmp.extend([p for p in part.split(sep) if p])
            splits = tmp
            avg = sum(len(p) for p in splits) / max(1, len(splits))
            if avg <= self.opts.size * 1.2:
                break
        return _merge([s.strip() for s in splits if s.strip()], self.opts.size, self.opts.overlap)

    def token_split(self, text: str) -> List[str]:
        """Divise le texte en chunks de tokens."""
        # approximation par mots (vous pourrez brancher tiktoken ici)
        return self.word_split(text)

    # ---------- LLM suggestion (optionnel) ----------
    def llm_suggest(self, text: str) -> Tuple[str, int, int]:
        """Retourne (strategy, size, overlap). Fallback heuristique si LLM indisponible."""
        if not self.opts.use_llm or self.llm is None:
            return self._heuristic_suggest(text)

        preview = text[: self.opts.llm_max_preview_chars]
        prompt = (
            "You are a chunking strategist. Given a text preview, propose a chunking strategy "
            "that preserves semantic coherence for RAG.\n"
            "Allowed strategies: char, word, sentence, paragraph, line, recursive, tokens.\n"
            "Return strictly a JSON object with keys: strategy, size, overlap.\n"
            f"Preview:\n{preview}\n"
        )
        try:
            if hasattr(self.llm, "complete"):
                out = self.llm.complete(prompt)  # -> str
            elif hasattr(self.llm, "chat"):
                out = self.llm.chat([{"role": "user", "content": prompt}])  # -> str|obj
            else:
                return self._heuristic_suggest(text)

            s = out if isinstance(out, str) else getattr(out, "content", "")
            blob = re.search(r"\{.*\}", s, re.S)
            cfg = json.loads(blob.group(0)) if blob else {}
            strat = str(cfg.get("strategy", "sentence")).lower()
            size = int(cfg.get("size", self.opts.size))
            overlap = int(cfg.get("overlap", self.opts.overlap))
            if strat not in self._strategies:
                strat = "sentence"
            return (strat, max(100, size), max(0, overlap))
        except Exception:
            return self._heuristic_suggest(text)

    def _heuristic_suggest(self, text: str) -> Tuple[str, int, int]:
        """Heuristique simple pour suggérer (strategy, size, overlap)."""
        n = len(text)
        bullet_rate = text.count("•") + text.count("- ")
        newline_rate = text.count("\n")
        table_like = ("|" in text) or ("," in text and "\n" in text and len(text) / (text.count("\n") + 1) > 40)

        if table_like or bullet_rate > 10 or newline_rate > 20:
            return ("paragraph", min(1000, max(400, n // 50)), 100)
        if n < 2000:
            return ("sentence", 600, 120)
        return ("recursive", 800, 150)

    # ---------- API principale ----------
    def split_text(self, text: str) -> List[str]:
        """Divise un texte en chunks selon la stratégie choisie."""
        strat = self.opts.strategy
        if strat == "llm":
            strat, sz, ov = self.llm_suggest(text)
            self.opts.size, self.opts.overlap = sz, ov
        fn = self._strategies.get(strat, self.sentence_split)
        return fn(text)

    def _keep_whole_block(self, b: TextBlock) -> bool:
        """Règle métier: ne pas découper certaines natures de blocs."""
        btype = ((b.meta or {}).get("type") or "").lower()
        return btype in {"price_panel", "table"}

    def split_blocks(self, blocks: Iterable[TextBlock]) -> List[Chunk]:
        """Divise une série de TextBlock en une série de Chunk."""
        idx = 0
        results: List[Chunk] = []
        for b in blocks:
            if self._keep_whole_block(b):
                # on conserve le bloc tel quel (ex: panneau prix/tableau)
                results.append(
                    Chunk(
                        doc=b.doc,
                        idx=idx,
                        text=b.text,
                        meta={
                            "page": b.page,
                            "strategy": self.opts.strategy,
                            "btype": (b.meta or {}).get("type"),
                            "source": (b.meta or {}).get("source"),
                        },
                    )
                )
                idx += 1
                continue

            # sinon on découpe suivant la stratégie choisie
            for txt in self.split_text(b.text):
                results.append(
                    Chunk(
                        doc=b.doc,
                        idx=idx,
                        text=txt,
                        meta={
                            "page": b.page,
                            "strategy": self.opts.strategy,
                            "btype": (b.meta or {}).get("type"),
                            "source": (b.meta or {}).get("source"),
                        },
                    )
                )
                idx += 1
        return results


# -----------------------------
# Runner série (consomme extracted/*blocks.jsonl)
# -----------------------------
class ChunkRunner:
    def __init__(self, opts: Optional[ChunkOptions] = None) -> None:
        self.opts = opts or ChunkOptions()
        self.cfg = get_settings()
        self.storage = get_storage()
        self.log = get_logger("chunker")

    def _load_blocks(self, path: Path) -> List[TextBlock]:
        """
        Charge les blocs de texte à partir d'un fichier JSONL.
        """
        items: List[TextBlock] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                doc = Document(**data["doc"])
                items.append(
                    TextBlock(
                        doc=doc,
                        page=data.get("page"),
                        order=data.get("order"),
                        text=data.get("text", ""),
                        bbox=data.get("bbox"),
                        lang=data.get("lang"),
                        meta=data.get("meta") or {},
                    )
                )
            except Exception:
                # fallback minimal
                d = Document(series=path.parents[1].name, filename=path.stem, path=str(path))
                items.append(TextBlock(doc=d, page=1, order=0, text=line, meta={}))
        return items

    def _write_chunks(self, out_path: Path, chunks: List[Chunk]) -> None:
        """Écrit les chunks dans un fichier JSONL."""
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            for c in chunks:
                f.write(json.dumps(c.model_dump(), ensure_ascii=False) + "\n")

    def run_series(self, series: str) -> dict:
        """
        Exécute le processus de chunking pour une série de documents.
        """
        series_dir = self.storage.ensure_series(series)
        extracted_dir = series_dir / "extracted"
        report_path = extracted_dir / "_report.json"
        items = json.loads(report_path.read_text(encoding="utf-8")).get("items", []) if report_path.exists() else []

        chunk_dir = series_dir / "chunks"
        chunk_dir.mkdir(parents=True, exist_ok=True)   # ✅ FIX: crée le dossier 'chunks/' systématiquement

        results = []
        total_chunks = 0

        chunker = Chunker(self.opts)

        for it in items:
            if (it.get("status") != "ok") or not it.get("output"):
                continue
            blocks_path = series_dir / it["output"]
            blocks = self._load_blocks(blocks_path)
            chunks = chunker.split_blocks(blocks)
            out_path = chunk_dir / f"{Path(it['filename']).stem}.chunks.jsonl"
            self._write_chunks(out_path, chunks)

            results.append({
                "filename": it["filename"],
                "blocks": len(blocks),
                "chunks": len(chunks),
                "output": str(out_path.relative_to(series_dir)),
                "strategy": self.opts.strategy,
                "size": self.opts.size,
                "overlap": self.opts.overlap,
            })
            total_chunks += len(chunks)

        report = {
            "series": series,
            "strategy": self.opts.strategy,
            "size": self.opts.size,
            "overlap": self.opts.overlap,
            "items": results,
            "total_chunks": total_chunks,
        }

        chunk_dir.mkdir(parents=True, exist_ok=True)
        # maintenant le dossier existe toujours → pas d'exception
        (chunk_dir / "_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report


# Utilitaire simple (API stable existante)
def by_tokens(blocks: Iterable[TextBlock], max_tokens=600, overlap=80) -> List[Chunk]:
    """
    Divise les blocs de texte en chunks basés sur le nombre de tokens.
    """
    opts = ChunkOptions(strategy="tokens", size=max_tokens, overlap=overlap)
    return Chunker(opts).split_blocks(blocks)
