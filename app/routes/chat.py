from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import uuid
from app.models.chatbot import query_document
from app.db.db import get_connection, release_connection

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/chat/session', methods=['POST'])
@jwt_required()
def create_session():
    """
    Create a new chat session for a document.
    
    Request JSON:
    {
        "document_id": "uuid-here"
    }
    
    Response JSON:
    {
        "session_id": "uuid-here",
        "document_id": "uuid-here",
        "created_at": "timestamp"
    }
    """
    data = request.get_json()
    
    if not data or not data.get("document_id"):
        return jsonify({"msg": "Missing required field: document_id"}), 400
    
    document_id = data.get("document_id")
    user_id = get_jwt_identity()
    session_id = str(uuid.uuid4())
    
    conn = get_connection()
    if not conn:
        return jsonify({"msg": "Database connection error"}), 500
    
    try:
        with conn.cursor() as cursor:
            # Verify document exists and belongs to user
            cursor.execute(
                "SELECT id FROM documents WHERE id = %s AND user_id = %s",
                (document_id, user_id)
            )
            if not cursor.fetchone():
                return jsonify({"msg": "Document not found"}), 404
            
            # Create new session
            cursor.execute(
                """
                INSERT INTO chat_sessions (id, user_id, document_id, created_at)
                VALUES (%s, %s, %s, NOW())
                """,
                (session_id, user_id, document_id)
            )
            conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({"msg": f"Database error: {str(e)}"}), 500
    finally:
        release_connection(conn)
    
    return jsonify({
        "session_id": session_id,
        "document_id": document_id,
        "message": "Session created successfully"
    }), 201

@chat_bp.route('/chat', methods=['POST'])
@jwt_required()
def chat():
    """
    Chat endpoint that accepts a message and returns an AI response.
    
    Request JSON:
    {
        "session_id": "uuid-here",
        "document_id": "uuid-here",
        "message": "What is the interest rate?"
    }
    
    Response JSON:
    {
        "answer": "The interest rate is...",
        "cited_clause": "INTEREST",
        "cited_text": "..."
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({"msg": "No JSON data provided"}), 400
    
    session_id = data.get("session_id")
    document_id = data.get("document_id")
    message = data.get("message")
    
    # Validate required fields
    if not session_id or not document_id or not message:
        return jsonify({"msg": "Missing required fields: session_id, document_id, message"}), 400
    
    user_id = get_jwt_identity()
    
    # Verify session belongs to user and document exists
    conn = get_connection()
    if not conn:
        return jsonify({"msg": "Database connection error"}), 500
    
    try:
        with conn.cursor() as cursor:
            # Verify session exists and belongs to user
            cursor.execute(
                "SELECT id FROM chat_sessions WHERE id = %s AND user_id = %s AND document_id = %s",
                (session_id, user_id, document_id)
            )
            if not cursor.fetchone():
                return jsonify({"msg": "Invalid session or document"}), 404
    except Exception as e:
        return jsonify({"msg": f"Database error: {str(e)}"}), 500
    finally:
        release_connection(conn)
    
    # Query the document using the chatbot module
    try:
        result = query_document(document_id, message)
    except FileNotFoundError as e:
        return jsonify({"msg": f"Document not found or not indexed: {str(e)}"}), 404
    except Exception as e:
        return jsonify({"msg": f"Error querying document: {str(e)}"}), 500
    
    # Save user message to database
    conn = get_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                message_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO chat_messages (id, session_id, role, content, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    """,
                    (message_id, session_id, "user", message)
                )
                
                # Save assistant response
                response_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO chat_messages (id, session_id, role, content, cited_clause, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    """,
                    (response_id, session_id, "assistant", result["answer"], result["cited_text"])
                )
                conn.commit()
        except Exception as e:
            conn.rollback()
            # Don't fail the request if we can't save to DB, just log it
            print(f"Warning: Could not save chat message to database: {str(e)}")
        finally:
            release_connection(conn)
    
    return jsonify({
        "answer": result["answer"],
        "cited_clause": result["cited_clause"],
        "cited_text": result["cited_text"]
    }), 200
