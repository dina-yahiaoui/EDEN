# LEGACY : ce module n'est plus utilisé par défaut depuis la semaine 2.
# app/ocr/gpt4o.py (GPT-4o Vision) est le moteur d'extraction actif,
# branché sur POST /extract/ dans api/extract.py. Conservé ici pour
# référence et comme repli local/gratuit potentiel, pas maintenu au même
# niveau : plusieurs bugs d'extraction identifiés (voir
# docs/specifications_mvp.md, section "limites connues") ne sont corrigés
# que partiellement, pour un seul fournisseur.

import re
from typing import List

def parse_invoice_text(ocr_text: str) -> dict:
    """
    Transforme le texte OCR d'une facture en JSON EDEN.
    Version MVP : extraction simple avec règles de base.
    """

    energy_type = extract_energy_type(ocr_text)
    period_start = extract_period_start(ocr_text)
    period_end = extract_period_end(ocr_text)
    consumption_kwh = extract_consumption_kwh(ocr_text)
    amount_ht = extract_amount_ht(ocr_text)
    amount_ttc = extract_amount_ttc(ocr_text)

    return {
        # Schéma harmonisé avec carbon.py, data/processed/*.json et les
        # prompts GPT-4o/Mistral (electricity_kwh / gas_m3 / waste_tons /
        # logistics_km). Le parser Tesseract ne distingue qu'électricité/gaz
        # et n'a pas d'extracteur dédié aux m3 : la valeur "kWh" détectée est
        # donc rangée sous le champ correspondant à l'énergie détectée.
        "electricity_kwh": consumption_kwh if energy_type == "electricity" else None,
        "gas_m3": consumption_kwh if energy_type == "gas" else None,
        "waste_tons": None,
        "logistics_km": None,
        "invoice_number": extract_invoice_number(ocr_text),
        "invoice_date": extract_invoice_date(ocr_text),
        "billing_period": f"{period_start} — {period_end}" if period_start or period_end else "",
        "supplier": extract_supplier(ocr_text),
        "amount_total": amount_ttc or amount_ht,

        # Champs conservés pour ne pas casser rag/ingestion.py (build_document
        # lit precisement ces cles) : ne pas les retirer sans mettre a jour
        # l'indexation RAG des factures.
        "contract_number": extract_contract_number(ocr_text),
        "customer_name": extract_customer_name(ocr_text),
        "energy_type": energy_type,
        "period_start": period_start,
        "period_end": period_end,
        "consumption_kwh": consumption_kwh,
        "amount_ht": amount_ht,
        "amount_ttc": amount_ttc,
        "ocr_text": ocr_text,
    }


def extract_supplier(text: str) -> str:
    text_lower = text.lower()

    if "totalenergies" in text_lower:
        return "TotalEnergies"
    if "iberdrola" in text_lower:
        return "Iberdrola"
    if "edf" in text_lower:
        return "EDF"
    if "engie" in text_lower:
        return "Engie"

    return ""


def extract_energy_type(text: str) -> str:
    text_lower = text.lower()

    if "électricité" in text_lower or "electricite" in text_lower:
        return "electricity"

    if "gaz" in text_lower:
        return "gas"

    return ""


def extract_invoice_number(text: str) -> str:
    patterns = [
        r"N[°º]\s*(?:de\s*)?Facture\s*[:\-]?\s*([A-Z0-9]+)",
        r"Facture\s*n[°º]\s*([A-Z0-9]+)",
        r"N[°º]\s*([A-Z0-9]{8,})",
    ]

    return find_first_match(text, patterns)


def extract_invoice_date(text: str) -> str:
    """
    Extrait la date d'émission de la facture.

    Priorité aux libellés explicites ("Date Facture JJ/MM/AAAA"), qui
    apparaissent en en-tête. Le pattern générique "FACTURE...DU <date>"
    est gardé en dernier recours mais exclut les dates suivies d'une
    référence légale (Arrêté, Loi, Décret), qui matchent sinon des mentions
    réglementaires en pied de facture au lieu de la date réelle.
    """

    patterns = [
        r"Date\s+Facture\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})",
        r"Facture\s+(?:émise\s+)?du\s+(\d{2}/\d{2}/\d{4})",
        r"FACTURE.*?DU\s+(\d{1,2}\s+[A-ZÉÛ]+\s+\d{4})",
        r"Facture.*?(\d{2}/\d{2}/\d{4})",
    ]

    exclude_keywords = ("arrêté", "arrete", "loi", "décret", "decret", "règlement", "reglement")

    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL | re.MULTILINE):
            context = text[max(0, match.start() - 40):match.end() + 20].lower()
            if any(keyword in context for keyword in exclude_keywords):
                continue
            return match.group(1).strip()

    return ""

