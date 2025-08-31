# corpus/extractor/ocr.py
from __future__ import annotations
from typing import Iterable, Tuple, Optional
from pathlib import Path
import shutil
import pytesseract
from PIL import Image
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

def _resolve_tesseract_cmd() -> str:
    """Normalise et valide le chemin tesseract, ou trouve 'tesseract' dans le PATH."""
    cfg = get_settings().ocr
    cmd = (cfg.tesseract_cmd or "").strip().strip('"').strip("'")
    if cmd:
        # éviter les effets \t -> tabulation dans les logs et normaliser le chemin
        cmd = str(Path(cmd.replace("\\", "/")).resolve())
        if not Path(cmd).exists():
            raise FileNotFoundError(f"Tesseract introuvable: {cmd}")
        pytesseract.pytesseract.tesseract_cmd = cmd
        return cmd
    found = shutil.which("tesseract")
    if not found:
        raise FileNotFoundError(
            "Tesseract introuvable. Renseignez settings.ocr.tesseract_cmd ou ajoutez-le au PATH."
        )
    pytesseract.pytesseract.tesseract_cmd = found
    return found

def ocr_pil_image(img: Image.Image, languages: Iterable[str] = ("eng",)) -> tuple[str, float]:
    """
    OCR sur image PIL, retour (texte, avg_conf).
    psm 4 (colonnes) → fallback psm 6 (blocs).
    """
    _resolve_tesseract_cmd()
    lang = "+".join(languages) if languages else "eng"

    try:
        data = pytesseract.image_to_data(
            img, lang=lang, output_type=pytesseract.Output.DICT, config="--oem 1 --psm 4"
        )
    except Exception:
        data = pytesseract.image_to_data(
            img, lang=lang, output_type=pytesseract.Output.DICT, config="--oem 1 --psm 6"
        )

    texts, confs = [], []
    for t, c in zip(data.get("text", []), data.get("conf", [])):
        t = (t or "").strip()
        if not t:
            continue
        texts.append(t)
        try:
            confs.append(float(c))
        except Exception:
            pass
    avg_conf = sum(confs) / len(confs) if confs else 0.0
    return " ".join(texts), avg_conf






# # corpus/extractor/ocr.py
# from __future__ import annotations
# import pytesseract, os
# from app.core.resources import get_settings
# from PIL import Image
# from pathlib import Path
# from shutil import which
# from typing import Iterable, Tuple, Optional
# from app.core.logging import get_logger

# # NB : l’activation se pilote via settings.ocr.enabled et settings.ocr.languages déjà présents dans YAML

# logger = get_logger(__name__)

# # Flag module-level pour initialisation lazy
# _OCR_READY = False

# def _normalize_cmd(cmd: str) -> str:
#     """
#     Rendez le chemin « safe » :
#     - Corrige un éventuel TAB réel (ex: '\t' devenu tab) -> remet 't'
#     - Utilise des slashes (tolérés par Windows)
#     """
#     if "\t" in cmd:
#         # cas que vous rencontrez : YAML/env a transformé '\t' en TAB
#         cmd = cmd.replace("\t", "t")
#     cmd = cmd.replace("\\", "/")
#     return cmd

# def _find_tesseract_cmd(explicit: Optional[str]) -> str:
#     # 1) valeur de la conf
#     candidates = []
#     if explicit:
#         candidates.append(_normalize_cmd(explicit))

#     # 2) PATH système
#     auto = which("tesseract")
#     if auto:
#         candidates.append(_normalize_cmd(auto))

#     # 3) chemins par défaut Windows
#     candidates += [
#         "C:/Program Files/Tesseract-OCR/tesseract.exe",
#         "C:/Program Files (x86)/Tesseract-OCR/tesseract.exe",
#     ]

#     for c in candidates:
#         if c and Path(c).exists():
#             return c

#     raise FileNotFoundError(
#         "Tesseract introuvable. "
#         "Vérifiez .env TESSERACT_CMD ou ajoutez Tesseract au PATH."
#     )

# def _ensure_ocr_ready() -> dict:
#     global _OCR_READY
#     if _OCR_READY:
#         return {}

#     cfg = get_settings().ocr
#     cmd = _find_tesseract_cmd(cfg.tesseract_cmd)
#     pytesseract.pytesseract.tesseract_cmd = cmd

#     # TESSDATA : langues (eng, fra, ara…)
#     tessdata = os.getenv("TESSDATA_PREFIX") or str(Path(cmd).parent / "tessdata")
#     os.environ["TESSDATA_PREFIX"] = tessdata

#     ver = str(pytesseract.get_tesseract_version())
#     logger.info(f"Tesseract OK | cmd={cmd} | version={ver} | tessdata={tessdata}")
#     _OCR_READY = True
#     return {"cmd": cmd, "version": ver, "tessdata": tessdata}

# # ---------- API utilitaires (appelées par pdf.py) ----------

# def ocr_pil_image(img: Image.Image, languages: Iterable[str] = ("eng",)) -> str:
#     if pytesseract is None or img is None:
#         return ""
#     _ensure_ocr_ready()
#     lang = "+".join(languages) if languages else "eng"
#     try:
#         return pytesseract.image_to_string(img, lang=lang) or ""
#     except Exception:
#         return ""

# def ocr_pdfplumber_page(page, languages: Iterable[str] = ("eng",)) -> str:
#     """Rasterise une page (300 dpi) et applique l'OCR.
#        NB: 'page' est un objet pdfplumber.Page
#     """
#     try:
#         im = page.to_image(resolution=300).original  # PIL.Image
#     except Exception:
#         return ""
#     return ocr_pil_image(im, languages)

# # (optionnel) petit diag pour la route de santé
# def ocr_diagnostics() -> dict:
#     try:
#         info = _ensure_ocr_ready()
#         return {"ok": True, **info}
#     except Exception as e:
#         return {"ok": False, "error": str(e)}
