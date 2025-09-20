"""Knowledge base management for Vito's Pizza Cafe application."""

import os
import logging
from functools import lru_cache
from typing import List

import cohere
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from langchain_cohere import CohereEmbeddings
from langchain.text_splitter import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter
)
from langchain_core.messages import SystemMessage

from .config import Config

logger = logging.getLogger(__name__)

def load_documents(directory_path: str) -> List[str]:
    """Load documents from the specified directory."""
    docs = []
    for file in os.listdir(directory_path):
        if file.endswith(".md"):
            file_path = os.path.join(directory_path, file)
            loader = TextLoader(file_path, encoding="utf-8")
            loaded_docs = loader.load()
            docs.extend(loaded_docs)
    return docs

def chunk_documents(documents) -> List[str]:
    """Chunk documents into smaller chunks."""
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3")
    ]

    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        return_each_line=False,
        strip_headers=False
    )

    structured_docs = []
    for doc in documents:
        splits = markdown_splitter.split_text(doc.page_content)
        structured_docs.extend(splits)

    # Secondary chunking (for long paragraphs)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=Config.CHUNK_SIZE,
        chunk_overlap=Config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = text_splitter.split_documents(structured_docs)
    logger.info(f"Total chunks after chunking: {len(chunks)}")
    return chunks

@lru_cache(maxsize=1)
def setup_knowledge_base(directory_path: str = None) -> FAISS:
    """Process markdown documents and create a vector store."""
    if directory_path is None:
        directory_path = Config.KNOWLEDGE_BASE_PATH

    index_file_path = os.path.join(directory_path, "faiss_index")
    embeddings = CohereEmbeddings(
        model=Config.EMBEDDING_MODEL,
        cohere_api_key=Config.COHERE_API_KEY
    )

    if os.path.exists(index_file_path):
        logger.info("Loading existing index...")
        vector_store = FAISS.load_local(
            index_file_path,
            embeddings,
            allow_dangerous_deserialization=True
        )
    else:
        logger.info("Creating new vector store...")
        docs = load_documents(directory_path)
        chunked_docs = chunk_documents(docs)
        vector_store = FAISS.from_documents(chunked_docs, embeddings)
        vector_store.save_local(index_file_path)
        logger.info(f"Index saved to {index_file_path}")

    logger.info("Knowledge base processed and vector store created")
    return vector_store

def get_vector_store() -> FAISS:
    """Get cached vector store."""
    return setup_knowledge_base()

def retrieve_context(user_query: str) -> str:
    """Retrieve relevant context from the vector store for a user query."""
    logger.debug(f"Retrieving context for query: {user_query}")

    # Get vector store
    vector_store = get_vector_store()

    # Get documents and their similarity scores
    docs_with_scores = vector_store.similarity_search_with_score(
        user_query,
        k=Config.SIMILARITY_SEARCH_K
    )

    # Filter results with similarity score less than a threshold
    filtered_docs = [doc for doc, score in docs_with_scores]

    # If no documents, return empty context
    if not docs_with_scores:
        logger.warning("No relevant context found from the knowledge base")
        return "<context>\nNo relevant context found from the knowledge base.\n</context>"

    # Use Cohere API for reranking
    co = cohere.Client(Config.COHERE_API_KEY)
    rerank_results = co.rerank(
        model=Config.RERANK_MODEL,
        query=user_query,
        documents=[doc.page_content for doc in filtered_docs],
        top_n=Config.RERANK_TOP_N
    )

    reranked_docs = []
    for i in range(len(rerank_results.results)):
        reranked_docs.append(filtered_docs[rerank_results.results[i].index])

    context_content = "\n".join([doc.page_content for doc in reranked_docs])
    context_message = f"<context>\n{context_content}\n</context>"

    logger.debug(f"Retrieved {len(reranked_docs)} relevant documents")
    return context_message