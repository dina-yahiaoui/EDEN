"""
Nettoyage one-shot de la Base Carbone ADEME pour le MVP EDEN.

Entree : backend/knowledge/ademe/base_carbone.csv
Sortie : backend/knowledge/ademe/facteurs_clean.json (electricite + gaz uniquement)

Le detail des categories Transport / Dechets est affiche en console pour
permettre de choisir lesquelles garder avant de figer leurs cles dans le JSON.
"""

import json
import re
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
CSV_PATH = BASE_DIR / "knowledge" / "ademe" / "base_carbone.csv"
OUTPUT_PATH = BASE_DIR / "knowledge" / "ademe" / "facteurs_clean.json"

STATUTS_VALIDES = ["Valide générique", "Valide spécifique"]

BRANCHES = {
    "Electricité": "Electricité > Mix réseau électrique > France continentale > Moyen",
    "Gaz": "Combustibles > Fossiles > Gazeux > Gaz naturel",
    "Transport": "Transport",
    "Déchets": "Traitement des déchets",
}


def normalize(value) -> str:
    """
    Cle de comparaison insensible aux accents, a la casse et a la corruption
    d'encodage du CSV source (voir note en tete de main()) : on ne garde que
    les caracteres a-z0-9, donc un caractere accentue correct et un caractere
    corrompu a la meme position se reduisent tous les deux a rien.
    """
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def find_column(df: pd.DataFrame, label: str) -> str:
    key = normalize(label)
    for col in df.columns:
        if key in normalize(col):
            return col
    raise KeyError(f"Colonne introuvable pour : {label!r}")


