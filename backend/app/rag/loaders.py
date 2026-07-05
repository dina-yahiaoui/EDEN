from langchain_community.document_loaders import PyPDFLoader


def load_pdf(file_path: str):
    """
    Charge un document PDF avec LangChain.

    Returns:
        Liste de Documents LangChain.
    """

    loader = PyPDFLoader(file_path)

    documents = loader.load()

    return documents