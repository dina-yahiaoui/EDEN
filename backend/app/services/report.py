import re
from pathlib import Path
from xml.sax.saxutils import escape

from openai import OpenAI
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.utils.config import OPENAI_API_KEY


client = OpenAI(api_key=OPENAI_API_KEY)


def _fr_number(value: float) -> str:
    """Formate un nombre en notation française (virgule), sans zéros superflus."""
    return f"{value:g}".replace(".", ",")


def _format_kwh_with_mwh(value_kwh: float) -> str:
    """Ex: 215 -> '215 kWh (0,215 MWh)'. 1000 kWh = 1 MWh."""
    mwh = round(value_kwh / 1000, 3)
    return f"{_fr_number(value_kwh)} kWh ({_fr_number(mwh)} MWh)"


def _format_energy_lines(invoice_data: dict) -> str:
    """
    Prépare les lignes de consommation d'énergie avec équivalent MWh, à
    reprendre telles quelles dans le rapport (calcul fait ici, pas par le
    modèle, pour éviter toute erreur d'arithmétique dans le texte généré).

    gas_m3 n'a pas d'équivalent MWh ici : la conversion m3 -> kWh dépend du
    pouvoir calorifique du gaz, une donnée que l'extraction ne fournit pas
    (contrairement à electricity_kwh, déjà en kWh). Affiché en m3 seul.
    """

    lines = []

    electricity_kwh = invoice_data.get("electricity_kwh")
    if electricity_kwh is not None:
        lines.append(f"- Électricité : {_format_kwh_with_mwh(electricity_kwh)}")

    gas_m3 = invoice_data.get("gas_m3")
    if gas_m3 is not None:
        lines.append(f"- Gaz : {_fr_number(gas_m3)} m³ (pas d'équivalent MWh sans pouvoir calorifique)")

    return "\n".join(lines) if lines else "Aucune consommation d'énergie (électricité/gaz) sur cette facture."


def generate_csrd_report(
    invoice_data: dict,
    carbon_data: dict,
    context: str,
) -> str:
    """
    Génère un rapport CSRD simplifié avec GPT-4o.
    """

    energy_lines = _format_energy_lines(invoice_data)

    prompt = f"""
Tu es EDEN, un agent de pilotage CSRD et décarbonation.

À partir des données suivantes, génère un compte rendu CSRD simplifié.

Données facture :
{invoice_data}

Consommations d'énergie avec équivalent MWh (valeurs déjà calculées, à
reprendre EXACTEMENT telles quelles partout où tu mentionnes ces
consommations dans le rapport, ne recalcule jamais toi-même la conversion) :
{energy_lines}

Calcul carbone :
{carbon_data}

Contexte réglementaire / RAG :
{context}

Le rapport doit contenir :
1. Résumé de la facture
2. Données extraites (pour l'électricité et le gaz, utilise le format
   "kWh (MWh)" / "m³" donné ci-dessus, pas seulement les kWh/m³ bruts)
3. Calcul des émissions CO2e, en précisant pour chaque poste son scope
   GHG Protocol (scope 1, 2 ou 3, donné dans le champ "scope" de chaque
   élément de "details")
4. Lien avec ESRS E1 / climat
5. Limites et données manquantes
6. Recommandations
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "Tu es un expert CSRD, ESRS E1 et bilan carbone."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content


def _inline_markdown_to_reportlab_xml(text: str) -> str:
    """Échappe le texte puis convertit **gras** au format <b> compris par
    reportlab.platypus.Paragraph (le seul balisage markdown utilisé par le
    rapport généré, voir le prompt de generate_csrd_report)."""

    escaped = escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)


def save_report_as_pdf(report_markdown: str, pdf_path: Path) -> None:
    """
    Convertit le rapport CSRD (texte Markdown léger généré par GPT-4o) en
    PDF, sans dépendance système (reportlab est pur Python côté
    installation, contrairement à weasyprint qui nécessite GTK/Pango/Cairo
    installés sur la machine).

    Conversion volontairement simple : une ligne "**...**" seule devient un
    titre, une ligne "- ..." devient une puce, le reste un paragraphe
    normal ; le gras inline (**mot**) est préservé. Suffisant pour la
    structure du rapport (titres numérotés + listes), pas un moteur
    Markdown complet.
    """

    styles = getSampleStyleSheet()
    normal_style = styles["Normal"]
    heading_style = ParagraphStyle(
        "EdenReportHeading",
        parent=styles["Heading3"],
        spaceBefore=10,
        spaceAfter=6,
    )

    story = []

    for raw_line in report_markdown.splitlines():
        line = raw_line.strip()

        if not line:
            story.append(Spacer(1, 0.2 * cm))
            continue

        heading_match = re.fullmatch(r"\*\*(.+)\*\*", line)
        if heading_match:
            story.append(Paragraph(_inline_markdown_to_reportlab_xml(heading_match.group(1)), heading_style))
            continue

        if line.startswith("- "):
            story.append(Paragraph(f"• {_inline_markdown_to_reportlab_xml(line[2:])}", normal_style))
            continue

        story.append(Paragraph(_inline_markdown_to_reportlab_xml(line), normal_style))

    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )
    doc.build(story)