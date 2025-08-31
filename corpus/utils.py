# corpus/utils.py
from __future__ import annotations
from datetime import datetime
import re, secrets, unicodedata, io, cv2
from typing import Optional, Tuple, Dict, Any
import logging
import numpy as np

log = logging.getLogger(__name__)

# -------------------- Normalisation texte --------------------

_SERIES_SAFE = re.compile(r"[^0-9A-Za-z_\-]+", re.UNICODE)
_PUA = [
    "\u2028", "\u2029", "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
    "\ufeff", "\u200b", "\u200c", "\u200d", "\u2060", "\xad"  # soft hyphen
]

def normalize_text(s: str) -> str:
    if not s:
        return ""
    # remove control chars & PUA
    s = "".join(ch for ch in s if ch.isprintable() and ch not in _PUA)
    # NFKC
    s = unicodedata.normalize("NFKC", s)
    # fix hyphenation line breaks: "immobili-\ner" -> "immobilier"
    s = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", s)
    # compact whitespace
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s).strip()
    return s



def sanitize_series(value: str | None) -> str | None:
    """Nettoie un nom de série (slug simple). Retourne None si vide."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    value = _SERIES_SAFE.sub("-", value)
    value = re.sub(r"-+", "-", value).strip("-_")
    return value or None

def make_series_id(prefix: str = "series") -> str:
    """Ex: series-20250821-194512-a3f2"""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    rnd = secrets.token_hex(2)  # 4 hex chars
    return f"{prefix}-{ts}-{rnd}"


# -------------------- OCR: pré-traitement OpenCV --------------------

def preprocess_for_ocr(img_bgr) -> "np.ndarray":
    """
    img_bgr: image OpenCV BGR
    Sortie: image binaire/clean pour OCR (OpenCV)
    """
    if cv2 is None or np is None:
        return img_bgr
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    # Contraste adaptatif (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    # Denoise léger
    gray = cv2.medianBlur(gray, 3)
    # Binarisation (Sauvola fallback Otsu)
    try:
        import skimage.filters as skf  # type: ignore
        th = skf.threshold_sauvola(gray, window_size=25, k=0.2)
        bw = (gray > th).astype("uint8") * 255
    except Exception:
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Dé-skew (approx) via moments
    coords = cv2.findNonZero(bw)
    if coords is not None:
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        (h, w) = bw.shape
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        bw = cv2.warpAffine(bw, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return bw

# -------------------- Heuristiques "faits" (prix/surfaces/unités) --------------------

_PRICE_RX = re.compile(r"(\d[\d\s.,]*)\s*(MDH|MAD|DHS|Dh|Dhs|dirhams?)", re.I)
_AREA_RX  = re.compile(r"(\d+(?:[.,]\d+)?)\s*m²|\b(\d+(?:[.,]\d+)?)\s*m2", re.I)
_UNITS_RX = re.compile(r"(\d+)\s*(villas?|appartements?|appartement|villes?)", re.I)

def parse_facts(text: str) -> Dict[str, Any]:
    """Retourne quelques faits normalisés depuis un bloc 'typologie/prix'."""
    facts: Dict[str, Any] = {}
    tx = normalize_text(text)
    # Prix "à partir de"
    m = _PRICE_RX.search(tx)
    if m:
        raw, unit = m.group(1), m.group(2).upper()
        amount = float(re.sub(r"[^\d.]", "", raw.replace(",", ".")))
        if unit in {"MDH"}:  # 1 MDH = 1_000_000 MAD
            amount = amount * 1_000_000.0
            unit = "MAD"
        if unit in {"DHS", "DH", "DHS", "DIRHAMS"}:
            unit = "MAD"
        facts["price_from_mad"] = int(round(amount))
        facts["currency"] = "MAD"
    # Surface
    m2 = _AREA_RX.search(tx)
    if m2:
        area = m2.group(1) or m2.group(2)
        if area:
            facts["area_m2"] = float(area.replace(",", "."))
    # Compteurs d'unités
    mu = _UNITS_RX.search(tx)
    if mu:
        facts["units_count"] = int(mu.group(1))
        facts["units_label"] = mu.group(2).lower()
    return facts

# -------------------- Petites heuristiques utiles --------------------

def is_too_sparse(text: str, threshold: int = 60) -> bool:
    """Heuristique 'page vide' côté extraction texte brut."""
    return len(normalize_text(text)) < threshold