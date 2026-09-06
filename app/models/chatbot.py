import os
import json
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

_embedder = None

def get_embedder():
    """Lazy load the sentence transformer embedder"""
    global _embedder
    if _embedder is None:
        _embedder = HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2')
    return _embedder

def query_document(document_id, message, chat_history=None):
    embeddings = get_embedder()
    vectorstore = FAISS.load_local(f'faiss_store/{document_id}', embeddings, allow_dangerous_deserialization=True)
    docs = vectorstore.similarity_search(message, k=3)
    if docs:
        answer = docs[0].page_content
        clause_type = docs[0].metadata.get('clause_type', 'DOCUMENT')
        return {'answer': answer, 'cited_clause': clause_type, 'cited_text': answer}
    return {'answer': 'Could not find relevant information.', 'cited_clause': 'NONE', 'cited_text': ''}
