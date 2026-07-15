from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

# backend/app/api/reports.py -> parents[2] = backend/
REPORTS_DIR = (Path(__file__).resolve().parents[2] / "data" / "reports").resolve()

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/{filename}")
def get_report(filename: str):
    """
    Sert un rapport PDF déjà généré (par agents/graph.py) depuis
    backend/data/reports/.

    Sécurité : filename doit être un simple nom de fichier, jamais un chemin.
    Path(filename).name retire tout séparateur de répertoire ou remontée
    (../, chemin absolu Windows/Unix) ; si le résultat diffère de la valeur
    reçue, c'est qu'elle tentait de sortir du dossier de rapports, donc rejet
    avant même de construire le chemin final.
    """

    if filename != Path(filename).name or not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Nom de fichier invalide.")

    report_path = REPORTS_DIR / filename

    if not report_path.is_file():
        raise HTTPException(status_code=404, detail="Rapport introuvable.")

    return FileResponse(report_path, media_type="application/pdf", filename=filename)
