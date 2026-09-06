LOANSPHERE
AI-Powered Loan Agreement Platform
Full Project Specification for Antigravity IDE
Project
LoanSphere — Major Project
Version
1.0.0
Stack
Python · Flask · spaCy · LangChain · PostgreSQL · FAISS
Deployment
Hosted Web App (Render / Railway)
Author
Vansh Jha
Date
April 2026
CONFIDENTIAL — COLLEGE MAJOR PROJECT
1. Project Overview
LoanSphere is a web-based AI platform that allows college students and learners to generate, summarize, and query loan agreements without legal expertise. It combines natural language processing, document generation, and a conversational AI interface into a single hosted application.
1.1  Problem Statement
Loan agreements are complex legal documents that most people cannot interpret without expert help.
Manual document drafting is error-prone and time-consuming.
Students and first-time borrowers have no accessible, affordable tool to understand their own loan terms.
1.2  Solution Summary
Target users
College students, first-time borrowers, learners
Core value
Turn complex loan documents into plain English — and generate new ones instantly
Deployment
Hosted web app (Render or Railway), accessible from any browser
AI approach
LangChain + HuggingFace models + spaCy NER + FAISS vector search
2. Feature Specification
LoanSphere has four core AI-powered features, each accessible from its own page in the web app.
Feature 1 — Loan Agreement Generator
The user fills a structured form with loan details. The system generates a complete, legally structured loan agreement as a downloadable DOCX or PDF file, with a live HTML preview in the browser.
Input fields (form)
Field
Type / Format
Description
borrower_name
String
Full legal name of the borrower
lender_name
String
Full legal name of the lender
loan_amount
Float (INR/USD)
Principal loan amount
interest_rate
Float (%)
Annual interest rate
tenure_months
Integer
Repayment period in months
start_date
Date (YYYY-MM-DD)
Loan disbursement date
collateral
String (optional)
Asset pledged as security
penalty_clause
String (optional)
Custom penalty for default
governing_law
String
Jurisdiction (e.g. Indian Contract Act, 1872)
Output
DOCX file with proper legal formatting (clauses, signatures, schedules)
Inline HTML preview rendered in the browser before download
PDF version generated server-side via python-docx + reportlab
Tech components
Jinja2 template: loan_template.docx.j2 — base legal document with {{ }} placeholders
python-docx: populates template and generates .docx
LangChain PromptTemplate: optionally rewrites clauses in plain English for readability
Flask route: POST /api/generate accepts JSON, returns file download URL
Feature 2 — Document Summarizer
The user uploads an existing loan agreement (PDF or DOCX). The system extracts the text, runs summarization, and returns the key terms as highlighted cards on screen.
Input
Field
Type / Format
Description
file
PDF or DOCX upload
Uploaded loan agreement (max 10MB)
summary_mode
Enum: brief / detailed
brief = 5 bullet points, detailed = section-by-section
Output (summary cards)
Loan amount & interest rate
Repayment schedule summary
Penalty / default clause
Collateral details
Governing law & jurisdiction
Tech components
PyMuPDF (fitz) for PDF text extraction; python-docx for DOCX extraction
Tesseract OCR (pytesseract) for scanned / image-based PDFs
HuggingFace transformers: facebook/bart-large-cnn for abstractive summarization
Fallback: extractive summarization with sumy or LexRank for very long documents
Flask route: POST /api/summarize — returns JSON with labelled card data
Feature 3 — Clause Extractor
The system identifies and labels specific legal clauses within an uploaded document. Each extracted clause is highlighted with its type and shown with a confidence score.
Clause types extracted
Field
Type / Format
Description
REPAYMENT
Date + schedule
When and how much is due each period
INTEREST
Rate + type
Fixed or floating, annual/monthly
PENALTY
Trigger + amount
Default condition and penalty amount
COLLATERAL
Asset description
Physical or financial asset pledged
PREPAYMENT
Charges + conditions
Early repayment terms
GOVERNING_LAW
Jurisdiction string
Applicable law and courts
TERMINATION
Conditions
How the agreement can end early
Tech components
spaCy en_core_web_lg: base NER for entities (ORG, MONEY, DATE, PERSON)
Custom spaCy NER component trained on a small loan agreement dataset (~200 annotated sentences)
Regex fallback patterns for structured fields (amounts, dates, percentages)
sentence-transformers (all-MiniLM-L6-v2): embed each extracted clause
FAISS index: store clause embeddings for semantic search by the Chatbot module
Flask route: POST /api/extract — returns JSON array of { clause_type, text, start_char, end_char, confidence }
Feature 4 — AI Chatbot / Q&A
A conversational interface where the user can ask plain-English questions about an uploaded loan agreement. The chatbot answers using the actual document content (RAG), not general knowledge, and cites the relevant clause.
Example Q&A flows
Field
Type / Format
Description
What is my interest rate?
Searches INTEREST clause
Returns rate from extracted clause with citation
What happens if I miss a payment?
Searches PENALTY clause
Returns penalty text with clause reference
Can I repay early?
Searches PREPAYMENT clause
Returns prepayment conditions
When is my first EMI due?
Searches REPAYMENT clause
Returns first payment date
Tech components
LangChain ConversationalRetrievalChain: manages multi-turn conversation with document context
FAISS vector store (from Extractor module): semantic retrieval of relevant clauses
HuggingFace Inference API or local model: answers are generated grounded in retrieved context
Conversation memory: LangChain ConversationBufferWindowMemory (last 5 turns)
Flask route: POST /api/chat — accepts { session_id, message } returns { answer, cited_clause }
Note: The chatbot is scoped to the user's uploaded document only. It will not answer general legal questions outside the document context.
3. Project Folder Structure
Paste this structure into Antigravity as the scaffold prompt. Every file listed here needs to be created.
LoanSphere/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Env vars, DB URL, model paths
│   ├── routes/
│   │   ├── generate.py          # POST /api/generate
│   │   ├── summarize.py         # POST /api/summarize
│   │   ├── extract.py           # POST /api/extract
│   │   ├── chat.py              # POST /api/chat
│   │   └── auth.py              # POST /api/register, /api/login
│   ├── models/
│   │   ├── generator.py         # Jinja2 + python-docx logic
│   │   ├── summarizer.py        # HuggingFace BART pipeline
│   │   ├── extractor.py         # spaCy NER + FAISS indexing
│   │   └── chatbot.py           # LangChain RAG chain
│   ├── db/
│   │   ├── schema.sql           # All CREATE TABLE statements
│   │   └── db.py                # psycopg2 connection pool
│   └── utils/
│       ├── pdf_utils.py         # PDF extract + OCR helpers
│       ├── docx_utils.py        # DOCX read / write helpers
│       └── file_utils.py        # Upload validation, temp cleanup
├── templates/                   # Jinja2 loan agreement templates
│   └── loan_agreement_base.docx # Base DOCX template with placeholders
├── static/
│   ├── css/
│   │   └── main.css
│   ├── js/
│   │   ├── generator.js
│   │   ├── summarizer.js
│   │   ├── extractor.js
│   │   └── chatbot.js
│   └── uploads/                 # Temp storage for user files
├── frontend/                    # HTML pages
│   ├── index.html               # Landing / dashboard
│   ├── generator.html
│   ├── summarizer.html
│   ├── extractor.html
│   └── chatbot.html
├── main.py                      # Entry point: flask run
├── requirements.txt
├── Procfile                     # For Render/Railway deployment
└── .env                         # Secrets (never commit)
4. Database Schema (PostgreSQL)
Run schema.sql once during project setup. All tables use UUID primary keys for safety.
4.1  users
Column
Type
Constraint
Description
id
UUID
PRIMARY KEY DEFAULT gen_random_uuid()
Unique user identifier
email
VARCHAR(255)
UNIQUE NOT NULL
Login email address
password_hash
VARCHAR(255)
NOT NULL
bcrypt hashed password
full_name
VARCHAR(255)
NOT NULL
Display name
created_at
TIMESTAMP
DEFAULT NOW()
Account creation time
4.2  documents
Column
Type
Constraint
Description
id
UUID
PRIMARY KEY DEFAULT gen_random_uuid()
Unique document ID
user_id
UUID
REFERENCES users(id) ON DELETE CASCADE
Owner of the document
filename
VARCHAR(255)
NOT NULL
Original uploaded filename
file_path
TEXT
NOT NULL
Server-side storage path
doc_type
VARCHAR(50)
DEFAULT 'uploaded'
uploaded or generated
created_at
TIMESTAMP
DEFAULT NOW()
Upload/creation timestamp
4.3  extracted_clauses
Column
Type
Constraint
Description
id
UUID
PRIMARY KEY DEFAULT gen_random_uuid()
Clause record ID
document_id
UUID
REFERENCES documents(id) ON DELETE CASCADE
Parent document
clause_type
VARCHAR(100)
NOT NULL
e.g. PENALTY, INTEREST
clause_text
TEXT
NOT NULL
Extracted clause content
confidence
FLOAT
DEFAULT 0.0
NER confidence score 0-1
start_char
INTEGER
Start position in original text
end_char
INTEGER
End position in original text
4.4  chat_sessions
Column
Type
Constraint
Description
id
UUID
PRIMARY KEY DEFAULT gen_random_uuid()
Session identifier
user_id
UUID
REFERENCES users(id) ON DELETE CASCADE
Session owner
document_id
UUID
REFERENCES documents(id)
Document being queried
created_at
TIMESTAMP
DEFAULT NOW()
Session start time
4.5  chat_messages
Column
Type
Constraint
Description
id
UUID
PRIMARY KEY DEFAULT gen_random_uuid()
Message ID
session_id
UUID
REFERENCES chat_sessions(id) ON DELETE CASCADE
Parent session
role
VARCHAR(20)
CHECK (role IN ('user','assistant'))
Sender role
content
TEXT
NOT NULL
Message text
cited_clause
TEXT
Clause reference cited in answer
created_at
TIMESTAMP
DEFAULT NOW()
Message timestamp
5. API Contracts
Each route accepts JSON (or multipart/form-data for file uploads) and returns JSON. All routes except /api/register and /api/login require a JWT Bearer token in the Authorization header.
5.1  POST /api/generate
Request body (application/json)
{ "borrower_name": "Riya Sharma",
  "lender_name": "SBI Bank",
  "loan_amount": 500000,
  "interest_rate": 8.5,
  "tenure_months": 60,
  "start_date": "2026-05-01",
  "collateral": "2016 Honda Activa",
  "penalty_clause": "2% of outstanding per month",
  "governing_law": "Indian Contract Act, 1872" }