def to_float(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().replace(",", ".").replace(" ", "")
    if not text or text.lower() == "nan":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def load_ademe(csv_path: Path) -> pd.DataFrame:
    return pd.read_csv(csv_path, sep=";", encoding="cp1252", low_memory=False)


def preview_categories(df: pd.DataFrame, cols: dict, mask: pd.Series, label: str) -> None:
    sub = df[mask]
    print(f"--- Catégories disponibles pour {label} ({sub[cols['cat']].nunique()} catégories, {len(sub)} lignes) ---")

    grouped = (
        sub.groupby(cols["cat"])
        .agg(
            nb_lignes=(cols["id"], "count"),
            unites=(cols["unite"], lambda s: ", ".join(sorted(set(s.dropna().astype(str))))),
            exemple=(cols["nombase"], lambda s: next((v for v in s if pd.notna(v)), "")),
        )
        .reset_index()
        .sort_values("nb_lignes", ascending=False)
    )

    for _, row in grouped.iterrows():
        print(f"  [{row['nb_lignes']:>4} lignes] {row[cols['cat']]}")
        print(f"      unités : {row['unites']}  |  exemple : {row['exemple']}")
    print()


def select_best_row(df: pd.DataFrame, cols: dict, target_unit_normalized: str) -> pd.Series:
    """Parmi les lignes agrégées (Type poste vide), garde l'unité demandée et prend
    la ligne la plus récemment modifiée dans la Base Carbone."""
    candidates = df[df[cols["unite"]].map(normalize) == target_unit_normalized].copy()
    candidates["_date_modif"] = pd.to_datetime(
        candidates[cols["datemodif"]], dayfirst=True, errors="coerce"
    )
    candidates = candidates.sort_values("_date_modif", ascending=False)
    return candidates.iloc[0]


def main() -> None:
    print(f"Lecture de {CSV_PATH} ...")
    df = load_ademe(CSV_PATH)
    print(f"{len(df)} lignes brutes, {len(df.columns)} colonnes.\n")

    cols = {
        "statut": find_column(df, "Statut de l'élément"),
        "cat": find_column(df, "Code de la catégorie"),
        "id": find_column(df, "Identifiant de l'élément"),
        "nombase": find_column(df, "Nom base français"),
        "nomattr": find_column(df, "Nom attribut français"),
        "unite": find_column(df, "Unité français"),
        "total": find_column(df, "Total poste non décomposé"),
        "locali": find_column(df, "Localisation géographique"),
        "typeposte": find_column(df, "Type poste"),
        "datemodif": find_column(df, "Date de modification"),
    }

    print(
        "Avertissement : le fichier CSV source contient une corruption d'encodage\n"
        "irréversible (chaque caractère accentué, dans l'en-tête ET dans les valeurs,\n"
        "a été remplacé par un caractère de remplacement générique avant l'export).\n"
        "Le filtrage ci-dessous utilise donc des clés normalisées (accents ignorés),\n"
        "ce qui n'affecte pas les valeurs numériques des facteurs. Si les libellés texte\n"
        "doivent être propres, retélécharger le CSV depuis data.ademe.fr.\n"
    )

    # --- Filtre 1 : Statut ---
    statut_norm = df[cols["statut"]].map(normalize)
    valid_targets = {normalize(s) for s in STATUTS_VALIDES}
    valid_mask = statut_norm.isin(valid_targets)
    print(f"Filtre Statut (Valide générique + Valide spécifique, hors Archivé) : {valid_mask.sum()} / {len(df)} lignes\n")

    # --- Filtre 2 : branche de catégorie ---
    cat_norm = df[cols["cat"]].map(normalize)
    branch_masks = {
        label: valid_mask & cat_norm.str.startswith(normalize(prefix))
        for label, prefix in BRANCHES.items()
    }

    print("=== Lignes restantes par branche (Statut valide + catégorie) ===")
    for label, mask in branch_masks.items():
        sub = df[mask]
        print(f"- {label:<12} : {len(sub):>5} lignes, {sub[cols['cat']].nunique():>3} catégories uniques")
    print()

    # --- Constat : chaque catégorie contient plusieurs années/unités ET des
    # sous-lignes décomposées (Amont, Combustion, ...) qui ne sont pas des
    # facteurs utilisables tels quels. On ne garde que les lignes agrégées
    # ("Type poste" vide = "Total poste non décomposé" est bien un total). ---
    aggregate_mask = df[cols["typeposte"]].isna()

    print(
        "Constat : dans Electricité et Gaz, chaque catégorie contient plusieurs\n"
        "années/générations ET des sous-lignes décomposées par poste (Amont,\n"
        "Combustion, Transport et distribution...) qui s'additionnent au total.\n"
        "On ne garde donc que les lignes où 'Type poste' est vide (le total agrégé).\n"
    )
    for label in ["Electricité", "Gaz"]:
        sub = df[branch_masks[label] & aggregate_mask]
        print(f"- {label:<12} après filtre 'total agrégé' : {len(sub)} lignes")
    print()

    # --- Aperçu Transport / Déchets : à choisir avant de figer le JSON ---
    preview_categories(df, cols, branch_masks["Transport"] & aggregate_mask, "Transport")
    preview_categories(df, cols, branch_masks["Déchets"] & aggregate_mask, "Déchets")

    print(
        "Transport et Déchets ne sont PAS écrits dans facteurs_clean.json pour l'instant :\n"
        "choisis les catégories pertinentes selon ce qui apparaît réellement dans tes\n"
        "factures parmi la liste ci-dessus, puis on ajoutera leurs clés au mapping.\n"
    )

    # --- Electricité : plusieurs années disponibles -> on garde la plus récente,
    # en kWh (cohérent avec le champ 'electricity_kwh' du schéma de facture). ---
    elec_candidates = df[branch_masks["Electricité"] & aggregate_mask]
    best_elec = select_best_row(elec_candidates, cols, normalize("kgCO2e/kWh"))
    print(
        f"Électricité retenue : id={best_elec[cols['id']]} | {best_elec[cols['nomattr']]} | "
        f"{best_elec[cols['total']]} {best_elec[cols['unite']]} "
        f"(dernière modification : {best_elec[cols['datemodif']]})"
    )

    # --- Gaz naturel : plusieurs unités disponibles -> on garde le m3, cohérent
    # avec le champ 'gas_m3' du schéma de facture, génération la plus récente. ---
    gaz_candidates = df[branch_masks["Gaz"] & aggregate_mask]
    best_gaz = select_best_row(gaz_candidates, cols, normalize("kgCO2e/m3"))
    print(
        f"Gaz naturel retenu : id={best_gaz[cols['id']]} | {best_gaz[cols['nomattr']]} | "
        f"{best_gaz[cols['total']]} {best_gaz[cols['unite']]} "
        f"(dernière modification : {best_gaz[cols['datemodif']]})\n"
    )

    result = {
        "electricity_france": {
            "nom": "Électricité - mix moyen France continentale",
            "facteur_kgco2e": to_float(best_elec[cols["total"]]),
            "unite": "kWh",
            "source": "ADEME Base Carbone",
        },
        "gas_naturel": {
            "nom": "Gaz naturel - mix moyen",
            "facteur_kgco2e": to_float(best_gaz[cols["total"]]),
            "unite": "m3",
            "source": "ADEME Base Carbone",
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"{len(result)} facteur(s) écrits dans {OUTPUT_PATH}")
    print("(waste_tons / logistics_km à ajouter dans un second temps, une fois les catégories Transport/Déchets choisies)")


if __name__ == "__main__":
    main()
