"""
Indexation one-shot dans Chroma Cloud pour le RAG EDEN.

Sources :
1. Base Carbone ADEME complète (toutes les lignes valides, tous secteurs,
   pas seulement les 4 branches de facteurs_clean.json) -> collection
   'facteurs_emission'.
2. GHG Protocol + CSRD FAQ + ESRS E1 (PDF réglementaires déjà présents
   dans backend/knowledge/) -> collection 'reglementation'.

Réutilise le pipeline RAG existant (app/rag/chroma.py, chunking.py,
loaders.py, rag.py) sans le réécrire : chaque ligne ADEME est déjà un
chunk atomique (pas besoin du RecursiveCharacterTextSplitter), les PDF
passent par ingest_knowledge() qui gère déjà chargement + découpage +
indexation.

Ce script est idempotent : il supprime puis recrée les deux collections
à chaque exécution (pas de doublons en cas de relance).
"""

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

import pandas as pd

from clean_ademe import CSV_PATH, STATUTS_VALIDES, find_column, load_ademe, normalize, to_float
from app.rag.chroma import ChromaManager
from app.rag.rag import FACTORS_COLLECTION, KNOWLEDGE_COLLECTION, ingest_knowledge

BATCH_SIZE = 200

REGULATORY_PDFS = [
    (BACKEND_DIR / "knowledge" / "ghg" / "ghg_protocol.pdf", "GHG Protocol"),
    (BACKEND_DIR / "knowledge" / "csrd" / "csrd_faq.pdf", "CSRD FAQ"),
    (BACKEND_DIR / "knowledge" / "esrs" / "esrs_e1.pdf", "ESRS E1"),
]


def build_label(row: pd.Series, cols: dict) -> str:
    parts = []
    for key in ("nombase", "nomattr", "nomposte"):
        value = row[cols[key]]
        if pd.notna(value) and str(value).strip():
            parts.append(str(value).strip())

    dedup = []
    for part in parts:
        if not dedup or dedup[-1] != part:
            dedup.append(part)

    return " / ".join(dedup) if dedup else "(sans nom)"


def build_text(row: pd.Series, cols: dict, categorie: str, label: str, valeur: float) -> str:
    categorie_lisible = categorie.replace(" > ", ", ")
    valeur_txt = str(valeur).replace(".", ",")
    unite = row[cols["unite"]] if pd.notna(row[cols["unite"]]) else ""
    return f"{categorie_lisible} — {label} : {valeur_txt} {unite}."


def ingest_ademe_factors(limit: int | None = None) -> None:
    print(f"Lecture de {CSV_PATH} ...")
    df = load_ademe(CSV_PATH)

    cols = {
        "statut": find_column(df, "Statut de l'élément"),
        "cat": find_column(df, "Code de la catégorie"),
        "id": find_column(df, "Identifiant de l'élément"),
        "nombase": find_column(df, "Nom base français"),
        "nomattr": find_column(df, "Nom attribut français"),
        "nomposte": find_column(df, "Nom poste français"),
        "unite": find_column(df, "Unité français"),
        "total": find_column(df, "Total poste non décomposé"),
        "locali": find_column(df, "Localisation géographique"),
    }

    valid_targets = {normalize(s) for s in STATUTS_VALIDES}
    valid_mask = df[cols["statut"]].map(normalize).isin(valid_targets)
    valid = df[valid_mask]
    print(f"{len(valid)} lignes valides (Valide générique/spécifique) sur {len(df)} au total.")

    if limit:
        valid = valid.head(limit)
        print(f"Mode test : limité à {len(valid)} lignes.")

    ids, texts, metadatas = [], [], []
    skipped = 0

    for row_index, row in valid.iterrows():
        valeur = to_float(row[cols["total"]])
        if valeur is None:
            skipped += 1
            continue

        categorie = row[cols["cat"]] if pd.notna(row[cols["cat"]]) else ""
        label = build_label(row, cols)

        # "Identifiant de l'élément" n'est pas unique par ligne : un même
        # identifiant est partagé par la ligne agrégée et ses sous-postes
        # décomposés (Amont, Combustion, ...). On utilise l'index de ligne
        # du CSV (unique) comme identifiant Chroma, et on garde
        # l'identifiant ADEME en métadonnée pour la traçabilité.
        ids.append(f"ademe-{row_index}")
        texts.append(build_text(row, cols, categorie, label, valeur))
        metadatas.append(
            {
                "identifiant_ademe": int(row[cols["id"]]),
                "nom_base": str(row[cols["nombase"]]) if pd.notna(row[cols["nombase"]]) else "",
                "nom_attribut": str(row[cols["nomattr"]]) if pd.notna(row[cols["nomattr"]]) else "",
                "categorie": categorie,
                "unite": str(row[cols["unite"]]) if pd.notna(row[cols["unite"]]) else "",
                "valeur": valeur,
                "localisation": str(row[cols["locali"]]) if pd.notna(row[cols["locali"]]) else "",
            }
        )

    print(f"{len(ids)} lignes indexables ({skipped} ignorées, pas de valeur numérique).")

    chroma = ChromaManager()

    try:
        chroma.client.delete_collection(FACTORS_COLLECTION)
        print(f"Collection '{FACTORS_COLLECTION}' existante supprimée (réindexation propre).")
    except Exception:
        pass

    total = len(ids)
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        chroma.add_chunks(
            collection_name=FACTORS_COLLECTION,
            ids=ids[start:end],
            documents=texts[start:end],
            metadatas=metadatas[start:end],
        )
        print(f"  {end}/{total} lignes indexées dans '{FACTORS_COLLECTION}'...")

    print(f"Terminé : {total} facteurs ADEME indexés dans '{FACTORS_COLLECTION}'.\n")


def ingest_regulatory_pdfs() -> None:
    chroma = ChromaManager()
    try:
        chroma.client.delete_collection(KNOWLEDGE_COLLECTION)
        print(f"Collection '{KNOWLEDGE_COLLECTION}' existante supprimée (réindexation propre).")
    except Exception:
        pass

    for pdf_path, document_name in REGULATORY_PDFS:
        if not pdf_path.exists():
            print(f"  ATTENTION : {pdf_path} introuvable, ignoré.")
            continue
        print(f"Indexation de {document_name} ({pdf_path.name}) ...")
        result = ingest_knowledge(str(pdf_path), document_name)
        print(f"  -> {result}")

    print(f"Terminé : documents réglementaires indexés dans '{KNOWLEDGE_COLLECTION}'.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite le nombre de lignes ADEME indexées (pour un test rapide).",
    )
    parser.add_argument(
        "--skip-factors",
        action="store_true",
        help="N'indexe pas la base ADEME (collection facteurs_emission).",
    )
    parser.add_argument(
        "--skip-pdfs",
        action="store_true",
        help="N'indexe pas les PDF réglementaires (collection reglementation).",
    )
    args = parser.parse_args()

    if not args.skip_factors:
        ingest_ademe_factors(limit=args.limit)
    if not args.skip_pdfs:
        ingest_regulatory_pdfs()


if __name__ == "__main__":
    main()
