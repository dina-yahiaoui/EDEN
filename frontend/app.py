"""
Dashboard EDEN (Streamlit) — suivi des factures traitées et des émissions
CO2e calculées par le pipeline (API FastAPI + graphe LangGraph).

Ce dashboard vit dans frontend/ (interface), séparé de backend/ (API et
logique métier) : il ne lit jamais directement le code de backend/app/,
seulement les fichiers qu'il écrit sur disque (backend/data/reports/) et
l'API HTTP qu'il expose.

Lancement : voir README ou la commande donnée en fin de session de travail.
L'API FastAPI doit tourner en parallèle (http://localhost:8000 par défaut)
pour que la page "Upload" fonctionne — les autres pages lisent directement
les résumés déjà écrits sur disque et n'ont pas besoin de l'API.
"""

import json
from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
import requests
import streamlit as st

API_URL = "http://localhost:8000"

# frontend/app.py -> parents[1] = racine du projet -> backend/data/reports/
REPORTS_DIR = Path(__file__).resolve().parents[1] / "backend" / "data" / "reports"

# Couleurs fixes par scope GHG Protocol (jamais de palette auto-générée) :
# scope 1 = combustion directe, scope 2 = énergie achetée, scope 3 = chaîne de valeur.
SCOPE_COLORS = {
    "scope 1": "#D97706",
    "scope 2": "#2563EB",
    "scope 3": "#059669",
}
SCOPE_ORDER = ["scope 1", "scope 2", "scope 3"]


def load_summaries() -> list[dict]:
    """Charge tous les résumés structurés écrits par agents/graph.py."""
    summaries = []
    if not REPORTS_DIR.exists():
        return summaries

    for path in sorted(REPORTS_DIR.glob("*.json")):
        try:
            summaries.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue

    return summaries


def parse_invoice_date(date_str: str | None):
    if not date_str:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def scopes_covered(details: list[dict]) -> str:
    scopes = sorted(
        {d["scope"] for d in details if d.get("scope") and d.get("emissions_kgco2e") is not None},
        key=lambda s: SCOPE_ORDER.index(s) if s in SCOPE_ORDER else 99,
    )
    return ", ".join(scopes) if scopes else "—"


def summaries_to_dataframe(summaries: list[dict]) -> pd.DataFrame:
    rows = []
    for summary in summaries:
        carbon = summary.get("carbon_data") or {}
        details = carbon.get("details") or []
        rows.append(
            {
                "Fournisseur": summary.get("supplier") or "—",
                "Date facture": summary.get("invoice_date") or "—",
                "Statut": summary.get("status") or "—",
                "À vérifier": "⚠️ Oui" if summary.get("a_verifier") else "Non",
                "CO2eq total (kg)": carbon.get("emissions_totales_kgco2e"),
                "Scopes couverts": scopes_covered(details),
                "Rapport": summary.get("report_path") or "—",
                "Rapport PDF": summary.get("report_path_pdf") or "—",
            }
        )
    return pd.DataFrame(rows)


def render_carbon_table(details: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Champ": d.get("champ"),
                "Scope": d.get("scope") or "—",
                "Quantité": d.get("quantite"),
                "Facteur (kgCO2e/unité)": d.get("facteur_kgco2e_par_unite"),
                "Émissions (kgCO2e)": d.get("emissions_kgco2e"),
                "Source": (d.get("source") or {}).get("nom") or (d.get("source") or {}).get("origine"),
            }
            for d in details
        ]
    )


def page_upload() -> None:
    st.header("Traiter une nouvelle facture")
    st.caption(f"Appelle l'API FastAPI sur {API_URL}/extract/")

    uploaded_file = st.file_uploader("Facture PDF", type=["pdf"])

    if uploaded_file and st.button("Analyser la facture", type="primary"):
        with st.spinner("Extraction GPT-4o Vision, calcul carbone, indexation et génération du rapport…"):
            try:
                response = requests.post(
                    f"{API_URL}/extract/",
                    files={"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")},
                    timeout=180,
                )
                response.raise_for_status()
                result = response.json()
            except requests.exceptions.ConnectionError:
                st.error(
                    f"Impossible de joindre l'API FastAPI sur {API_URL}. "
                    f"Vérifie qu'elle tourne (uvicorn app.main:app)."
                )
                return
            except requests.exceptions.RequestException as exc:
                st.error(f"Erreur lors de l'appel à l'API : {exc}")
                return

        status = result.get("status")

        if status == "erreur_extraction":
            st.error(f"Extraction impossible : {result.get('error')}")
            return

        if status == "erreur_calcul":
            st.warning(
                f"Calcul carbone impossible : {result.get('error')} "
                f"(la facture a tout de même été indexée dans le RAG)"
            )

        if result.get("a_verifier"):
            st.warning(f"⚠️ À vérifier : {result.get('raison_verification')}")

        invoice = result.get("invoice") or {}
        st.subheader("Données extraites")
        col1, col2, col3 = st.columns(3)
        col1.metric("Fournisseur", invoice.get("supplier") or "—")
        col2.metric("Date facture", invoice.get("invoice_date") or "—")
        amount = invoice.get("amount_total")
        col3.metric("Montant total", f"{amount} €" if amount is not None else "—")

        carbon = result.get("carbon") or {}
        details = carbon.get("details") or []

        if details:
            st.subheader("Émissions CO2e par poste")
            st.dataframe(render_carbon_table(details), use_container_width=True)
            st.metric("Total CO2eq", f"{carbon.get('emissions_totales_kgco2e', 0)} kg")
        else:
            st.info("Aucune donnée de consommation exploitable pour le calcul carbone.")

        report_path = result.get("report_path")
        if report_path:
            st.subheader("Rapport CSRD")
            st.caption(f"Sauvegardé dans : `{report_path}`")
            report_text = result.get("report")
            if report_text:
                with st.expander("Voir le rapport complet"):
                    st.markdown(report_text)

            report_path_pdf = result.get("report_path_pdf")
            if report_path_pdf and Path(report_path_pdf).exists():
                st.download_button(
                    "Télécharger le rapport PDF",
                    data=Path(report_path_pdf).read_bytes(),
                    file_name=Path(report_path_pdf).name,
                    mime="application/pdf",
                )

        with st.expander("Log de transitions du graphe"):
            st.dataframe(pd.DataFrame(result.get("log") or []), use_container_width=True)


