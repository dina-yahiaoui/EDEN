"""
Tests de app.services.carbon — pas de couverture exhaustive, seulement les
cas critiques pour la fiabilité du calcul carbone :
1. Calcul avec un facteur cœur JSON direct connu (CO2eq + scope exacts)
2. Aucun facteur trouvé (ni JSON ni RAG) -> signal clair, pas de crash
   silencieux ni de résultat inventé
3. Chaque champ de consommation est associé au bon scope GHG Protocol

Tourne offline : le RAG (Chroma) est mocké, seul facteurs_clean.json (fichier
local du projet) est lu réellement pour les cas JSON direct.
"""

from unittest.mock import patch

import pytest

from app.services import carbon


def test_calcul_simple_facteur_json_direct():
    """electricity_kwh=100 doit résoudre via facteurs_clean.json et calculer
    le CO2eq et le scope exacts, sans appel réseau."""

    expected_factor = carbon.CORE_FACTORS["electricity_france"]["facteur_kgco2e"]
    expected_emissions = round(100 * expected_factor, 2)

    result = carbon.calculate_carbon_emissions({"electricity_kwh": 100})

    assert len(result["details"]) == 1
    detail = result["details"][0]

    assert detail["champ"] == "electricity_kwh"
    assert detail["scope"] == "scope 2"
    assert detail["facteur_kgco2e_par_unite"] == expected_factor
    assert detail["emissions_kgco2e"] == expected_emissions
    assert detail["source"]["origine"] == "JSON direct (facteurs_clean.json)"
    assert result["emissions_totales_kgco2e"] == expected_emissions


def test_aucun_facteur_trouve_ni_json_ni_rag():
    """
    logistics_km n'a jamais de facteur cœur direct (toujours RAG, cf.
    FIELD_TO_FACTOR_KEY). En mockant le RAG pour ne rien trouver, le
    résultat doit être un signal clair (emissions_kgco2e=None + message
    explicite), pas un crash ni un chiffre inventé.
    """

    with patch.object(carbon, "get_factor_from_rag", return_value=None):
        result = carbon.calculate_carbon_emissions({"logistics_km": 50})

    assert len(result["details"]) == 1
    detail = result["details"][0]

    assert detail["champ"] == "logistics_km"
    assert detail["emissions_kgco2e"] is None
    assert detail["source"]["origine"] == "aucun facteur trouvé"
    assert result["emissions_totales_kgco2e"] == 0.0


@pytest.mark.parametrize(
    "field, quantity, expected_scope",
    [
        ("electricity_kwh", 10, "scope 2"),
        ("gas_m3", 10, "scope 1"),
        ("waste_tons", 1, "scope 3"),
        ("logistics_km", 10, "scope 3"),
    ],
)
def test_scope_par_champ(field, quantity, expected_scope):
    """Chaque champ de consommation doit toujours porter le bon scope GHG
    Protocol, que le facteur soit trouvé ou non (mock RAG pour logistics_km,
    seul champ sans facteur cœur direct, afin de rester offline)."""

    with patch.object(carbon, "get_factor_from_rag", return_value=None):
        result = carbon.calculate_carbon_emissions({field: quantity})

    assert result["details"][0]["scope"] == expected_scope


def test_champ_absent_ne_produit_aucun_detail():
    """Un champ à None (ou absent) ne doit générer aucune entrée de detail."""

    result = carbon.calculate_carbon_emissions({"electricity_kwh": None})

    assert result["details"] == []
    assert result["emissions_totales_kgco2e"] == 0.0
