from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]

csv_path = BASE_DIR / "knowledge" / "ademe" / "base_carbone.csv"
pd.set_option("display.max_columns", None)
pd.set_option("display.max_colwidth", None)
df = pd.read_csv(
    csv_path,
    sep=";",
    encoding="cp1252",
    low_memory=False,
)

# Recherche des mots clés
keywords = [
    "mix électrique",
    "électricité réseau",
    "électricité France",
    "France métropolitaine",
    "kWh électrique",
    "gaz naturel"
]

for keyword in keywords:
    print(f"\n========== {keyword.upper()} ==========\n")

    result = df[
        df.astype(str)
        .apply(lambda row: row.str.contains(keyword, case=False, na=False).any(), axis=1)
    ]

    print(
    result[[
        "Nom base franï¿½ais",
        "Nom attribut franï¿½ais",
        "Unitï¿½ franï¿½ais",
        "Total poste non dï¿½composï¿½",
        "CO2f"
    ]].head(20)
)