Response (200 OK)
{ "document_id": "uuid-here",
  "download_url": "/static/generated/loan_uuid.docx",
  "preview_html": "<html>...</html>" }
5.2  POST /api/summarize
Request (multipart/form-data)
file: PDF or DOCX file (max 10MB)
summary_mode: brief | detailed
Response (200 OK)
{ "document_id": "uuid-here",
  "cards": [
    { "label": "Loan Amount", "value": "INR 5,00,000" },
    { "label": "Interest Rate", "value": "8.5% per annum" },
    { "label": "Tenure", "value": "60 months" },
    { "label": "Penalty", "value": "2% of outstanding per month" }
  ] }
5.3  POST /api/extract
Request (multipart/form-data)
file: PDF or DOCX file
Response (200 OK)
{ "document_id": "uuid-here",
  "clauses": [
    { "clause_type": "INTEREST",
      "clause_text": "The loan shall carry interest at 8.5% per annum",
      "confidence": 0.94,
      "start_char": 142, "end_char": 198 }
  ] }
5.4  POST /api/chat
Request (application/json)
{ "session_id": "uuid-here",
  "document_id": "uuid-here",
  "message": "What happens if I miss a payment?" }
Response (200 OK)
{ "answer": "According to clause 7, a penalty of 2% of the outstanding...",
  "cited_clause": "PENALTY",
  "cited_text": "The borrower shall pay a penalty of 2%..." }
