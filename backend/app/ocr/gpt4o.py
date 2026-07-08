import base64
import json
import re
from datetime import datetime
from io import BytesIO

from openai import OpenAI
from pdf2image import convert_from_path

from app.utils.config import OPENAI_API_KEY

DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y")

client = OpenAI(api_key=OPENAI_API_KEY)

MODEL = "gpt-4o"

PROMPT = """
Tu es un assistant spécialisé dans l'analyse de factures d'énergie pour un
projet de décarbonation (CSRD).

Analyse TOUTES les pages de cette facture et retourne UNIQUEMENT un JSON
valide, sans texte autour, sans balises markdown.

Extrais les champs suivants :
- electricity_kwh : consommation totale d'électricité facturée, en kWh
- gas_m3 : consommation totale de gaz facturée, en m3
- waste_tons : quantité de déchets, en tonnes
- logistics_km : distance logistique, en km
- invoice_number : numéro de facture
- invoice_date : date d'émission de la facture, au format JJ/MM/AAAA
- billing_period : période de facturation, au format "JJ/MM/AAAA — JJ/MM/AAAA"
- supplier : nom du fournisseur
- amount_total : montant total TTC à payer, en euros (nombre)
- a_verifier : booléen, false par défaut (voir règle spécifique ci-dessous)
- raison_verification : voir règle spécifique ci-dessous, sinon null

Si une information n'est pas présente, retourne null pour ce champ.

Points d'attention IMPORTANTS (erreurs fréquentes à éviter) :

- invoice_date : c'est la date d'ÉMISSION de la facture (souvent juste à
  côté du numéro de facture, libellée "Date Facture"). Ce n'est JAMAIS :
  une date de prélèvement bancaire, une date limite de paiement, ou une
  date citée dans une mention légale/réglementaire (ex: "Arrêté du...",
  "Loi n°...", "Décret du..."). Convertis toujours au format JJ/MM/AAAA,
  même si la facture affiche un mois en toutes lettres
  (ex: "16 août 2024" -> "16/08/2024").

  invoice_date et billing_period sont deux informations INDÉPENDANTES :
  la date d'émission n'est ni le début ni la fin de la période couverte.
  Cherche toujours invoice_date séparément, même quand billing_period est
  déjà trouvé — ne le déduis jamais de billing_period. Si aucune date
  d'émission distincte n'est présente sur le document, laisse invoice_date
  à null plutôt que de recopier une borne de billing_period (un mécanisme
  côté application gère cette approximation si besoin).

- electricity_kwh / gas_m3 : c'est la consommation RÉELLE TOTALE facturée
  sur la période, pas une valeur intermédiaire. Ignore en particulier :
  - les lignes de calcul de taxe (TICFE, TCCFE, CTA, accises) qui
    décomposent la consommation en tranches partielles pour appliquer un
    taux différent à chacune — une tranche isolée n'est PAS le total ;
  - les lignes de détail tarifaire par période/index (HP/HC, Base, etc.)
    qui ne couvrent qu'une partie de la consommation si plusieurs lignes
    de ce type existent sur la facture ;
  - une valeur de consommation elle-même explicitement qualifiée, dans
    son contexte immédiat (juste avant/après le nombre), par les mots
    "référence" (ex: "Consommation Annuelle de Référence"), "prévisionnel(le)"
    ou "estimé(e)" — ce sont des projections sur 12 mois glissants, pas la
    consommation réellement facturée sur cette période.
  Cherche en priorité un total explicite (ex: "Terme d'énergie",
  "Total consommation", un récapitulatif en tête de facture).

  Attention : ces deux règles d'exclusion s'appliquent UNIQUEMENT à
  electricity_kwh et gas_m3, et uniquement quand la valeur de consommation
  ELLE-MÊME porte la qualification "référence"/"prévisionnel"/"estimé"
  dans son contexte immédiat — jamais par association avec un autre champ.
  En particulier, sur une facture de mensualisation/acompte où le montant
  (amount_total) est qualifié d'"estimé" ou de "prévisionnel" : renvoie
  quand même amount_total normalement (c'est une information à part
  entière, toujours à extraire), et n'écarte electricity_kwh/gas_m3 QUE
  si ce champ précis porte lui-même l'une de ces qualifications.

- a_verifier / raison_verification : si electricity_kwh OU gas_m3 vaut
  null UNIQUEMENT parce que la seule valeur trouvée sur la facture était
  qualifiée de référence/prévisionnelle/estimée (donc écartée par la règle
  ci-dessus), mets "a_verifier" à true et explique en une phrase dans
  "raison_verification" pourquoi aucune consommation réelle n'a été
  retenue (ex: "Facture de mensualisation, seule une consommation annuelle
  de référence est mentionnée, pas de consommation réelle"). Dans tous les
  autres cas (valeur trouvée normalement, ou champ réellement absent de la
  facture sans mention de ce type), laisse "a_verifier" à false et
  "raison_verification" à null.

Format de réponse attendu :

{
  "electricity_kwh": null,
  "gas_m3": null,
  "waste_tons": null,
  "logistics_km": null,
  "invoice_number": null,
  "invoice_date": null,
  "billing_period": null,
  "supplier": null,
  "amount_total": null,
  "a_verifier": false,
  "raison_verification": null
}
"""


