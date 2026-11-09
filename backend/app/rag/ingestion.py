
from app.core.config import OPENAI_API_KEY
from pathlib import Path

from pypdf import PdfReader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

# Persistent FAISS storage
BASE_DIR = Path(__file__).resolve().parents[2]
FAISS_DIR = BASE_DIR / "storage" / "faiss_index"

# Embedding model
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=OPENAI_API_KEY
)
# Text splitter
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", " ", ""]
)


def ingest_pdf(file_path: str, display_name: str = None):

    pdf_path = Path(file_path)

    if not pdf_path.exists():
        raise FileNotFoundError("PDF file not found")

    # 1. Extract text page by page
    reader = PdfReader(str(pdf_path))

    documents = []

    for page_number, page in enumerate(reader.pages):

        text = page.extract_text()

        if text and text.strip():
            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": display_name or pdf_path.name,
                        "page": page_number + 1
                    }
                )
            )

    if not documents:
        raise ValueError(
            "No extractable text found in PDF. Scanned PDFs need OCR."
        )

    # 2. Split documents into chunks
    chunks = text_splitter.split_documents(documents)

    if not chunks:
        raise ValueError("No document chunks generated")

    # 3. Create or update FAISS index
    FAISS_DIR.mkdir(parents=True, exist_ok=True)

    if (FAISS_DIR / "index.faiss").exists():

        vector_store = FAISS.load_local(
            str(FAISS_DIR),
            embeddings,
            allow_dangerous_deserialization=True
        )

        vector_store.add_documents(chunks)

    else:

        vector_store = FAISS.from_documents(
            chunks,
            embeddings
        )

    # 4. Persist index
    vector_store.save_local(str(FAISS_DIR))

    return {
        "filename": pdf_path.name,
        "pages_processed": len(documents),
        "chunks_created": len(chunks),
        "status": "success"
    }
