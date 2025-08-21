# corpus/extractor/ocr.py

# OCR FR/AR : on le branche dans un ocr.py (Tesseract/rapidocr) appelé par PdfExtractor seulement quand extract_text() 
# est pauvre et si settings.ocr.enabled=True. On pourra affiner (détection de blocs, tables, sens RTL).