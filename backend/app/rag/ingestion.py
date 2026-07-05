from uuid import uuid4


def build_document(invoice_data: dict) -> dict:
    """
    Construit un document enrichi à partir du JSON EDEN.

    Returns:
        dict contenant :
        - id
        - document
        - metadata
    """

    document = f"""
Energy invoice

Supplier: {invoice_data.get("supplier", "")}

Customer: {invoice_data.get("customer_name", "")}

Invoice number: {invoice_data.get("invoice_number", "")}

Invoice date: {invoice_data.get("invoice_date", "")}

Contract number: {invoice_data.get("contract_number", "")}

Energy type: {invoice_data.get("energy_type", "")}

Consumption: {invoice_data.get("consumption_kwh", "")} kWh

Amount HT: {invoice_data.get("amount_ht", "")} €

Amount TTC: {invoice_data.get("amount_ttc", "")} €

Billing period:
{invoice_data.get("period_start", "")}
to
{invoice_data.get("period_end", "")}

OCR text:

{invoice_data.get("ocr_text", "")}
""".strip()

    metadata = {
        "supplier": invoice_data.get("supplier", ""),
        "customer": invoice_data.get("customer_name", ""),
        "invoice_number": invoice_data.get("invoice_number", ""),
        "energy_type": invoice_data.get("energy_type", ""),
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