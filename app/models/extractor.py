import os
import re
import json
import spacy
import faiss
import numpy as np
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
from app.utils.pdf_utils import extract_text_from_pdf
from app.utils.docx_utils import extract_text_from_docx

_nlp = None
_embedder = None

def get_nlp():
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("en_core_web_lg")
        except Exception as e:
            print(f"Error loading spaCy model: {e}")
            _nlp = spacy.blank("en")
            _nlp.add_pipe("sentencizer")
    return _nlp

def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2')
    return _embedder

CLAUSE_PATTERNS = {
    "INTEREST": r"(?i)\b(interest|rate|per annum|p\.a\.)\b",
    "REPAYMENT": r"(?i)\b(repay|repayment|emi|installment|due|schedule)\b",
    "PENALTY": r"(?i)\b(penalty|default|late fee|breach)\b",
    "COLLATERAL": r"(?i)\b(collateral|pledge|security|asset|mortgage)\b",
    "PREPAYMENT": r"(?i)\b(prepayment|early repayment|foreclosure)\b",
    "GOVERNING_LAW": r"(?i)\b(governing law|jurisdiction|courts of|construed in accordance)\b",
    "TERMINATION": r"(?i)\b(termination|terminate|cancel|end early)\b"
}

def identify_clause(sentence_text):
    best_match = None
    max_score = 0
    
    for clause_type, pattern in CLAUSE_PATTERNS.items():
        matches = len(re.findall(pattern, sentence_text))
        if matches > max_score:
            max_score = matches
            best_match = clause_type
            
    confidence = 0.0
    if best_match:
        confidence = min(0.95, 0.4 + (max_score * 0.15))
        
    return best_match, confidence

def extract_clauses(file_path, document_id):
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.pdf':
        text = extract_text_from_pdf(file_path)
    elif ext in ['.docx', '.doc']:
        text = extract_text_from_docx(file_path)
    else:
        raise ValueError("Unsupported file format")

    nlp = get_nlp()
    # spaCy has a 1 million character limit by default, increase it just in case
    nlp.max_length = len(text) + 100000 
    doc = nlp(text)
    
    extracted = []
    
    for sent in doc.sents:
        clause_type, confidence = identify_clause(sent.text)
        if clause_type:
            extracted.append({
                "clause_type": clause_type,
                "clause_text": sent.text.strip(),
                "confidence": confidence,
                "start_char": sent.start_char,
                "end_char": sent.end_char
            })
            
    if not extracted:
        return []
        
    # Embeddings and FAISS
    embedder = get_embedder()
    
    documents = []
    for item in extracted:
        doc = Document(
            page_content=item["clause_text"],
            metadata={
                "clause_type": item["clause_type"],
                "confidence": item["confidence"],
                "start_char": item["start_char"],
                "end_char": item["end_char"]
            }
        )
        documents.append(doc)
    
    faiss_dir = "faiss_store"
    os.makedirs(faiss_dir, exist_ok=True)
    
    vectorstore = FAISS.from_documents(documents, embedder)
    vectorstore.save_local(os.path.join(faiss_dir, document_id))
    
    return extracted
