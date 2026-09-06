import os
import re
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words
from app.utils.pdf_utils import extract_text_from_pdf
from app.utils.docx_utils import extract_text_from_docx

LANGUAGE = "english"
SENTENCES_COUNT = 5


def extractive_summarize(text, sentence_count=SENTENCES_COUNT):
    """Use LsaSummarizer to extract the N most important sentences."""
    parser = PlaintextParser.from_string(text, Tokenizer(LANGUAGE))
    stemmer = Stemmer(LANGUAGE)
    summarizer = LsaSummarizer(stemmer)
    summarizer.stop_words = get_stop_words(LANGUAGE)
    sentences = summarizer(parser.document, sentence_count)
    return " ".join(str(s) for s in sentences)


def summarize_document(file_path, summary_mode="brief"):
    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.pdf':
        text = extract_text_from_pdf(file_path)
    elif ext in ['.docx', '.doc']:
        text = extract_text_from_docx(file_path)
    else:
        raise ValueError("Unsupported file format")

    if len(text.strip()) == 0:
        raise ValueError("Could not extract any text from the document.")

    # Number of sentences scales with mode
    n_sentences = SENTENCES_COUNT if summary_mode == "brief" else 10
    abstract_summary = extractive_summarize(text, n_sentences)

    # ── Regex field extraction ────────────────────────────────────────────────

    loan_amount = "Not Found"
    interest_rate = "Not Found"
    tenure = "Not Found"
    penalty = "Not Found"
    governing_law = "Not Found"

    # Loan amount: Rs./INR/$  followed by digits
    amount_match = re.search(
        r'(?:Rs\.?|INR|\$|USD)\s*[\d,]+(?:\.\d{1,2})?'
        r'|(?:sum|amount|loan)\s+of\s+(?:Rs\.?|INR|\$)?\s*[\d,]+(?:\.\d{1,2})?',
        text, re.IGNORECASE
    )
    if amount_match:
        loan_amount = amount_match.group(0).strip()

    # Interest rate: number followed by % per annum / p.a.
    interest_match = re.search(
        r'([\d\.]+)\s*%\s*(?:per\s+annum|p\.a\.|per\s+year|annually)?',
        text, re.IGNORECASE
    )
    if interest_match:
        suffix = interest_match.group(0).split('%', 1)[1].strip()
        interest_rate = f"{interest_match.group(1)}% {suffix}".strip() if suffix else f"{interest_match.group(1)}% per annum"

    # Tenure: digits followed by months/years
    tenure_match = re.search(
        r'(\d+)\s*(months?|years?)',
        text, re.IGNORECASE
    )
    if tenure_match:
        tenure = f"{tenure_match.group(1)} {tenure_match.group(2)}"

    # Penalty: "penalty … X%"  or "X% penalty"
    penalty_match = re.search(
        r'penalty[\s\w]{0,30}([\d\.]+)\s*%'
        r'|([\d\.]+)\s*%[\s\w]{0,20}penalty',
        text, re.IGNORECASE
    )
    if penalty_match:
        pct = penalty_match.group(1) or penalty_match.group(2)
        penalty = f"{pct}% penalty"

    # Governing law: "governed by / laws of <State/Country>"
    gov_match = re.search(
        r'(?:governed\s+by|laws?\s+of|jurisdiction\s+of)\s+(?:the\s+)?([A-Z][a-zA-Z\s]{2,40})',
        text
    )
    if gov_match:
        governing_law = gov_match.group(1).strip()

    # ── Build response cards ─────────────────────────────────────────────────
    cards = [
        {"label": "Document Summary",  "value": abstract_summary},
        {"label": "Loan Amount",        "value": loan_amount},
        {"label": "Interest Rate",      "value": interest_rate},
        {"label": "Tenure",             "value": tenure},
        {"label": "Penalty",            "value": penalty},
        {"label": "Governing Law",      "value": governing_law},
    ]

    return cards
