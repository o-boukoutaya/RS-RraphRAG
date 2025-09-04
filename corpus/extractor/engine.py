# corpus/extractor/engine.py
from __future__ import annotations
import hashlib, json, mimetypes, os, time
from pathlib import Path
from typing import Dict, List, Optional, Type
from app.core.resources import get_storage
from corpus.models import Document, TextBlock
from .base import ExtractOptions
from . import registry
from app.core.logging import get_logger

logger = get_logger(__name__)

def _sha256_file(p: Path) -> str:
    """Calcule le hash SHA-256 d'un fichier."""
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def _detect_lang(text: str) -> Optional[str]:
    """Detecte la langue d'un texte (extrait)."""
    try:
        from langdetect import detect
        sample = text[:2000]
        return detect(sample)
    except Exception:
        return None
    


class ExtractorRunner:
    """Runs the extraction process for a series of documents."""

    def __init__(self, out_dirname: str = "extracted") -> None:
        self.storage = get_storage()
        self.out_dirname = out_dirname

    def _write_jsonl(self, path: Path, blocks: List[TextBlock]) -> None:
        """Écrit les blocs de texte dans un fichier JSONL."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for b in blocks:
                rec = b.model_dump()
                rec["text_len"] = len(b.text)
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _append_history(self, history_path: Path, event: Dict) -> None:
        """Ajoute un événement à l'historique."""
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def run_series(self, series: str, *, options: ExtractOptions | None = None) -> Dict:
        """Exécute le processus d'extraction pour une série de documents."""
        options = options or ExtractOptions()
        series_dir = self.storage.ensure_series(series)
        out_dir = series_dir / self.out_dirname
        out_dir.mkdir(parents=True, exist_ok=True)   # ✅ FIX: crée le dossier 'extracted/' systématiquement
        logger.info(f"ensure out_dir exists: {out_dir.exists()}")
        history = series_dir / "_extract.history.jsonl"

        started = time.time()
        items: List[Dict] = []
        grand_total_chars = 0

        # itère les documents de la série
        for f in sorted(series_dir.iterdir()):
            if not f.is_file(): 
                continue
            ext = f.suffix.lower()
            # ExtractorCls: Type | None = registry.get(ext)
            ExtractorCls: Optional[Type] = registry.get(ext)
            if not ExtractorCls:
                continue

            # métadonnées Document enrichies
            mime, _ = mimetypes.guess_type(f.as_posix())
            doc = Document(
                series=series,
                filename=f.name,
                path=str(f),
                size=os.path.getsize(f),
                mime=mime,
                sha256=_sha256_file(f),
                meta={},  # place pour d'autres tags si besoin
            )

            extractor = ExtractorCls(options)  # options propagées
            t0 = time.time()
            status = "ok"; err = None
            try:
                blocks = extractor.extract(doc)
                # langue (optionnelle)
                for b in blocks:
                    if getattr(b, "lang", None) is None:
                        try:
                            b.lang = _detect_lang(b.text)  # type: ignore[attr-defined]
                        except Exception:
                            pass
            except Exception as exc:
                status = "error"; err = f"{type(exc).__name__}: {exc}"
                blocks = []
            dur = time.time() - t0

            out_path = out_dir / f"{f.stem}.blocks.jsonl"
            chars = sum(len(b.text) for b in blocks)
            grand_total_chars += chars

            if blocks:
                self._write_jsonl(out_path, blocks)

            item = {
                "filename": f.name,
                "ext": ext,
                "blocks": len(blocks),
                "chars": chars,
                "duration_s": round(dur, 3),
                "output": str(out_path.relative_to(series_dir)) if blocks else None,
                "status": status,
                "error": err,
            }
            items.append(item)
            self._append_history(history, {"ts": time.time(), **item})

        report = {
            "series": series,
            "started_at": started,
            "duration_s": round(time.time() - started, 3),
            # "total_docs": total_docs,
            # "ok_docs": ok_docs,
            # "error_docs": err_docs,
            "total_chars": grand_total_chars,
            "items": items,
        }
        # rapport global
        (out_dir / "_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
