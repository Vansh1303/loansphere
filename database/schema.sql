-- LoanSphere Database Schema
-- PostgreSQL 12+

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    doc_type VARCHAR(50) DEFAULT 'uploaded',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Extracted clauses table
CREATE TABLE IF NOT EXISTS extracted_clauses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    clause_type VARCHAR(100) NOT NULL,
    clause_text TEXT NOT NULL,
    confidence FLOAT DEFAULT 0.0,
    start_char INTEGER,
    end_char INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Chat sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Chat messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user','assistant')),
    content TEXT NOT NULL,
    cited_clause TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_extracted_clauses_document_id ON extracted_clauses(document_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_document_id ON chat_sessions(document_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);

-- KYC records table
CREATE TABLE IF NOT EXISTS kyc_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    pan_number VARCHAR(10),
    pan_verified BOOLEAN DEFAULT FALSE,
    pan_verified_name VARCHAR(255),
    aadhaar_number_masked VARCHAR(20),
    aadhaar_format_valid BOOLEAN DEFAULT FALSE,
    bank_account_number VARCHAR(30),
    bank_ifsc VARCHAR(11),
    bank_verified BOOLEAN DEFAULT FALSE,
    bank_verified_name VARCHAR(255),
    full_name VARCHAR(255),
    date_of_birth DATE,
    kyc_status VARCHAR(20) DEFAULT 'not_started',
    rejection_reason TEXT,
    submitted_at TIMESTAMP,
    verified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kyc_records_user_id ON kyc_records(user_id);

-- Financial profiles table
CREATE TABLE IF NOT EXISTS financial_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    monthly_income FLOAT,
    employment_type VARCHAR(30),
    employment_start_date DATE,
    existing_emis_monthly FLOAT DEFAULT 0,
    existing_loans_count INT DEFAULT 0,
    credit_card_limit_total FLOAT DEFAULT 0,
    credit_card_outstanding_total FLOAT DEFAULT 0,
    on_time_payments_pct FLOAT DEFAULT 100,
    missed_payments_count_12m INT DEFAULT 0,
    defaults_count INT DEFAULT 0,
    settlements_count INT DEFAULT 0,
    credit_history_length_years FLOAT DEFAULT 0,
    hard_inquiries_6m INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_financial_profiles_user_id ON financial_profiles(user_id);

-- Credit scores table
CREATE TABLE IF NOT EXISTS credit_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    requested_loan_amount FLOAT,
    requested_tenure_months INT,
    requested_loan_type VARCHAR(20),
    score INT,
    band VARCHAR(20),
    component_breakdown JSONB,
    explanation JSONB,
    computed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credit_scores_user_id ON credit_scores(user_id);
