from fastapi import FastAPI
from app.api.extract import router as extract_router

app = FastAPI(
    title="EDEN API",
    description="Backend de l'application EDEN - Agent CSRD et décarbonation",
    version="0.1.0",
)

# Ajout des routes de l'API
app.include_router(extract_router)


@app.get("/health")
def health_check():
    """
    Vérifie que l'API EDEN fonctionne.
    """
    return {
        "status": "ok",
        "message": "EDEN API is running"
    }