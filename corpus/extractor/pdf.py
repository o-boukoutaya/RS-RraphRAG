# corpus/extractor/pdf.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
import io, logging, fitz, pytesseract
from pathlib import Path
from PIL import Image
import numpy as np
from corpus.extractor.ocr import ocr_pil_image
import pdfplumber

from app.core.config import get_settings

from .base import BaseExtractor, _allowed_page, _normalize_text
from .registry import register  # veillez à votre import réel (vous aviez "registry.py")
from corpus.utils import normalize_text, preprocess_for_ocr, parse_facts, is_too_sparse
from corpus.models import Document, TextBlock

from app.core.logging import get_logger

logger = get_logger(__name__)

log = logging.getLogger("neo4j")

@dataclass
class _PageExtraction:
    text: str
    source: str              # "pdf" | "ocr"
    lang: Optional[str]
    avg_conf: Optional[float]
    blocks: List[Tuple[Tuple[float, float, float, float], str]]  # (bbox, text)

@register(".pdf")
class PdfExtractor(BaseExtractor):
    extensions = [".pdf"]

    def _extract_text_pymupdf(self, page) -> _PageExtraction:
        # Texte brut + blocs
        blocks = []
        page_text = page.get_text("text") or ""
        for b in page.get_text("blocks") or []:
            # b = (x0, y0, x1, y1, "text", block_no, ...)
            bbox = (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
            txt = normalize_text(b[4] or "")
            if txt:
                blocks.append((bbox, txt))
        return _PageExtraction(
            text=normalize_text(page_text),
            source="pdf",
            lang=None,
            avg_conf=None,
            blocks=blocks
        )
    
    def _extract_text_ocr(self, page, dpi: int = 300, langs: str = "fra+eng") -> _PageExtraction:
        if Image is None or pytesseract is None:
            return _PageExtraction(text="", source="ocr", lang=None, avg_conf=None, blocks=[])
        # rendu raster haut DPI
        pix = page.get_pixmap(dpi=dpi, alpha=False)  # fond blanc
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        # OpenCV preprocess si dispo
        if np is not None:
            import cv2  # type: ignore
            img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            img_bgr = preprocess_for_ocr(img_bgr)
            img = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
        # OCR data pour confidence + bbox
        try:
            logger.info(f"OCR - tesseract Path: {get_settings().ocr.tesseract_cmd}")
            pytesseract.pytesseract.tesseract_cmd = get_settings().ocr.tesseract_cmd
            data = pytesseract.image_to_data(img, lang=langs, output_type=pytesseract.Output.DICT,
                                             config="--oem 1 --psm 4")  # colonnes
        except Exception:
            data = pytesseract.image_to_data(img, lang=langs, output_type=pytesseract.Output.DICT,
                                             config="--oem 1 --psm 6")  # bloc
        texts, blocks = [], []
        confs = []
        for i in range(len(data["text"])):
            txt = normalize_text(data["text"][i] or "")
            if not txt:
                continue
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            conf = float(data.get("conf", [0]*len(data["text"]))[i] or 0.0)
            if conf >= 0:
                confs.append(conf)
            texts.append(txt)
            blocks.append(((float(x), float(y), float(x + w), float(y + h)), txt))
        joined = normalize_text(" ".join(texts))
        avg_conf = (sum(confs) / len(confs)) if confs else None
        return _PageExtraction(text=joined, source="ocr", lang=None, avg_conf=avg_conf, blocks=blocks)
    
    # --- Optionnel : si j'ai déjà include/exclude dans BaseExtractor / options ---
    def _page_is_selected(self, page_no: int) -> bool:
        """Adapte à ta mécanique d'include/exclude si elle est portée par BaseExtractor/options."""
        try:
            inc = getattr(self, "include_pages_set", None)
            exc = getattr(self, "exclude_pages_set", None)
            if inc and page_no not in inc: 
                return False
            if exc and page_no in exc: 
                return False
        except Exception:
            pass
        return True

    # def extract(self, doc: Document) -> List[TextBlock]:
    #     cfg = get_settings()
    #     ocr_enabled = bool(cfg.ocr.enabled)
    #     ocr_langs = tuple(cfg.ocr.languages or ["eng"])

    #     if fitz is None:
    #         log.error("PyMuPDF (fitz) n'est pas installé.")
    #         return []

    #     res: List[TextBlock] = []
    #     ocr_langs = (doc.meta or {}).get("ocr_langs") or "fra+eng"  # vous passez déjà 'eng,fra' côté route
    #     # uniformiser "eng,fra" -> "eng+fra" pour tesseract
    #     ocr_langs = ocr_langs.replace(",", "+").strip("+")
    #     try:
    #         pdf = fitz.open(doc.path)
    #     except Exception as e:
    #         log.exception("Impossible d'ouvrir PDF: %s", e)
    #         return []

    #     for pno in range(len(pdf)):
    #         page = pdf[pno]
    #         # 1) essai texte natif
    #         nat = self._extract_text_pymupdf(page)
    #         use_ocr = is_too_sparse(nat.text, threshold=60)
    #         # 2) fallback OCR si texte trop pauvre OU doc.meta.ocr=True
    #         if use_ocr or (doc.meta or {}).get("ocr") is True:
    #             ocr = self._extract_text_ocr(page, dpi=330, langs=ocr_langs)
    #             final = ocr if len(ocr.text) > len(nat.text) else nat
    #         else:
    #             final = nat

    #         # construction des TextBlocks
    #         order = 0
    #         if final.blocks:
    #             # heuristique légère: si un bloc contient prix/surface => type=price_panel,
    #             # sinon 'paragraph'
    #             for bbox, txt in final.blocks:
    #                 if not txt.strip():
    #                     continue
    #                 meta = {
    #                     "source": final.source,
    #                     "avg_conf": final.avg_conf,
    #                     "lang": final.lang or "fr",
    #                     "type": "price_panel" if any(k in parse_facts(txt) for k in ("price_from_mad","area_m2","units_count")) else "paragraph"
    #                 }
    #                 res.append(TextBlock(doc=doc, page=pno + 1, order=order, text=txt, bbox=bbox, lang=meta["lang"], meta=meta))
    #                 order += 1
    #         else:
    #             # bloc unique si on n'a pas pu distinguer
    #             meta = {
    #                 "source": final.source,
    #                 "avg_conf": final.avg_conf,
    #                 "lang": final.lang or "fr",
    #                 "type": "paragraph"
    #             }
    #             res.append(TextBlock(doc=doc, page=pno + 1, order=0, text=final.text, bbox=None, lang=meta["lang"], meta=meta))

    #     pdf.close()
    #     return res

    def extract(self, doc: Document) -> List[TextBlock]:
        cfg = get_settings()
        ocr_enabled = bool(cfg.ocr.enabled)
        ocr_langs = tuple(cfg.ocr.languages or ["eng"])

        blocks: List[TextBlock] = []
        with pdfplumber.open(doc.path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                # Filtre include/exclude si tes options les gèrent via BaseExtractor/options
                if not self._page_is_selected(i):
                    continue

                raw = (page.extract_text() or "").strip()
                if raw:
                    blocks.append(TextBlock(
                        doc=doc, page=i, order=0,
                        text=normalize_text(raw),
                        meta={"type": "paragraph", "source": "pdf-text"}
                    ))
                    continue

                if not ocr_enabled:
                    # page image mais OCR désactivé → on logue, on renvoie vide pour cette page
                    logger.warning(f"PDF page {i}: pas de texte natif et OCR désactivé.")
                    continue

                # Rasterise la page puis OCR (300 dpi, couleurs => PIL.Image)
                try:
                    im = page.to_image(resolution=300, antialias=True).original  # PIL.Image
                except Exception:
                    # fallback plus robuste (certaines versions pdfplumber)
                    im = page.to_image(resolution=300).original

                text, conf = ocr_pil_image(im, languages=ocr_langs)
                text = normalize_text(text)
                if text:
                    blocks.append(TextBlock(
                        doc=doc, page=i, order=0,
                        text=text,
                        meta={"type": "paragraph", "source": "pdf-ocr", "ocr_conf": round(conf, 2)}
                    ))
                else:
                    logger.info(f"OCR vide sur {Path(doc.path).name} page {i}.")

        return blocks

    def _similarity(self, a: str, b: str) -> float:
        """Jaccard très simple pour 'auto' (suffisant pour le routage de granularité)."""
        aw = {w.lower() for w in a.split()}
        bw = {w.lower() for w in b.split()}
        if not aw or not bw: return 0.0
        inter = len(aw & bw); union = len(aw | bw)
        return inter / union if union else 0.0

    def _auto_mode(self, page_texts: List[str]) -> str:
        """Décide 'linked' vs 'per_page' selon la similarité moyenne adjacente."""
        if len(page_texts) <= 2: return "per_page"
        sims = [self._similarity(page_texts[i-1], page_texts[i]) for i in range(1, len(page_texts))]
        return "linked" if (sum(sims) / max(1, len(sims))) >= 0.35 else "per_page"

    # def extract(self, doc: Document) -> List[TextBlock]:
    #     blocks: List[TextBlock] = []
    #     try:
    #         import pdfplumber
    #         from .ocr import ocr_pdfplumber_page
    #     except Exception:
    #         pdfplumber = None
    #         ocr_pdfplumber_page = None  # type: ignore
    #         return blocks

    #     page_texts: List[str] = []
    #     page_sizes: List[Tuple[float,float]] = []

    #     try:
    #         with pdfplumber.open(doc.path) as pdf:
    #             total = len(pdf.pages)
    #             for i, page in enumerate(pdf.pages, start=1):
    #                 if not _allowed_page(i, total, self.options.include_pages, self.options.exclude_pages):
    #                     continue
    #                 txt = page.extract_text() or "" 

    #                 # tables rudimentaires → concatène lignes CSV-like
    #                 try:
    #                     tbls = page.extract_tables() or []
    #                 except Exception:
    #                     tbls = []
    #                 if tbls:
    #                     table_strs = []
    #                     for t in tbls:
    #                         # t: List[List[str|None]] — on normalise
    #                         rows = [",".join([(c or "").replace("\n", " ").strip() for c in row]) for row in t if row]
    #                         if rows:
    #                             table_strs.append("\n".join(rows))
    #                     if table_strs:
    #                         txt = (txt + "\n\n" + "\n\n".join(table_strs)).strip()

    #                 # OCR de secours si page "faible" et OCR activé
    #                 if (self.options.ocr_enabled and len((txt or "").strip()) < 40 and ocr_pdfplumber_page):
    #                     try:
    #                         ocr_txt = ocr_pdfplumber_page(page, self.options.ocr_languages)
    #                         if len(ocr_txt.strip()) > len((txt or "").strip()):
    #                             txt = ocr_txt
    #                     except Exception:
    #                         pass
    #                 txt = _normalize_text(txt)
    #                 page_texts.append(txt)
    #                 page_sizes.append((float(page.width), float(page.height)))
    #     except Exception:
    #         # on renvoie ce qu’on a pu lire
    #         pass

    #     # Routage de granularité
    #     mode = self.options.mode
    #     if mode == "auto":
    #         mode = self._auto_mode(page_texts)

    #     if mode == "linked":
    #         # whole = "\n\n".join(t for t in page_texts if t.strip())
    #         whole = _normalize_text("\n\n".join(t for t in page_texts if t.strip()))
    #         if whole.strip():
    #             blocks.append(TextBlock(doc=doc, page=None, order=0, text=whole, bbox=None))
    #     else:  # per_page
    #         order = 0
    #         for idx, t in enumerate(page_texts, start=1):
    #             if t.strip():
    #                 w, h = page_sizes[idx-1] if idx-1 < len(page_sizes) else (0.0, 0.0)
    #                 blocks.append(TextBlock(doc=doc, page=idx, order=order, text=t, bbox=[0.0, 0.0, w, h]))
    #                 order += 1

    #     return blocks
