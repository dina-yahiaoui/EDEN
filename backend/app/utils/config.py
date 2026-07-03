from pathlib import Path

# Racine du projet (EDEN)
BASE_DIR = Path(__file__).resolve().parents[3]

# Dossiers du projet
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Tesseract
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


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
# Chroma
# ============================

CHROMA_DB_DIR = DATA_DIR / "chroma_db"

# ============================
# OCR
# ============================

TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"