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