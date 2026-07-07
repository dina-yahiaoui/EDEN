from uuid import uuid4

# Champs de consommation du schéma harmonisé produit par l'extraction
# (gpt4o.py), avec leur unité d'affichage.
CONSUMPTION_FIELDS = {
    "electricity_kwh": "kWh",
    "gas_m3": "m3",
    "waste_tons": "tonnes",
    "logistics_km": "km",
}


def build_document(invoice_data: dict) -> dict:
    """
    Construit un document enrichi à partir du JSON structuré produit par
    l'extraction : electricity_kwh, gas_m3, waste_tons, logistics_km,
    invoice_number, invoice_date, billing_period, supplier, amount_total.

    Returns:
        dict contenant :
        - id
        - document
        - metadata
    """

    consumption_lines = [
        f"- {field}: {invoice_data[field]} {unit}"
        for field, unit in CONSUMPTION_FIELDS.items()
        if invoice_data.get(field) is not None
    ]
    consumption_block = "\n".join(consumption_lines) if consumption_lines else "(non renseignée)"

    document = (
        f"Energy invoice\n\n"
        f"Supplier: {invoice_data.get('supplier', '')}\n"
        f"Invoice number: {invoice_data.get('invoice_number', '')}\n"
        f"Invoice date: {invoice_data.get('invoice_date', '')}\n"
        f"Billing period: {invoice_data.get('billing_period', '')}\n"
        f"Amount total: {invoice_data.get('amount_total', '')} €\n\n"
        f"Consumption:\n{consumption_block}"
    ).strip()

    types_present = [field for field in CONSUMPTION_FIELDS if invoice_data.get(field) is not None]

    metadata = {
        "supplier": invoice_data.get("supplier", ""),
        "invoice_number": invoice_data.get("invoice_number", ""),
        "type": ", ".join(types_present),
    }

    document_id = (
        invoice_data.get("invoice_number")
        or str(uuid4())
    )

    return {
        "id": document_id,
        "document": document,
        "metadata": metadata,
    }