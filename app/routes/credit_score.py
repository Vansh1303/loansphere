"""
LoanSphere Creditworthiness Score Routes
API endpoints for calculating and retrieving LoanSphere Creditworthiness Scores.
Gated behind financial profile existing (not KYC).
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.feature_engineering import get_financial_profile, compute_feature_set
from app.models.credit_score import (
    calculate_creditworthiness_score,
    generate_score_explanation,
    save_credit_score,
    get_latest_credit_score,
)

credit_score_bp = Blueprint('credit_score', __name__)

VALID_LOAN_TYPES = {'home', 'personal', 'education', 'car'}


@credit_score_bp.route('/credit-score/calculate', methods=['POST'])
@jwt_required()
def calculate_user_credit_score():
    """
    Calculate and persist a new LoanSphere Creditworthiness Score.
    Requires an existing financial profile.
    """
    user_id = get_jwt_identity()

    data = request.get_json()
    if not data:
        return jsonify({"msg": "Request body is required"}), 400

    # Validate inputs
    requested_loan_amount = data.get('requested_loan_amount')
    requested_tenure_months = data.get('requested_tenure_months')
    requested_loan_type = data.get('requested_loan_type')

    if requested_loan_amount is None:
        return jsonify({"msg": "Requested loan amount is required"}), 400
    try:
        requested_loan_amount = float(requested_loan_amount)
        if requested_loan_amount <= 0:
            return jsonify({"msg": "Requested loan amount must be greater than zero"}), 400
    except (ValueError, TypeError):
        return jsonify({"msg": "Invalid requested loan amount"}), 400

    if requested_tenure_months is None:
        return jsonify({"msg": "Requested tenure is required"}), 400
    try:
        requested_tenure_months = int(requested_tenure_months)
        if requested_tenure_months <= 0:
            return jsonify({"msg": "Requested tenure must be greater than zero"}), 400
    except (ValueError, TypeError):
        return jsonify({"msg": "Invalid requested tenure"}), 400

    if not requested_loan_type or not str(requested_loan_type).strip():
        return jsonify({"msg": "Requested loan type is required"}), 400

    loan_type_clean = str(requested_loan_type).strip().lower()
    if loan_type_clean not in VALID_LOAN_TYPES:
        return jsonify({
            "msg": f"Invalid loan type '{requested_loan_type}'. Valid types: {', '.join(sorted(VALID_LOAN_TYPES))}"
        }), 400

    # Fetch financial profile
    try:
        profile = get_financial_profile(user_id)
        if not profile:
            return jsonify({
                "msg": "Financial profile not found. Please complete your financial profile first."
            }), 400

        # Merge loan parameters with financial profile
        raw_inputs = dict(profile)
        raw_inputs['requested_loan_amount'] = requested_loan_amount
        raw_inputs['requested_tenure_months'] = requested_tenure_months
        raw_inputs['requested_loan_type'] = loan_type_clean

        # Reuse compute_feature_set without recalculating independently
        features = compute_feature_set(raw_inputs)

        # Calculate score and explanation
        score_result = calculate_creditworthiness_score(features)
        explanation = generate_score_explanation(score_result['component_breakdown'])
        score_result['explanation'] = explanation

        # Persist to database
        save_credit_score(
            user_id=user_id,
            requested_loan_amount=requested_loan_amount,
            requested_tenure_months=requested_tenure_months,
            requested_loan_type=loan_type_clean,
            score=score_result['score'],
            band=score_result['band']['label'],
            component_breakdown=score_result['component_breakdown'],
            explanation=explanation,
        )

        return jsonify({
            "score": score_result['score'],
            "band": score_result['band'],
            "component_breakdown": score_result['component_breakdown'],
            "explanation": explanation,
        }), 200

    except Exception as e:
        return jsonify({"msg": f"Calculation error: {str(e)}"}), 500


@credit_score_bp.route('/credit-score/latest', methods=['GET'])
@jwt_required()
def get_latest_user_credit_score():
    """Retrieve the most recent credit score for the authenticated user."""
    user_id = get_jwt_identity()
    try:
        latest = get_latest_credit_score(user_id)
        if not latest:
            return jsonify({"score": None}), 200
        return jsonify(latest), 200
    except Exception as e:
        return jsonify({"msg": f"Database error: {str(e)}"}), 500
