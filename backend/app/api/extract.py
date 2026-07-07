from pathlib import Path
import shutil
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.rag.rag import ingest_knowledge
from fastapi import Body
from app.agents.graph import run_eden

router = APIRouter(
    prefix="/extract",
    tags=["Extraction"]
)

@router.post("/")
async def extract_invoice(file: UploadFile = File(...)):
    """
    Reçoit une facture PDF et la traite via le graphe EDEN (LangGraph) :
    extraction GPT-4o Vision -> vérification -> calcul carbone ->
    indexation RAG -> génération du rapport CSRD.
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

        # Pipeline complet (extraction, vérification, calcul, indexation, génération)
        final_state = run_eden(str(temp_path))

        return {
            "message": "Invoice processed.",
            "status": final_state.get("status"),
            "a_verifier": final_state.get("a_verifier", False),
            "raison_verification": final_state.get("raison_verification"),
            "error": final_state.get("error"),
            "invoice": final_state.get("invoice_data"),
            "carbon": final_state.get("carbon_data"),
            "rag": final_state.get("rag_result"),
            "report": final_state.get("report"),
            "report_path": final_state.get("report_path"),
            "log": final_state.get("log", []),
        }

    finally:
        # Suppression du fichier temporaire
        if temp_path and temp_path.exists():
            temp_path.unlink()




@router.post("/knowledge/ingest")
def ingest_knowledge_api(
    pdf_path: str = Body(...),
    document_name: str = Body(...)
):
    """
    Indexe un document réglementaire dans Chroma.
    """

    return ingest_knowledge(
        pdf_path=pdf_path,
        document_name=document_name,
    )