6. requirements.txt
Paste this as your requirements.txt. Pin major versions for reproducibility.
flask==3.0.3
flask-cors==4.0.1
flask-jwt-extended==4.6.0
psycopg2-binary==2.9.9
python-docx==1.1.2
jinja2==3.1.4
pymupdf==1.24.5
pytesseract==0.3.10
transformers==4.41.2
torch==2.3.0
sentence-transformers==3.0.1
faiss-cpu==1.8.0
spacy==3.7.4
langchain==0.2.5
langchain-community==0.2.5
langchain-huggingface==0.0.3
sumy==0.11.0
bcrypt==4.1.3
python-dotenv==1.0.1
gunicorn==22.0.0
After installing, run:
python -m spacy download en_core_web_lg
7. Environment Variables (.env)
Note: Never commit .env to GitHub. Add it to .gitignore immediately.
DATABASE_URL
postgresql://user:pass@host:5432/loansphere
JWT_SECRET_KEY
any-long-random-string-here
UPLOAD_FOLDER
static/uploads
GENERATED_FOLDER
static/generated
MAX_FILE_SIZE_MB
10
HUGGINGFACE_API_KEY
hf_xxxxxxxxxxxxxxxx (from huggingface.co/settings/tokens)
FLASK_ENV
development (change to production on deploy)
8. Recommended Build Order for Antigravity
Follow this exact sequence. Each phase gives you a working, demonstrable output before moving to the next — important for incremental college reviews.
Phase 1 — Scaffold (Day 1)
Create the full folder structure as listed in Section 3
Set up Flask app factory in app/__init__.py with Blueprint registration
Configure PostgreSQL connection in app/db/db.py using psycopg2 connection pool
Run schema.sql to create all 5 tables
Implement /api/register and /api/login with bcrypt + JWT
Deliverable: Flask server runs, user can register and log in, DB tables exist
Phase 2 — Generator (Day 2–3)
Create loan_agreement_base.docx template with {{ }} Jinja2 placeholders for all fields
Build generator.py: loads template, fills placeholders, saves output DOCX
Build generate.html: form with all input fields, submit calls POST /api/generate
Render HTML preview of the generated document inline on the page
Add PDF export option
Deliverable: User fills form, gets a downloadable loan agreement DOCX
Phase 3 — Summarizer (Day 4–5)
Build pdf_utils.py and docx_utils.py for text extraction and OCR
Build summarizer.py: BART pipeline on extracted text, returns key cards
Build summarizer.html: file upload area, display summary cards on success
Flask route: POST /api/summarize
Deliverable: User uploads loan PDF, gets 5 key-term cards
Phase 4 — Clause Extractor (Day 6–7)
Build extractor.py: spaCy NER pipeline + regex fallbacks for each clause type
Embed extracted clauses with sentence-transformers, store in FAISS index per document_id
Build extractor.html: file upload + visual clause highlighting with color-coded chips
Flask route: POST /api/extract, store results in extracted_clauses table
Deliverable: User uploads a document, sees every clause type highlighted and labelled
Phase 5 — Chatbot (Day 8–10)
Build chatbot.py: LangChain ConversationalRetrievalChain backed by the FAISS index from Phase 4
Add ConversationBufferWindowMemory (k=5) so the chatbot remembers context
Build chatbot.html: chat UI with message bubbles, citation display below each answer
Flask route: POST /api/chat, log all messages to chat_messages table
Deliverable: User can ask plain-English questions about any uploaded document
Phase 6 — Polish & Deploy (Day 11–14)
Build index.html dashboard linking all four tools
Add document history page: list all a user's uploaded and generated docs
Responsive CSS for mobile browsers
Write Procfile: web: gunicorn main:app
Deploy to Render.com (free tier) or Railway — link PostgreSQL add-on
Run end-to-end tests with a real loan agreement PDF
9. Antigravity Prompt Templates
Use these prompts verbatim when building each module. They include the full context Antigravity needs to generate working code.
Prompt 1 — Flask scaffold
Create a Flask application called LoanSphere. Use an app factory pattern in app/__init__.py. Register four Blueprints: generate_bp, summarize_bp, extract_bp, chat_bp, each in their own file under app/routes/. Add Flask-CORS, Flask-JWT-Extended. Create a PostgreSQL connection pool in app/db/db.py using psycopg2. Add /api/register (POST) and /api/login (POST) routes in app/routes/auth.py using bcrypt for password hashing and JWT for tokens. Create main.py as the entry point. Create .env with DATABASE_URL, JWT_SECRET_KEY, UPLOAD_FOLDER, GENERATED_FOLDER variables.
Prompt 2 — Generator module
Create app/models/generator.py. It should accept a dictionary with keys: borrower_name, lender_name, loan_amount, interest_rate, tenure_months, start_date, collateral, penalty_clause, governing_law. Load a Jinja2 DOCX template from templates/loan_agreement_base.docx, fill all placeholders, and save the output to GENERATED_FOLDER with a UUID filename. Return the output file path and an HTML string preview. Create app/routes/generate.py with POST /api/generate that calls this module, saves document metadata to the documents table, and returns { document_id, download_url, preview_html }.
Prompt 3 — Summarizer module
Create app/models/summarizer.py. Accept a file path and summary_mode (brief or detailed). Use PyMuPDF to extract text from PDFs and python-docx for DOCX files. Fall back to pytesseract OCR if text extraction returns less than 100 characters. Run the HuggingFace pipeline facebook/bart-large-cnn on the extracted text. Return a list of dicts: [{ label, value }] covering loan amount, interest rate, tenure, penalty clause, and governing law. Create app/routes/summarize.py with POST /api/summarize accepting multipart/form-data file upload.
Prompt 4 — Extractor module
Create app/models/extractor.py. Load spaCy en_core_web_lg. Define regex patterns for INTEREST, REPAYMENT, PENALTY, COLLATERAL, PREPAYMENT, GOVERNING_LAW, and TERMINATION clause types. For each sentence in the document text, run spaCy NER and regex to identify the clause type. Embed each extracted clause using sentence-transformers all-MiniLM-L6-v2. Store embeddings in a FAISS IndexFlatL2 index keyed by document_id, saved to disk as faiss_store/{document_id}.index. Return list of { clause_type, clause_text, confidence, start_char, end_char }. Create app/routes/extract.py with POST /api/extract.
Prompt 5 — Chatbot module
Create app/models/chatbot.py. Load the FAISS index for a given document_id from faiss_store/{document_id}.index. Use LangChain FAISS vectorstore wrapper with sentence-transformers all-MiniLM-L6-v2 as the embedding model. Create a ConversationalRetrievalChain with ConversationBufferWindowMemory(k=5). Use HuggingFaceHub with mistralai/Mistral-7B-Instruct-v0.2 as the LLM (via HUGGINGFACE_API_KEY). The chain should return the answer and the source document chunk it cited. Create app/routes/chat.py with POST /api/chat accepting { session_id, document_id, message } and saving messages to the chat_messages table.
10. Pre-Submission Checklist
Go through this before your final demo:
All 4 features work end-to-end with a real sample loan agreement PDF
User registration and login flow is working with JWT auth
Generated DOCX downloads correctly and opens in MS Word / Google Docs
Summarizer handles a scanned PDF (OCR path tested)
Clause extractor correctly identifies at least 4 of the 7 clause types
Chatbot cites the correct clause in its answers
App is deployed and accessible via a public URL
No .env file or secrets committed to GitHub
README.md explains what the project does, how to run locally, and what each route does
requirements.txt is frozen with exact versions (pip freeze > requirements.txt)
LoanSphere — Spec v1.0  |  Built with Antigravity + Claude  |  April 2026