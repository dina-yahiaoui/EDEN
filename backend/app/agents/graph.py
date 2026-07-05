from app.rag.rag import retrieve_context
from app.services.carbon import calculate_carbon_emissions
from app.services.report import generate_csrd_report


def run_eden(invoice_data: dict):
    """
    Pipeline principal de l'agent EDEN.
    """

    # 1. Récupération du contexte réglementaire
    context = retrieve_context(invoice_data)

    # 2. Calcul des émissions CO2
    carbon_data = calculate_carbon_emissions(invoice_data)

    # 3. Génération du rapport
    report = generate_csrd_report(
        invoice_data=invoice_data,
        carbon_data=carbon_data,
        context=context,
    )

    return {
        "invoice": invoice_data,
        "carbon": carbon_data,
        "report": report,
    }