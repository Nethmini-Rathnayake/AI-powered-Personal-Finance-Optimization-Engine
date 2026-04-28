import os
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_anthropic import ChatAnthropic
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chromadb")
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

_PROMPT_TEMPLATE = ChatPromptTemplate.from_template(
    """You are a financial advisor specialising in debt management and consumer credit.

{debt_context}

Relevant bank terms and conditions:
{context}

Question: {question}

Give a clear, practical answer grounded in the provided context.
Flag any fees, penalties, or clauses the user should watch out for."""
)


def _embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL)


def index_pdf(pdf_path: str) -> int:
    """Chunk a PDF and upsert into ChromaDB. Returns the number of chunks stored."""
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = splitter.split_documents(docs)

    Chroma.from_documents(
        chunks,
        embedding=_embeddings(),
        persist_directory=CHROMA_DIR,
    )
    return len(chunks)


def _vector_store() -> Chroma:
    return Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=_embeddings(),
    )


def answer_question(question: str, debt_context: str = "") -> str:
    """
    RAG pipeline: retrieve relevant T&C clauses then answer with Claude.
    debt_context should be a plain-text summary of the user's debt situation.
    """
    llm = ChatAnthropic(
        model="claude-sonnet-4-6",
        api_key=os.environ["ANTHROPIC_API_KEY"],
    )

    retriever = _vector_store().as_retriever(search_kwargs={"k": 4})

    def format_docs(docs) -> str:
        return "\n\n".join(doc.page_content for doc in docs)

    debt_ctx_str = (
        f"User's current debt situation:\n{debt_context}" if debt_context else ""
    )

    chain = (
        {
            "context": retriever | format_docs,
            "question": RunnablePassthrough(),
            "debt_context": lambda _: debt_ctx_str,
        }
        | _PROMPT_TEMPLATE
        | llm
        | StrOutputParser()
    )

    return chain.invoke(question)
