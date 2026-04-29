"""
ChromaDB knowledge base — PDF ingestion and vector retrieval.

The LangChain chain that used to live here has been replaced by the
agentic loop in agent.py, which calls get_vector_store() directly.
"""

import os

from langchain_community.document_loaders import PyPDFLoader
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chromadb")
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL)


def get_vector_store() -> Chroma:
    return Chroma(persist_directory=CHROMA_DIR, embedding_function=_embeddings())


def index_pdf(pdf_path: str) -> int:
    """Chunk a PDF and upsert into ChromaDB. Returns number of chunks stored."""
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()
    chunks = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=100
    ).split_documents(docs)
    Chroma.from_documents(chunks, embedding=_embeddings(), persist_directory=CHROMA_DIR)
    return len(chunks)
