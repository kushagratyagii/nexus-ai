
from pathlib import Path
from app.core.config import OPENAI_API_KEY

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from app.rag.ingestion import FAISS_DIR

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=OPENAI_API_KEY
)
def get_vector_store():

    if not (FAISS_DIR / "index.faiss").exists():
        raise FileNotFoundError(
            "FAISS index not found. Upload a PDF first."
        )

    return FAISS.load_local(
        str(FAISS_DIR),
        embeddings,
        allow_dangerous_deserialization=True
    )


def retrieve_documents(query: str, k: int = 4):

    vector_store = get_vector_store()

    results = vector_store.similarity_search(
        query,
        k=k
    )

    return results


def get_relevant_context(query: str, k: int = 4):

    documents = retrieve_documents(query, k)

    context = "\n\n".join(
        f"""
        Source: {doc.metadata.get('source', 'Unknown')}
        Page: {doc.metadata.get('page', 'Unknown')}

        Content:
        {doc.page_content}
        """
        for doc in documents
    )

    return context
