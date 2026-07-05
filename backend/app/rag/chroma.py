import chromadb

from app.utils.config import (
    CHROMA_API_KEY,
    CHROMA_TENANT,
    CHROMA_DATABASE,
)


class ChromaManager:
    """
    Gère la connexion et les opérations sur Chroma Cloud.
    """

    def __init__(self):
        self.client = chromadb.CloudClient(
            api_key=CHROMA_API_KEY,
            tenant=CHROMA_TENANT,
            database=CHROMA_DATABASE,
        )

    def get_or_create_collection(self, collection_name: str):
        """
        Retourne une collection existante ou la crée.
        """
        return self.client.get_or_create_collection(
            name=collection_name
        )

    def add_document(
        self,
        collection_name: str,
        document_data: dict,
    ):
        """
        Ajoute un document dans une collection Chroma.
        """

        collection = self.get_or_create_collection(collection_name)

        collection.add(
            ids=[document_data["id"]],
            documents=[document_data["document"]],
            metadatas=[document_data["metadata"]],
        )

        return {
            "status": "success",
            "document_id": document_data["id"],
            "collection": collection_name,
        }
    def search_documents(
        self,
        collection_name: str,
        query: str,
        n_results: int = 3,
    ):
        """
        Recherche les documents les plus proches
        d'une question.
        """

        collection = self.get_or_create_collection(
            collection_name
        )

        results = collection.query(
            query_texts=[query],
            n_results=n_results,
        )

        return results
    
    def add_chunks(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
    ):
        """
        Ajoute plusieurs chunks dans une collection Chroma.
        """

        collection = self.get_or_create_collection(collection_name)

        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        return {
            "status": "success",
            "chunks": len(ids),
            "collection": collection_name,
        }