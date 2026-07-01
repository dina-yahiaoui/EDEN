from fastapi import APIRouter, UploadFile, File

router = APIRouter()


@router.post("/extract")
async def extract_invoice(file: UploadFile = File(...)):
    """
    Reçoit une facture PDF.
    L'OCR sera ajouté dans une prochaine étape.
    """

    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "message": "File received successfully"
    }