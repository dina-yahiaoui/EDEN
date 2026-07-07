from openai import OpenAI

from app.utils.config import OPENAI_API_KEY


client = OpenAI(api_key=OPENAI_API_KEY)


def generate_csrd_report(
    invoice_data: dict,
    carbon_data: dict,
    context: str,
) -> str:
    """
    Génère un rapport CSRD simplifié avec GPT-4o.
    """

    prompt = f"""
Tu es EDEN, un agent de pilotage CSRD et décarbonation.

À partir des données suivantes, génère un compte rendu CSRD simplifié.

Données facture :
{invoice_data}

Calcul carbone :
{carbon_data}

Contexte réglementaire / RAG :
{context}

Le rapport doit contenir :
1. Résumé de la facture
2. Données extraites
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