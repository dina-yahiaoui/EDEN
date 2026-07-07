# LEGACY : ce module n'est plus utilisé par défaut depuis la semaine 2.
# app/ocr/gpt4o.py (GPT-4o Vision) est le moteur d'extraction actif,
# branché sur POST /extract/ dans api/extract.py. Conservé ici pour
# référence et comme repli local/gratuit potentiel, pas maintenu au même
# niveau (voir docs/specifications_mvp.md, section "choix techniques").

from pathlib import Path

import pytesseract
from pdf2image import convert_from_path

from app.utils.config import TESSERACT_CMD

# Configuration de l'exécutable Tesseract
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def extract_text_with_tesseract(file_path: str) -> str:
    """
    Extrait le texte d'une facture PDF avec Tesseract OCR.

    Args:
        file_path: Chemin du fichier PDF.

    Returns:
        Le texte brut extrait de toutes les pages du document.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {file_path}")

    # Conversion du PDF en images
    pages = convert_from_path(path)

    # Liste qui contiendra le texte de chaque page
    texts = []

    for page in pages:
        text = pytesseract.image_to_string(
            page,
            lang="fra"  # Modèle français de Tesseract
        )
        texts.append(text)

    # Fusion du texte de toutes les pages
    return "\n".join(texts)