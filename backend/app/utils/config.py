import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ============================
# Racine du projet
# ============================

BASE_DIR = Path(__file__).resolve().parents[3]

# ============================
# Dossiers de données
# ============================

DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EMISSION_FACTORS_DIR = DATA_DIR / "emission_factors"

# ============================
# OCR
# ============================

TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ============================
# Chroma Cloud
# ============================

CHROMA_API_KEY = os.getenv("CHROMA_API_KEY")
CHROMA_TENANT = os.getenv("CHROMA_TENANT")
CHROMA_DATABASE = os.getenv("CHROMA_DATABASE")