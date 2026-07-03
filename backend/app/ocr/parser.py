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
        r"Date\s*Facture\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})",
        r"FACTURE.*?DU\s*(\d{1,2})\s+([A-ZÉÛ]+)\s+(\d{4})",
    ]

    return find_first_match(text, patterns)


def extract_contract_number(text: str) -> str:
    patterns = [
        r"Référence du Contrat\s*[:\-]?\s*([0-9]+)",
        r"Référence client\s*[:\-]?\s*([0-9]+)",
    ]

    return find_first_match(text, patterns)


def extract_customer_name(text: str) -> str:
    patterns = [
        r"Nom du client\s*:\s*M\.?\s*([A-ZÉÈÀÙÂÊÎÔÛÄËÏÖÜÇ\s\-]+)",
        r"Titulaire\s*:\s*([A-ZÉÈÀÙÂÊÎÔÛÄËÏÖÜÇ\s\-]+)",
        r"Titulaire du compte\s*:\s*\n\s*([A-ZÉÈÀÙÂÊÎÔÛÄËÏÖÜÇ\s\-]+)",
    ]

    return find_first_match(text, patterns).strip()


def extract_period_start(text: str) -> str:
    pattern = r"(\d{2}/\d{2}/\d{4})\s*[—\-]\s*(\d{2}/\d{2}/\d{4})"
    match = re.search(pattern, text)

    if match:
        return match.group(1)

    return ""


def extract_period_end(text: str) -> str:
    pattern = r"(\d{2}/\d{2}/\d{4})\s*[—\-]\s*(\d{2}/\d{2}/\d{4})"
    match = re.search(pattern, text)

    if match:
        return match.group(2)

    return ""


def extract_consumption_kwh(text: str) -> float:
    patterns = [
        r"(\d+[,.]?\d*)\s*kWh",
        r"Conso\s*\(KWh\).*?(\d+[,.]?\d*)",
    ]

    value = find_first_match(text, patterns)

    return to_float(value)


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