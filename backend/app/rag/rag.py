import uuid

from app.rag.chroma import ChromaManager
from app.rag.chunking import split_documents
from app.rag.ingestion import build_document, CONSUMPTION_FIELDS
from app.rag.loaders import load_pdf


INVOICE_COLLECTION = "energy-invoices"
KNOWLEDGE_COLLECTION = "reglementation"
FACTORS_COLLECTION = "facteurs_emission"

# Chroma Cloud refuse les ajouts au-dela d'un certain nombre
# d'enregistrements par requete (quota du plan) : on decoupe donc tout
# ajout en lots.
ADD_BATCH_SIZE = 200


def index_invoice(invoice_data: dict) -> dict:
    """
    Indexe une facture dans Chroma Cloud.
    """

    document_data = build_document(invoice_data)

    chroma = ChromaManager()

    return chroma.add_document(
        collection_name=INVOICE_COLLECTION,
        document_data=document_data,
    )





def ingest_knowledge(pdf_path: str, document_name: str) -> dict:
    """
    Charge un document réglementaire, le découpe en chunks
    et l'indexe dans Chroma Cloud.
    """

    documents = load_pdf(pdf_path)
    chunks = split_documents(documents)

    ids = []
    texts = []
    metadatas = []

    for chunk in chunks:
        ids.append(str(uuid.uuid4()))
        texts.append(chunk.page_content)

        metadata = chunk.metadata.copy()
        metadata["document"] = document_name

        metadatas.append(metadata)

    chroma = ChromaManager()

    total = len(ids)
    last_result = {"status": "success", "chunks": 0, "collection": KNOWLEDGE_COLLECTION}

    for start in range(0, total, ADD_BATCH_SIZE):
        end = min(start + ADD_BATCH_SIZE, total)
        last_result = chroma.add_chunks(
            collection_name=KNOWLEDGE_COLLECTION,
            ids=ids[start:end],
            documents=texts[start:end],
            metadatas=metadatas[start:end],
        )

    return {**last_result, "chunks": total}


def search_knowledge(query: str, n_results: int = 3) -> dict:
    """
    Recherche dans la base documentaire.
    """

    chroma = ChromaManager()

    return chroma.search_documents(
        collection_name=KNOWLEDGE_COLLECTION,
        query=query,
        n_results=n_results,
    )

def retrieve_context(invoice_data: dict) -> str:
    """
    Recherche automatiquement les passages les plus pertinents
    dans la base documentaire, à partir du schéma harmonisé produit par
    l'extraction (electricity_kwh, gas_m3, waste_tons, logistics_km).
    """

    chroma = ChromaManager()

    consumption_field = next(
        (field for field in CONSUMPTION_FIELDS if invoice_data.get(field) is not None),
        None,
    )

    if consumption_field:
        quantity = invoice_data[consumption_field]
        unit = CONSUMPTION_FIELDS[consumption_field]
        consumption_lines = (
            f"Type de consommation: {consumption_field}\n"
            f"Quantité: {quantity} {unit}"
        )
    else:
        consumption_lines = "Type de consommation: inconnue"

    query = f"""
    Fournisseur: {invoice_data.get("supplier", "")}
    {consumption_lines}
    """

    results = chroma.search_documents(
        collection_name=KNOWLEDGE_COLLECTION,
        query=query,
        n_results=3,
    )

    context = ""

    if results["documents"]:
        for document in results["documents"][0]:
            context += document + "\n\n"

    return context