def page_suivi() -> None:
    st.header("Suivi des extractions")

    summaries = load_summaries()
    if not summaries:
        st.info("Aucune facture traitée pour l'instant (rien dans backend/data/reports/).")
        return

    st.dataframe(summaries_to_dataframe(summaries), use_container_width=True)


def page_scopes() -> None:
    st.header("Indicateurs CO2 par scope (GHG Protocol)")

    summaries = load_summaries()
    if not summaries:
        st.info("Aucune facture traitée pour l'instant.")
        return

    totals = {scope: 0.0 for scope in SCOPE_ORDER}
    for summary in summaries:
        for detail in (summary.get("carbon_data") or {}).get("details") or []:
            scope = detail.get("scope")
            emissions = detail.get("emissions_kgco2e")
            if scope in totals and emissions is not None:
                totals[scope] += emissions

    df_scope = pd.DataFrame({"Scope": SCOPE_ORDER, "CO2eq (kg)": [totals[s] for s in SCOPE_ORDER]})

    chart = (
        alt.Chart(df_scope)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, size=60)
        .encode(
            x=alt.X("Scope:N", sort=SCOPE_ORDER, title=None),
            y=alt.Y("CO2eq (kg):Q", title="CO2eq (kg)"),
            color=alt.Color(
                "Scope:N",
                scale=alt.Scale(domain=SCOPE_ORDER, range=[SCOPE_COLORS[s] for s in SCOPE_ORDER]),
                legend=alt.Legend(title="Scope"),
            ),
            tooltip=[alt.Tooltip("Scope:N"), alt.Tooltip("CO2eq (kg):Q", format=".2f")],
        )
        .properties(height=380)
    )
    st.altair_chart(chart, use_container_width=True)
    st.dataframe(df_scope, use_container_width=True)


def page_evolution() -> None:
    st.header("Évolution temporelle des émissions CO2e")

    summaries = load_summaries()

    rows = []
    for summary in summaries:
        date = parse_invoice_date(summary.get("invoice_date"))
        total = (summary.get("carbon_data") or {}).get("emissions_totales_kgco2e")
        if date is not None and total is not None:
            rows.append(
                {
                    "Date facture": date,
                    "CO2eq (kg)": total,
                    "Fournisseur": summary.get("supplier") or "—",
                }
            )

    if not rows:
        st.info("Pas assez de factures avec date + CO2eq calculé pour tracer une évolution.")
        return

    df_time = pd.DataFrame(rows).sort_values("Date facture")

    chart = (
        alt.Chart(df_time)
        .mark_line(point=alt.OverlayMarkDef(size=60), color=SCOPE_COLORS["scope 2"])
        .encode(
            x=alt.X("Date facture:T", title="Date de facture"),
            y=alt.Y("CO2eq (kg):Q", title="CO2eq (kg)"),
            tooltip=[
                alt.Tooltip("Date facture:T"),
                alt.Tooltip("CO2eq (kg):Q", format=".2f"),
                alt.Tooltip("Fournisseur:N"),
            ],
        )
        .properties(height=380)
    )
    st.altair_chart(chart, use_container_width=True)
    st.dataframe(df_time, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="EDEN — Suivi carbone", layout="wide")

    st.sidebar.title("EDEN")
    st.sidebar.caption("Agent CSRD et décarbonation")

    page = st.sidebar.radio(
        "Navigation",
        ["Upload", "Suivi des extractions", "Indicateurs CO2 par scope", "Évolution temporelle"],
    )

    pages = {
        "Upload": page_upload,
        "Suivi des extractions": page_suivi,
        "Indicateurs CO2 par scope": page_scopes,
        "Évolution temporelle": page_evolution,
    }
    pages[page]()


if __name__ == "__main__":
    main()
