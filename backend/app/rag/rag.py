import uuid

from app.rag.chroma import ChromaManager
from app.rag.chunking import split_documents
from app.rag.ingestion import build_document
from app.rag.loaders import load_pdf


INVOICE_COLLECTION = "energy-invoices"
KNOWLEDGE_COLLECTION = "knowledge-base"


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

    return chroma.add_chunks(
        collection_name=KNOWLEDGE_COLLECTION,
        ids=ids,
        documents=texts,
        metadatas=metadatas,
    )


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
    dans la base documentaire.
    """

    chroma = ChromaManager()

    query = f"""
    Supplier: {invoice_data.get("supplier", "")}
    Energy: {invoice_data.get("energy_type", "")}
    Consumption: {invoice_data.get("consumption_kwh", "")} kWh
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