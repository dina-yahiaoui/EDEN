from fastapi import FastAPI

app = FastAPI(
    title="EDEN API",
    description="Backend de l'application EDEN - Agent CSRD et décarbonation",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    """
    Vérifie que l'API EDEN fonctionne.
    """
    return {
        "status": "ok",
        "message": "EDEN API is running"
    }