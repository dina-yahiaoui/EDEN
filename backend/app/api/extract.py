from pathlib import Path
import shutil
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.ocr.tesseract import extract_text_with_tesseract
from app.ocr.parser import parse_invoice_text

router = APIRouter(
    prefix="/extract",
    tags=["Extraction"]
)

@router.post("/")
async def extract_invoice(file: UploadFile = File(...)):
    """
    Reçoit une facture PDF, lance l'OCR Tesseract
    et retourne le texte extrait.
    """

    # Vérification du type de fichier
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Le fichier doit être au format PDF."
        )

    temp_path = None

    try:
        # Création d'un fichier temporaire
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = Path(temp_file.name)

        # OCR
        ocr_text = extract_text_with_tesseract(str(temp_path))

        # Parser
        invoice_data = parse_invoice_text(ocr_text)

        return invoice_data

    finally:
        # Suppression du fichier temporaire
        if temp_path and temp_path.exists():
            temp_path.unlink()