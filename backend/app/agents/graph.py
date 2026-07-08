import json
import logging
import operator
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional, TypedDict

import requests
from langgraph.graph import END, START, StateGraph

from app.ocr.gpt4o import extract_invoice_data_with_gpt4o
from app.rag.ingestion import CONSUMPTION_FIELDS
from app.rag.rag import index_invoice, retrieve_context
from app.services.carbon import calculate_carbon_emissions
from app.services.report import generate_csrd_report

logger = logging.getLogger(__name__)

CONSUMPTION_KEYS = list(CONSUMPTION_FIELDS)
SCOPE_ORDER = ["scope 1", "scope 2", "scope 3"]

# backend/app/agents/graph.py -> parents[2] = backend/
REPORTS_DIR = Path(__file__).resolve().parents[2] / "data" / "reports"

# URL de production n8n (workflow actif, plus besoin d'ouvrir l'éditeur n8n).
WEBHOOK_URL = "http://localhost:5678/webhook/rapport-csrd"
WEBHOOK_TIMEOUT_SECONDS = 5


class EdenState(TypedDict, total=False):
    file_path: str
    invoice_data: Optional[dict]
    carbon_data: Optional[dict]
    rag_result: Optional[dict]
    report: Optional[str]
    a_verifier: bool
    raison_verification: Optional[str]
    extraction_ok: bool
    calcul_ok: bool
    status: str
    error: Optional[str]
    report_path: Optional[str]
    log: Annotated[list, operator.add]


def _safe_filename_part(value) -> str:
    if not value:
        return "sans_numero"
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(value))


def _log_entry(node: str, decision: str, raison: str) -> dict:
    return {
        "node": node,
        "decision": decision,
        "raison": raison,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _format_scopes(details: list) -> str:
    scopes = sorted(
        {d["scope"] for d in details if d.get("scope") and d.get("emissions_kgco2e") is not None},
        key=lambda s: SCOPE_ORDER.index(s) if s in SCOPE_ORDER else 99,
    )
    return ", ".join(s.capitalize() for s in scopes) if scopes else "Non déterminé"


def _notify_webhook(payload: dict) -> dict:
    """
    Notifie un webhook n8n en fin de pipeline. Best-effort : une panne du
    webhook (n8n non démarré, erreur réseau...) ne doit jamais faire
    échouer le pipeline, seulement être journalisée (log + warning).
    """

    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=WEBHOOK_TIMEOUT_SECONDS)
        response.raise_for_status()
        return {"ok": True, "detail": f"HTTP {response.status_code} : {response.text[:200]}"}
    except requests.exceptions.RequestException as exc:
        return {"ok": False, "detail": str(exc)}


def extraction_node(state: EdenState) -> dict:
    """1. Appelle GPT-4o Vision sur la facture."""

    invoice_data = extract_invoice_data_with_gpt4o(state["file_path"])

    return {
        "invoice_data": invoice_data,
        "log": [_log_entry("extraction", "ok", "Extraction GPT-4o Vision terminée")],
    }


def verification_node(state: EdenState) -> dict:
    """
    2. Vérifie la qualité de l'extraction : échec si aucune donnée de
    consommation exploitable, sinon propage a_verifier/raison_verification
    jusqu'au state final.
    """

    invoice_data = state.get("invoice_data") or {}
    has_data = any(invoice_data.get(key) is not None for key in CONSUMPTION_KEYS)
    a_verifier = bool(invoice_data.get("a_verifier", False))
    raison_verification = invoice_data.get("raison_verification")

    if not has_data:
        return {
            "extraction_ok": False,
            "a_verifier": a_verifier,
            "raison_verification": raison_verification,
            "log": [
                _log_entry(
                    "verification",
                    "erreur_extraction",
                    "Aucune donnée de consommation exploitable "
                    "(electricity_kwh/gas_m3/waste_tons/logistics_km tous null)",
                )
            ],
        }

    if a_verifier:
        decision, raison = "continue_a_verifier", raison_verification or "Champ a_verifier=true renvoyé par l'extraction"
    else:
        decision, raison = "continue", "Donnée(s) de consommation présente(s), rien à signaler"

    return {
        "extraction_ok": True,
        "a_verifier": a_verifier,
        "raison_verification": raison_verification,
        "log": [_log_entry("verification", decision, raison)],
    }


def route_after_verification(state: EdenState) -> str:
    return "ok" if state.get("extraction_ok") else "fail"


def erreur_extraction_node(state: EdenState) -> dict:
    """Route de sortie si l'extraction n'a produit aucune donnée exploitable."""

    return {
        "status": "erreur_extraction",
        "error": "Aucune donnée de consommation exploitable extraite de la facture.",
        "log": [
            _log_entry(
                "erreur_extraction",
                "fin",
                "Pipeline arrêté : pas de calcul ni de génération de rapport possibles",
            )
        ],
    }


def calcul_node(state: EdenState) -> dict:
    """3. Calcule les émissions carbone si la vérification est passée."""

    carbon_data = calculate_carbon_emissions(state["invoice_data"])
    details = carbon_data.get("details", [])
    found_any_factor = any(d.get("emissions_kgco2e") is not None for d in details)

    if not found_any_factor:
        return {
            "carbon_data": carbon_data,
            "calcul_ok": False,
            "log": [
                _log_entry(
                    "calcul",
                    "erreur_calcul",
                    "Aucun facteur d'émission trouvé (ni JSON direct ni RAG) "
                    "pour les données présentes",
                )
            ],
        }

    return {
        "carbon_data": carbon_data,
        "calcul_ok": True,
        "log": [
            _log_entry(
                "calcul",
                "ok",
                f"{len(details)} champ(s) traité(s), "
                f"{carbon_data.get('emissions_totales_kgco2e')} kgCO2e au total",
            )
        ],
    }


