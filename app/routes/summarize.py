from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import os
import uuid
from app.models.summarizer import summarize_document
from app.db.db import get_connection, release_connection

summarize_bp = Blueprint('summarize', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@summarize_bp.route('/summarize', methods=['POST'])
@jwt_required()
def summarize():
    if 'file' not in request.files:
        return jsonify({"msg": "No file part in the request"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"msg": "No selected file"}), 400
        
    if not allowed_file(file.filename):
        return jsonify({"msg": "File type not allowed. Please upload PDF or DOCX."}), 400
        
    summary_mode = request.form.get('summary_mode', 'brief')
    
    upload_folder = os.environ.get('UPLOAD_FOLDER', 'static/uploads')
    os.makedirs(upload_folder, exist_ok=True)
    
    document_id = str(uuid.uuid4())
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = secure_filename(f"upload_{document_id}.{ext}")
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)
    
    try:
        cards = summarize_document(file_path, summary_mode)
    except Exception as e:
        return jsonify({"msg": f"Error summarizing document: {str(e)}"}), 500
        
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
                    (document_id, user_id, file.filename, file_path, "uploaded")
                )
                conn.commit()
        except Exception as e:
            conn.rollback()
            return jsonify({"msg": f"Database error: {str(e)}"}), 500
        finally:
            release_connection(conn)
            
    return jsonify({
        "document_id": document_id,
        "cards": cards
    }), 200
