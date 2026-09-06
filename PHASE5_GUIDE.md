# Phase 5: Chatbot Implementation Guide

## Overview
Phase 5 implements an AI-powered chatbot that allows users to ask plain-English questions about uploaded loan agreements. The chatbot uses Retrieval Augmented Generation (RAG) with FAISS vector search and LangChain's ConversationalRetrievalChain.

## Components

### 1. app/models/chatbot.py
Main chatbot module that handles the RAG chain creation and document querying.

**Key Functions:**
- `get_embedder()` - Lazy loads sentence-transformers all-MiniLM-L6-v2
- `get_llm()` - Lazy loads HuggingFaceHub with Mistral-7B-Instruct-v0.2
- `create_chat_chain(document_id)` - Creates a ConversationalRetrievalChain for a document
- `query_document(document_id, message)` - Queries a document and returns answer with source

**Features:**
- Loads pre-built FAISS indexes from `faiss_store/{document_id}.index`
- Uses ConversationBufferWindowMemory with k=5 for context
- Returns both answer and source document chunks
- Includes metadata retrieval for citing clauses

### 2. app/routes/chat.py
Flask routes for chat functionality.

**Endpoints:**

#### POST /api/chat/session
Create a new chat session for a document.

```json
Request:
{
    "document_id": "uuid-here"
}

Response (201):
{
    "session_id": "uuid-here",
    "document_id": "uuid-here",
    "message": "Session created successfully"
}
```

#### POST /api/chat
Send a message and receive an answer.

```json
Request:
{
    "session_id": "uuid-here",
    "document_id": "uuid-here",
    "message": "What is the interest rate?"
}

Response (200):
{
    "answer": "The interest rate is 8.5% per annum...",
    "cited_clause": "INTEREST",
    "cited_text": "The loan shall carry interest at 8.5% per annum"
}
```

**Features:**
- JWT authentication required for both endpoints
- Validates session ownership and document access
- Saves all messages to `chat_messages` table
- Stores both user and assistant messages
- Includes error handling for missing documents

### 3. database/schema.sql
PostgreSQL schema for chat functionality.

**New Tables:**
- `chat_sessions` - Conversation sessions per document
- `chat_messages` - Individual messages in conversations

**Schema Details:**
```sql
chat_sessions:
- id: UUID (primary key)
- user_id: UUID (foreign key to users)
- document_id: UUID (foreign key to documents)
- created_at: TIMESTAMP

chat_messages:
- id: UUID (primary key)
- session_id: UUID (foreign key to chat_sessions)
- role: VARCHAR(20) - 'user' or 'assistant'
- content: TEXT - message content
- cited_clause: TEXT - source document reference
- created_at: TIMESTAMP
```

### 4. app/db/db.py
Enhanced database module with schema initialization.

**New Function:**
- `initialize_database()` - Reads schema.sql and applies it to PostgreSQL on app startup

### 5. app/models/extractor.py (Updated)
Enhanced to save metadata alongside FAISS indexes.

**Changes:**
- Now saves `faiss_store/{document_id}_metadata.json` with clause information
- Metadata includes: clause_type, clause_text, confidence, start_char, end_char
- Enables chatbot to retrieve source documents accurately

## Setup Instructions

### 1. Environment Variables
Add to `.env`:
```
HUGGINGFACE_API_KEY=your_huggingface_api_key_here
DATABASE_URL=postgresql://user:password@localhost/loansphere
JWT_SECRET_KEY=your_secret_key_here
```

### 2. Get HuggingFace API Key
1. Go to https://huggingface.co/settings/tokens
2. Create a new token with read access
3. Copy and paste into .env

### 3. Database Initialization
The database schema is automatically initialized when the Flask app starts.

### 4. First FAISS Index
The chatbot requires documents to be processed through Phase 4 (Extractor) first:
```
1. User uploads document
2. POST /api/extract creates FAISS index
3. Index stored as faiss_store/{document_id}.index
4. Metadata stored as faiss_store/{document_id}_metadata.json
5. User can now create chat session and ask questions
```

## Workflow

### User Workflow
```
1. User registers/logs in (JWT token obtained)
2. User uploads document (Phase 4 - Extractor)
   - FAISS index created and stored
   - Metadata saved alongside index
3. User creates chat session via POST /api/chat/session
   - Session ID obtained
4. User sends messages via POST /api/chat
   - LLM generates answer using RAG
   - Source documents cited
   - Conversation saved to database
```

### Technical Workflow
```
1. Chatbot receives query
2. Loads FAISS index and metadata
3. Retrieves 4 most relevant clause chunks
4. LLM generates answer using context
5. ConversationBufferWindowMemory(k=5) maintains 5-turn history
6. Answer and source returned to user
7. Messages saved to chat_messages table
```

## LLM Configuration

**Model:** mistralai/Mistral-7B-Instruct-v0.2
- Instruction-tuned model
- Optimized for chat and Q&A
- Supports long context windows

**Parameters:**
- temperature: 0.7 - Balance between creativity and accuracy
- top_p: 0.95 - Nucleus sampling for diversity
- max_new_tokens: 256 - Reasonable answer length

## Error Handling

**Common Errors:**

1. **HUGGINGFACE_API_KEY not set**
   - Solution: Add API key to .env file

2. **Document not indexed**
   - Solution: Run document through Phase 4 (Extractor) first

3. **Session not found**
   - Solution: Create session first via /api/chat/session

4. **Database connection error**
   - Solution: Check DATABASE_URL in .env

## Performance Considerations

1. **FAISS Index Loading**: Indexes are loaded per query (consider caching for high-traffic)
2. **LLM Response Time**: First call may take 10-30s (model loading)
3. **Memory Usage**: ConversationBufferWindowMemory(k=5) keeps 5 turns in memory
4. **Database**: All messages saved asynchronously (non-blocking)

## Future Enhancements

1. **Conversation Caching**: Cache active conversations to reduce index reloads
2. **Multiple Document Support**: Query across multiple documents in one session
3. **Citation Highlighting**: Return exact text spans for highlighting
4. **Custom System Prompt**: Allow users to customize chatbot behavior
5. **Feedback Loop**: Rate response quality for fine-tuning
6. **Async Processing**: Make LLM calls asynchronous for better scalability

## Testing

```bash
# 1. Create chat session
curl -X POST http://localhost:5000/api/chat/session \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"document_id": "uuid-of-document"}'

# 2. Send message
curl -X POST http://localhost:5000/api/chat \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "uuid-of-session",
    "document_id": "uuid-of-document",
    "message": "What is the interest rate?"
  }'
```

## Troubleshooting

1. **Slow responses**: LLM may need warm-up or API might be rate-limiting
2. **Poor answer quality**: Ensure document is properly indexed through Phase 4
3. **Source not cited**: Check metadata file exists at `faiss_store/{document_id}_metadata.json`
4. **Memory errors**: Reduce ConversationBufferWindowMemory k value or document batch size
