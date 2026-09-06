from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.kyc import require_kyc_verified
from app.models.feature_engineering import save_financial_profile, get_financial_profile

financial_profile_bp = Blueprint('financial_profile', __name__)


@financial_profile_bp.route('/financial-profile', methods=['GET'])
@jwt_required()
def get_user_financial_profile():
    """Retrieve the authenticated user's financial profile."""
    user_id = get_jwt_identity()

    if not require_kyc_verified(user_id):
        return jsonify({
            "msg": "KYC verification required before accessing financial profile.",
            "kyc_verified": False
        }), 403

    try:
        profile = get_financial_profile(user_id)
        response = {
            "profile": profile,
            "kyc_verified": True
        }
        if profile:
            response.update(profile)
        return jsonify(response), 200
    except Exception as e:
        return jsonify({"msg": f"Database error: {str(e)}"}), 500


@financial_profile_bp.route('/financial-profile', methods=['POST'])
@jwt_required()
def save_user_financial_profile():
    """Save or update the authenticated user's financial profile."""
    user_id = get_jwt_identity()

    if not require_kyc_verified(user_id):
        return jsonify({
            "msg": "KYC verification required before accessing financial profile.",
            "kyc_verified": False
        }), 403

    data = request.get_json()
    if not data:
        return jsonify({"msg": "Request body is required"}), 400

    monthly_income = data.get('monthly_income')
    employment_type = (data.get('employment_type') or '').strip()
    employment_start_date = data.get('employment_start_date')

    if monthly_income is None or monthly_income == '':
        return jsonify({"msg": "Monthly income is required"}), 400
    if not employment_type:
        return jsonify({"msg": "Employment type is required"}), 400
    if not employment_start_date:
        return jsonify({"msg": "Employment start date is required"}), 400

    try:
        saved_profile = save_financial_profile(user_id, data)
        return jsonify({
            "msg": "Financial profile saved successfully",
            "profile": saved_profile
        }), 200
    except Exception as e:
        return jsonify({"msg": f"Failed to save financial profile: {str(e)}"}), 500
