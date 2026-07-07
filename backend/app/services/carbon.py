import json
from pathlib import Path

from app.rag.chroma import ChromaManager
from app.rag.rag import FACTORS_COLLECTION

FACTORS_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "ademe" / "facteurs_clean.json"

with open(FACTORS_PATH, encoding="utf-8") as f:
    CORE_FACTORS = json.load(f)

# Champ de facture -> clé facteurs_clean.json, uniquement quand l'unité du
# facteur cœur correspond directement à la donnée extraite (kWh, m3, tonne).
# 'logistics_km' n'a pas d'équivalent direct : les facteurs transport du
# JSON sont en kgCO2e/t.km (nécessitent un tonnage), pas en kgCO2e/km seul.
# On passe donc systématiquement par la recherche sémantique pour ce champ.
FIELD_TO_FACTOR_KEY = {
    "electricity_kwh": "electricity_france",
    "gas_m3": "gas_naturel",
    "waste_tons": "dechets_dae",
}

# Classification GHG Protocol par champ de consommation.
FIELD_TO_SCOPE = {
    "electricity_kwh": "scope 2",
    "gas_m3": "scope 1",
    "logistics_km": "scope 3",
    "waste_tons": "scope 3",
}

RAG_QUERY_BY_FIELD = {
    "electricity_kwh": "électricité consommation réseau France kWh",
    "gas_m3": "gaz naturel consommation m3",
    "waste_tons": "déchets non dangereux traitement tonne",
    "logistics_km": "véhicule utilitaire livraison kilomètre",
}

# Unités ADEME acceptables par champ, une fois le préfixe "kgCO2e/" retiré.
# Sert à écarter les résultats sémantiquement proches mais dimensionnellement
# incompatibles (ex : un facteur en kgCO2e/t.km ou /m3.km ne peut pas
# s'appliquer à une distance seule en km, faute de tonnage ou de volume).
COMPATIBLE_UNITS = {
    "electricity_kwh": {"kwh"},
    "gas_m3": {"m3"},
    "waste_tons": {"tonnededechets", "tonne"},
    "logistics_km": {"km"},
}


def _normalize_unit(unite: str) -> str:
    u = (unite or "").strip().lower().replace(" ", "")
    prefix = "kgco2e/"
    return u[len(prefix):] if u.startswith(prefix) else u


def get_core_factor(field: str) -> dict | None:
    """Cherche un facteur cœur directement dans facteurs_clean.json."""
    key = FIELD_TO_FACTOR_KEY.get(field)
    return CORE_FACTORS.get(key) if key else None


def get_factor_from_rag(field: str) -> dict | None:
    """
    Recherche sémantique dans la collection Chroma 'facteurs_emission'
    (base ADEME complète), utilisée quand aucun facteur cœur ne correspond.
    La valeur du facteur est lue dans les métadonnées du résultat, pas dans
    le texte généré, pour garantir l'exactitude du chiffre.

    Ne retient que les résultats dont l'unité est dimensionnellement
    compatible avec le champ recherché (ex : rejette un facteur au m3.km
    ou au t.km pour une simple distance en km).
    """
    query = RAG_QUERY_BY_FIELD.get(field, field)
    compatible = COMPATIBLE_UNITS.get(field)

    try:
        chroma = ChromaManager()
        results = chroma.search_documents(
            collection_name=FACTORS_COLLECTION,
            query=query,
            n_results=10,
        )
    except Exception:
        return None

    metadatas = results.get("metadatas") or [[]]
    if not metadatas or not metadatas[0]:
        return None

    for metadata in metadatas[0]:
        if compatible and _normalize_unit(metadata.get("unite", "")) not in compatible:
            continue

        return {
            "nom": metadata.get("nom_attribut") or metadata.get("nom_base") or "",
            "facteur_kgco2e": metadata.get("valeur"),
            "unite": metadata.get("unite", ""),
            "source": "ADEME Base Carbone (recherche sémantique)",
            "categorie": metadata.get("categorie", ""),
            "identifiant_ademe": metadata.get("identifiant_ademe"),
        }

    return None


def resolve_factor(field: str) -> tuple[dict | None, str]:
    """Retourne (facteur, origine). origine = 'json_direct' | 'rag_semantique' | 'aucun'."""
    core = get_core_factor(field)
    if core:
        return core, "json_direct"

    rag_factor = get_factor_from_rag(field)
    if rag_factor:
        return rag_factor, "rag_semantique"

    return None, "aucun"


def calculate_carbon_emissions(invoice_data: dict) -> dict:
    """
    Calcule les émissions CO2e à partir des données extraites d'une facture.

    Pour chaque type de donnée présent (electricity_kwh, gas_m3, waste_tons,
    logistics_km), cherche le facteur d'émission correspondant : d'abord en
    lookup direct dans facteurs_clean.json (5 facteurs cœur), puis en
    recherche sémantique dans Chroma si aucun ne correspond. La source
    exacte de chaque facteur est renvoyée pour la traçabilité CSRD.
    """

    quantities = {
        "electricity_kwh": invoice_data.get("electricity_kwh"),
        "gas_m3": invoice_data.get("gas_m3"),
        "waste_tons": invoice_data.get("waste_tons"),
        "logistics_km": invoice_data.get("logistics_km"),
    }

    details = []
    total_emissions = 0.0

    for field, quantity in quantities.items():
        if not quantity:
            continue

        factor, origin = resolve_factor(field)

        if not factor or factor.get("facteur_kgco2e") is None:
            details.append(
                {
                    "champ": field,
                    "scope": FIELD_TO_SCOPE.get(field),
                    "quantite": quantity,
                    "emissions_kgco2e": None,
                    "source": {"origine": "aucun facteur trouvé"},
                }
            )
            continue

        emission_factor = factor["facteur_kgco2e"]
        emissions = quantity * emission_factor
        total_emissions += emissions

        details.append(
            {
                "champ": field,
                "scope": FIELD_TO_SCOPE.get(field),
                "quantite": quantity,
                "facteur_kgco2e_par_unite": emission_factor,
                "unite": factor.get("unite", ""),
                "emissions_kgco2e": round(emissions, 2),
                "source": {
                    "origine": "JSON direct (facteurs_clean.json)" if origin == "json_direct" else "Recherche sémantique (Chroma facteurs_emission)",
                    "nom": factor.get("nom", ""),
                    "categorie": factor.get("categorie", ""),
                    "identifiant_ademe": factor.get("identifiant_ademe"),
                },
            }
        )

    return {
        "details": details,
        "emissions_totales_kgco2e": round(total_emissions, 2),
    }
