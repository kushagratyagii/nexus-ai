
from langchain_core.tools import tool
from app.tools.approval import protected_action

@tool
def multiply(a: int, b: int) -> int:
    """Multiply two integers."""
    return a * b


@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


@tool
def search_knowledge_base(query: str) -> str:
    """
    Search uploaded PDF documents for relevant information.
    Use this tool when the user asks questions about uploaded documents,
    their contents, concepts, facts or explanations based on those files.
    """

    from app.rag.retrieval import retrieve_documents

    try:
        documents = retrieve_documents(query, k=4)

        if not documents:
            return "No relevant information found in uploaded documents."

        results = []

        for doc in documents:
            source = doc.metadata.get("source", "Unknown")
            page = doc.metadata.get("page", "Unknown")

            results.append(
                f"Source: {source}\n"
                f"Page: {page}\n"
                f"Content: {doc.page_content}"
            )

        return "\n\n---\n\n".join(results)

    except FileNotFoundError:
        return "No documents have been uploaded yet. Ask the user to upload a PDF."

    except Exception as e:
        print(f"RAG retrieval error: {e}")
        return "Knowledge base search failed."


tools = [
    multiply,
    add,
    search_knowledge_base,
    protected_action
]
