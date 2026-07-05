import re
from typing import List

def parse_invoice_text(ocr_text: str) -> dict:
    """
    Transforme le texte OCR d'une facture en JSON EDEN.
    Version MVP : extraction simple avec règles de base.
    """

    return {
        "supplier": extract_supplier(ocr_text),
        "invoice_number": extract_invoice_number(ocr_text),
        "invoice_date": extract_invoice_date(ocr_text),
        "contract_number": extract_contract_number(ocr_text),
        "customer_name": extract_customer_name(ocr_text),
        "energy_type": extract_energy_type(ocr_text),
        "period_start": extract_period_start(ocr_text),
        "period_end": extract_period_end(ocr_text),
        "consumption_kwh": extract_consumption_kwh(ocr_text),
        "amount_ht": extract_amount_ht(ocr_text),
        "amount_ttc": extract_amount_ttc(ocr_text),
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
    patterns = [
        r"FACTURE.*?DU\s+(\d{1,2}\s+[A-ZÉÛ]+\s+\d{4})",
        r"Facture.*?(\d{2}/\d{2}/\d{4})",
    ]

    return find_first_match(text, patterns)

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
    Ignore la Consommation Annuelle de Référence.
    """

    patterns = [
        # Tableau de consommation
        r"Base\s+\d+\s+\d+\s+\d+\s+(\d+)\s+0[,\.]\d+",

        # Ligne "Conso (KWh)"
        r"Conso\s*\(KWh\).*?(\d+)",

        # Fallback : dernier kWh rencontré
        r"(\d+)\s*kWh",
    ]

    matches = []

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)

        if matches:
            if pattern == r"(\d+)\s*kWh":
                return to_float(matches[-1])  # dernier kWh
            return to_float(matches[0])

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