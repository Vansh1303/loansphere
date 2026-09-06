from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.generator import generate_loan_agreement
from app.models.kyc import require_kyc_verified
from app.db.db import get_connection, release_connection
import os

generate_bp = Blueprint('generate', __name__)

@generate_bp.route('/generate', methods=['POST'])
@jwt_required()
def generate():
    user_id = get_jwt_identity()
    if not require_kyc_verified(user_id):
        return jsonify({"msg": "Please complete KYC verification before proceeding."}), 403

    data = request.get_json()
    if not data:
        return jsonify({"msg": "Missing JSON payload"}), 400
    
    required_keys = ['borrower_name', 'lender_name', 'loan_amount', 'interest_rate', 
                     'tenure_months', 'start_date', 'governing_law']
    
    # Validate required keys
    for key in required_keys:
        if key not in data:
            return jsonify({"msg": f"Missing required field: {key}"}), 400
            
    # Handle optional fields with defaults if not provided
    data.setdefault('collateral', 'None')
    data.setdefault('penalty_clause', 'None')
            
    try:
        result = generate_loan_agreement(data)
    except Exception as e:
        return jsonify({"msg": f"Error generating document: {str(e)}"}), 500
        
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
                    (result["document_id"], user_id, f"loan_{result['document_id']}.docx", 
                     result["download_url"], "generated")
                )
                conn.commit()
        except Exception as e:
            conn.rollback()
            return jsonify({"msg": f"Database error: {str(e)}"}), 500
        finally:
            release_connection(conn)
    else:
        return jsonify({"msg": "Database connection error"}), 500
        
    return jsonify({
        "document_id": result["document_id"],
        "download_url": result["download_url"],
        "preview_html": result["preview_html"]
    }), 200