def extract_contract_number(text: str) -> str:
    patterns = [
        r"Référence du Contrat\s*[:\-]?\s*([0-9]+)",
        r"Référence client\s*[:\-]?\s*([0-9]+)",
    ]

    return find_first_match(text, patterns)


def extract_customer_name(text: str) -> str:
    """
    Extrait le nom du client.
    """

    patterns = [
        r"Nom du client\s*:\s*M\.?\s*([^\n\r]+)",
        r"Titulaire du compte\s*:\s*([^\n\r]+)",
        r"Titulaire\s*:\s*([^\n\r]+)",
    ]

    name = find_first_match(text, patterns)

    # Nettoyage
    name = re.sub(r"Lieu de consommation.*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name)

    return name.strip()

def extract_period_start(text: str) -> str:
    patterns = [
        r"Période du\s*(\d{2}/\d{2}/\d{2})\s*au\s*(\d{2}/\d{2}/\d{2})",
        r"(\d{2}/\d{2}/\d{4})\s*[-–]\s*(\d{2}/\d{2}/\d{4})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return match.group(1)

    return ""


def extract_period_end(text: str) -> str:
    patterns = [
        r"Période du\s*(\d{2}/\d{2}/\d{2})\s*au\s*(\d{2}/\d{2}/\d{2})",
        r"(\d{2}/\d{2}/\d{4})\s*[-–]\s*(\d{2}/\d{2}/\d{4})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return match.group(2)

    return ""


def extract_consumption_kwh(text: str) -> float:
    """
    Extrait la consommation facturée en kWh.
    Ignore la Consommation Annuelle de Référence et les lignes de calcul
    de taxe (TICFE/TCCFE/CTA), qui affichent aussi des valeurs en kWh mais
    correspondent à des tranches fiscales, pas à la consommation réelle.
    """

    patterns = [
        # Tableau de consommation
        r"Base\s+\d+\s+\d+\s+\d+\s+(\d+)\s+0[,\.]\d+",

        # Ligne "Conso (KWh)"
        r"Conso\s*\(KWh\).*?(\d+)",

        # Ligne "Terme d'énergie" (consommation facturée)
        r"Terme.{0,3}nergie\s+(\d+(?:[,.]\d+)?)\s*kWh",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
        if matches:
            return to_float(matches[0])

    # Fallback : première occurrence de "<nombre> kWh" qui n'apparaît pas
    # dans une ligne de calcul de taxe (celles-ci ne portent qu'une fraction
    # de la consommation réelle, pas le total facturé).
    exclude_keywords = ("taxe", "ticfe", "tccfe", "contribution", "accise", "cta")

    for match in re.finditer(r"(\d+(?:[,.]\d+)?)\s*kWh", text, re.IGNORECASE):
        context = text[max(0, match.start() - 80):match.start()].lower()
        if any(keyword in context for keyword in exclude_keywords):
            continue
        return to_float(match.group(1))

    return 0.0

def extract_amount_ht(text: str) -> float:
    patterns = [
        r"Total hors TVA\s*([0-9]+[,.][0-9]+)",
        r"TOTAL HT\s*([0-9]+[,.][0-9]+)",
    ]

    value = find_first_match(text, patterns)

    return to_float(value)


def extract_amount_ttc(text: str) -> float:
    patterns = [
        r"MONTANT TOTAL TTC\s*([0-9]+[,.][0-9]+)",
        r"TOTAL TTC\s*([0-9]+[,.][0-9]+)",
        r"Montant\s*:\s*([0-9]+[,.][0-9]+)",
    ]

    value = find_first_match(text, patterns)

    return to_float(value)


def find_first_match(text: str, patterns: List[str]) -> str:
    """
    Retourne la première correspondance trouvée parmi une liste de regex.
    """

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE | re.DOTALL | re.MULTILINE
        )

        if match:
            if len(match.groups()) == 1:
                return match.group(1).strip()

            return " ".join(match.groups()).strip()

    return ""


def to_float(value: str) -> float:
    if not value:
        return 0.0

    value = value.replace(",", ".").replace(" ", "")

    try:
        return float(value)
    except ValueError:
        return 0.0