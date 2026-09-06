from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import os
import uuid
from app.models.extractor import extract_clauses
from app.db.db import get_connection, release_connection

extract_bp = Blueprint('extract', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@extract_bp.route('/extract', methods=['POST'])
@jwt_required()
def extract():
    if 'file' not in request.files:
        return jsonify({"msg": "No file part in the request"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"msg": "No selected file"}), 400
        
    if not allowed_file(file.filename):
        return jsonify({"msg": "File type not allowed. Please upload PDF or DOCX."}), 400
        
    upload_folder = os.environ.get('UPLOAD_FOLDER', 'static/uploads')
    os.makedirs(upload_folder, exist_ok=True)
    
    document_id = str(uuid.uuid4())
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = secure_filename(f"extract_{document_id}.{ext}")
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)
    
    try:
        clauses = extract_clauses(file_path, document_id)
    except Exception as e:
        return jsonify({"msg": f"Error extracting clauses: {str(e)}"}), 500
        
    user_id = get_jwt_identity()
    conn = get_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO documents (id, user_id, filename, file_path, doc_type)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (document_id, user_id, file.filename, file_path, "uploaded_extract")
                )
                
                for clause in clauses:
                    cursor.execute(
                        """
                        INSERT INTO extracted_clauses 
                        (document_id, clause_type, clause_text, confidence, start_char, end_char)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (document_id, clause["clause_type"], clause["clause_text"], 
                         clause["confidence"], clause["start_char"], clause["end_char"])
                    )
                conn.commit()
        except Exception as e:
            conn.rollback()
            return jsonify({"msg": f"Database error: {str(e)}"}), 500
        finally:
            release_connection(conn)
            
    return jsonify({
        "document_id": document_id,
        "clauses": clauses
    }), 200