def route_after_calcul(state: EdenState) -> str:
    return "ok" if state.get("calcul_ok") else "fail"


def erreur_calcul_node(state: EdenState) -> dict:
    """
    Marque l'échec du calcul carbone sans bloquer la suite du pipeline :
    l'indexation RAG peut réussir indépendamment du calcul.
    """

    return {
        "status": "erreur_calcul",
        "error": "Aucun facteur d'émission n'a été trouvé pour cette facture.",
        "log": [
            _log_entry(
                "erreur_calcul",
                "continue_indexation",
                "Le calcul a échoué mais l'indexation RAG et la génération du "
                "rapport continuent indépendamment",
            )
        ],
    }


def indexation_node(state: EdenState) -> dict:
    """4. Indexe la facture dans Chroma (RAG)."""

    rag_result = index_invoice(state["invoice_data"])

    return {
        "rag_result": rag_result,
        "log": [
            _log_entry(
                "indexation",
                "ok",
                f"Facture indexée dans Chroma (id={rag_result.get('document_id')})",
            )
        ],
    }


def generation_node(state: EdenState) -> dict:
    """5. Génère le rapport CSRD et le persiste sur disque."""

    context = retrieve_context(state["invoice_data"])
    carbon_data = state.get("carbon_data") or {"details": [], "emissions_totales_kgco2e": 0.0}

    report = generate_csrd_report(
        invoice_data=state["invoice_data"],
        carbon_data=carbon_data,
        context=context,
    )

    invoice_number = _safe_filename_part(state["invoice_data"].get("invoice_number"))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base_name = f"rapport_csrd_{invoice_number}_{timestamp}"
    report_path = REPORTS_DIR / f"{base_name}.md"
    summary_path = REPORTS_DIR / f"{base_name}.json"

    final_status = state.get("status") or "success"

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    # Résumé structuré à côté du rapport texte : c'est la source de données
    # utilisée par le dashboard (suivi des extractions, indicateurs par
    # scope, évolution temporelle) pour éviter d'avoir à re-parser le
    # rapport en markdown.
    summary = {
        "invoice_number": state["invoice_data"].get("invoice_number"),
        "supplier": state["invoice_data"].get("supplier"),
        "invoice_date": state["invoice_data"].get("invoice_date"),
        "status": final_status,
        "a_verifier": state.get("a_verifier", False),
        "raison_verification": state.get("raison_verification"),
        "carbon_data": carbon_data,
        "report_path": str(report_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    log_entries = [
        _log_entry("generation", "ok", f"Rapport CSRD généré et sauvegardé dans {report_path}")
    ]

    # Notification best-effort vers n8n : ne doit jamais bloquer le pipeline.
    webhook_payload = {
        "fournisseur": state["invoice_data"].get("supplier"),
        "co2eq_total": carbon_data.get("emissions_totales_kgco2e"),
        "scope": _format_scopes(carbon_data.get("details") or []),
        "report_path": str(report_path),
        "invoice_number": state["invoice_data"].get("invoice_number"),
    }
    webhook_result = _notify_webhook(webhook_payload)

    if webhook_result["ok"]:
        log_entries.append(
            _log_entry("generation", "webhook_ok", f"Webhook n8n notifié : {webhook_result['detail']}")
        )
    else:
        logger.warning("Webhook n8n injoignable (%s) : %s", WEBHOOK_URL, webhook_result["detail"])
        log_entries.append(
            _log_entry(
                "generation",
                "webhook_echec",
                f"Webhook n8n injoignable, pipeline non bloqué : {webhook_result['detail']}",
            )
        )

    return {
        "report": report,
        "report_path": str(report_path),
        "status": final_status,
        "log": log_entries,
    }


def _build_graph():
    graph = StateGraph(EdenState)

    graph.add_node("extraction", extraction_node)
    graph.add_node("verification", verification_node)
    graph.add_node("erreur_extraction", erreur_extraction_node)
    graph.add_node("calcul", calcul_node)
    graph.add_node("erreur_calcul", erreur_calcul_node)
    graph.add_node("indexation", indexation_node)
    graph.add_node("generation", generation_node)

    graph.add_edge(START, "extraction")
    graph.add_edge("extraction", "verification")

    graph.add_conditional_edges(
        "verification",
        route_after_verification,
        {"ok": "calcul", "fail": "erreur_extraction"},
    )
    graph.add_edge("erreur_extraction", END)

    graph.add_conditional_edges(
        "calcul",
        route_after_calcul,
        {"ok": "indexation", "fail": "erreur_calcul"},
    )
    graph.add_edge("erreur_calcul", "indexation")
    graph.add_edge("indexation", "generation")
    graph.add_edge("generation", END)

    return graph.compile()


_compiled_graph = _build_graph()


def run_eden(file_path: str) -> dict:
    """
    Exécute le pipeline EDEN comme un graphe LangGraph :
    extraction -> vérification -> calcul -> indexation -> génération,
    avec routes d'erreur explicites (erreur_extraction, erreur_calcul).
    """

    initial_state: EdenState = {"file_path": file_path, "log": []}
    return _compiled_graph.invoke(initial_state)