def _pdf_to_base64_images(file_path: str) -> list[str]:
    # dpi=200 (défaut de pdf2image) rendait certains petits chiffres ambigus
    # pour le modèle (cf. instabilité observée sur facture_02) ; 300 donne
    # une image plus nette pour les factures à texte dense.
    pages = convert_from_path(file_path, dpi=300)

    images_base64 = []
    for page in pages:
        buffer = BytesIO()
        page.save(buffer, format="PNG")
        images_base64.append(base64.b64encode(buffer.getvalue()).decode("utf-8"))

    return images_base64


def _parse_json_response(content: str) -> dict:
    """Retire les éventuelles balises markdown ```json ... ``` autour du JSON."""
    cleaned = content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def _parse_period_end_date(billing_period: str) -> str | None:
    """Extrait la date de fin d'une période "JJ/MM/AAAA <séparateur> JJ/MM/AAAA"."""
    if not billing_period:
        return None

    parts = re.split(r"\s*(?:—|–|-|au)\s*", billing_period.strip())
    candidate = parts[-1].strip() if parts else ""

    for fmt in DATE_FORMATS:
        try:
            datetime.strptime(candidate, fmt)
            return candidate
        except ValueError:
            continue

    return None


def _apply_invoice_date_fallback(invoice_data: dict) -> dict:
    """
    Certaines factures (notamment des factures de mensualisation ou des
    documents de test) n'affichent aucune date d'émission distincte, mais
    seulement une période de facturation. Dans ce cas, on approxime
    invoice_date par la fin de billing_period, et on le signale via le
    même mécanisme que pour les consommations de référence/prévisionnelles
    (a_verifier / raison_verification), pour que ce ne soit jamais confondu
    avec une vraie date d'émission trouvée sur le document.
    """

    if invoice_data.get("invoice_date"):
        return invoice_data

    fallback_date = _parse_period_end_date(invoice_data.get("billing_period") or "")
    if not fallback_date:
        return invoice_data

    invoice_data["invoice_date"] = fallback_date

    note = (
        f"Date de facture absente du document ; approximée par la fin de "
        f"la période de facturation ({fallback_date})."
    )

    if invoice_data.get("a_verifier"):
        existing = invoice_data.get("raison_verification") or ""
        invoice_data["raison_verification"] = f"{existing} {note}".strip()
    else:
        invoice_data["a_verifier"] = True
        invoice_data["raison_verification"] = note

    return invoice_data


def _call_gpt4o_vision(file_path: str):
    """Appelle GPT-4o Vision sur toutes les pages du PDF et renvoie la réponse brute."""
    images_base64 = _pdf_to_base64_images(file_path)

    content = [{"type": "text", "text": PROMPT}]
    for image_base64 in images_base64:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_base64}"},
            }
        )

    return client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": content}],
        temperature=0,
    )


def extract_invoice_data_with_gpt4o(file_path: str) -> dict:
    """
    Extrait les données d'une facture via GPT-4o Vision, directement au
    format JSON harmonisé : electricity_kwh, gas_m3, waste_tons,
    logistics_km, invoice_number, invoice_date, billing_period, supplier,
    amount_total, a_verifier, raison_verification.

    Ce schéma est un sous-ensemble de celui de
    app.ocr.parser.parse_invoice_text, qui conserve en plus des champs
    legacy (customer_name, contract_number, energy_type, consumption_kwh,
    amount_ht, amount_ttc, period_start, period_end, ocr_text) absents ici.
    """

    response = _call_gpt4o_vision(file_path)
    invoice_data = _parse_json_response(response.choices[0].message.content)

    # Valeurs par défaut si le modèle omet ces champs (ne devrait pas
    # arriver vu le prompt, mais évite un KeyError en aval sinon).
    invoice_data.setdefault("a_verifier", False)
    invoice_data.setdefault("raison_verification", None)

    invoice_data = _apply_invoice_date_fallback(invoice_data)

    return invoice_data
