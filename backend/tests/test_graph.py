"""
Tests de app.agents.graph — pas de couverture exhaustive, seulement le
routage critique du graphe LangGraph :
4. a_verifier=true avec donnée présente -> continue vers calcul
5. Aucune donnée exploitable -> erreur_extraction
6. erreur_calcul -> continue quand même vers indexation/generation

Tourne offline : extraction (GPT-4o), calcul carbone, indexation RAG,
génération de rapport et webhook n8n sont tous mockés. Les nœuds ne sont
pas testés en lançant le graphe compilé (ce qui repartirait de START et
appellerait la vraie extraction) mais appelés directement, comme fait
manuellement lors du développement du graphe.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.agents import graph as graph_module


def _base_invoice_data(**overrides) -> dict:
    data = {
        "electricity_kwh": None,
        "gas_m3": None,
        "waste_tons": None,
        "logistics_km": None,
        "invoice_number": "TEST-001",
        "invoice_date": "01/01/2026",
        "billing_period": "01/01/2026 — 31/01/2026",
        "supplier": "Fournisseur Test",
        "amount_total": 10.0,
        "a_verifier": False,
        "raison_verification": None,
    }
    data.update(overrides)
    return data


def test_a_verifier_true_avec_donnee_continue_vers_calcul():
    """a_verifier=true mais une consommation réelle est présente (gas_m3) :
    le routage doit continuer vers calcul, pas partir en erreur_extraction."""

    state = {
        "invoice_data": _base_invoice_data(
            gas_m3=500,
            a_verifier=True,
            raison_verification="Test : gas_m3 présent malgré a_verifier",
        ),
        "log": [],
    }

    result = graph_module.verification_node(state)
    merged = {**state, **result}

    assert result["extraction_ok"] is True
    assert result["a_verifier"] is True
    assert graph_module.route_after_verification(merged) == "ok"


def test_aucune_donnee_exploitable_route_vers_erreur_extraction():
    """Si electricity_kwh/gas_m3/waste_tons/logistics_km sont tous None, le
    routage doit partir en erreur_extraction, même si a_verifier=true."""

    state = {
        "invoice_data": _base_invoice_data(
            a_verifier=True,
            raison_verification="Facture de mensualisation, aucune consommation réelle",
        ),
        "log": [],
    }

    result = graph_module.verification_node(state)
    merged = {**state, **result}

    assert result["extraction_ok"] is False
    assert graph_module.route_after_verification(merged) == "fail"


def test_erreur_calcul_continue_vers_indexation_et_generation(tmp_path, monkeypatch):
    """Si calculate_carbon_emissions ne trouve aucun facteur, le routage part
    en erreur_calcul, mais indexation et generation s'exécutent quand même
    (pas de crash, pas de blocage)."""

    fake_carbon_data = {
        "details": [
            {
                "champ": "electricity_kwh",
                "scope": "scope 2",
                "quantite": 100,
                "emissions_kgco2e": None,
                "source": {"origine": "aucun facteur trouvé"},
            }
        ],
        "emissions_totales_kgco2e": 0.0,
    }

    monkeypatch.setattr(graph_module, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(graph_module, "calculate_carbon_emissions", lambda invoice_data: fake_carbon_data)
    monkeypatch.setattr(
        graph_module,
        "index_invoice",
        lambda invoice_data: {"status": "success", "document_id": "TEST-001", "collection": "energy-invoices"},
    )
    monkeypatch.setattr(graph_module, "retrieve_context", lambda invoice_data: "contexte factice")
    monkeypatch.setattr(
        graph_module,
        "generate_csrd_report",
        lambda invoice_data, carbon_data, context: "Rapport factice",
    )
    monkeypatch.setattr(graph_module, "_notify_webhook", lambda payload: {"ok": True, "detail": "mock"})

    state = {
        "invoice_data": _base_invoice_data(electricity_kwh=100),
        "extraction_ok": True,
        "log": [],
    }

    # 1. calcul -> doit signaler l'echec
    result_calcul = graph_module.calcul_node(state)
    state = {**state, **result_calcul, "log": state["log"] + result_calcul["log"]}
    assert result_calcul["calcul_ok"] is False
    assert graph_module.route_after_calcul(state) == "fail"

    # 2. erreur_calcul -> marque le statut, ne doit pas etre un cul-de-sac
    result_erreur = graph_module.erreur_calcul_node(state)
    state = {**state, **result_erreur, "log": state["log"] + result_erreur["log"]}
    assert state["status"] == "erreur_calcul"

    # 3. indexation ne doit pas etre bloquee par l'echec du calcul
    result_indexation = graph_module.indexation_node(state)
    state = {**state, **result_indexation, "log": state["log"] + result_indexation["log"]}
    assert result_indexation["rag_result"]["status"] == "success"

    # 4. generation continue aussi (rapport + webhook mockes, pas de crash)
    result_generation = graph_module.generation_node(state)
    state = {**state, **result_generation, "log": state["log"] + result_generation["log"]}
    assert result_generation["report"] == "Rapport factice"
    assert result_generation["status"] == "erreur_calcul"  # conserve, pas ecrase par "success"

    decisions = [entry["decision"] for entry in state["log"]]
    assert "erreur_calcul" in decisions
    assert "continue_indexation" in decisions
    assert "webhook_ok" in decisions
