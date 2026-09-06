"""Authenticated endpoint for estimating a scored application's default risk."""

from datetime import date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.db.db import get_connection, release_connection
from app.models.feature_engineering import compute_feature_set, get_financial_profile
from app.models.kyc import get_kyc_record
from app.models.risk_model import predict_default_risk, save_risk_assessment


risk_assessment_bp = Blueprint('risk_assessment', __name__)


def age_from_date_of_birth(date_of_birth) -> int:
    """Calculate the current age from a date/date-string without approximation."""
    if isinstance(date_of_birth, str):
        date_of_birth = date.fromisoformat(date_of_birth)
    today = date.today()
    return today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )


def get_user_credit_score(credit_score_id: str, user_id: str):
    """Fetch only a score belonging to the authenticated user."""
    connection = get_connection()
    if not connection:
        raise RuntimeError('Database connection not available')
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT id, requested_loan_amount, requested_tenure_months,
                       requested_loan_type, score
                FROM credit_scores
                WHERE id = %s AND user_id = %s
                ''',
                (credit_score_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return dict(zip([column[0] for column in cursor.description], row))
    finally:
        release_connection(connection)


@risk_assessment_bp.route('/risk/assess', methods=['POST'])
@jwt_required()
def assess_risk():
    """Estimate and persist default risk for an existing, owned credit score."""
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    credit_score_id = data.get('credit_score_id')
    if not credit_score_id:
        return jsonify({'msg': 'credit_score_id is required'}), 400

    try:
        credit_score = get_user_credit_score(credit_score_id, user_id)
        if not credit_score:
            return jsonify({'msg': 'Credit score not found'}), 404

        profile = get_financial_profile(user_id)
        if not profile:
            return jsonify({'msg': 'Financial profile not found. Please complete it first.'}), 400

        kyc_record = get_kyc_record(user_id)
        if not kyc_record or not kyc_record.get('date_of_birth'):
            return jsonify({'msg': 'Date of birth is required to estimate default risk.'}), 400

        raw_inputs = dict(profile)
        raw_inputs.update({
            'requested_loan_amount': credit_score['requested_loan_amount'],
            'requested_tenure_months': credit_score['requested_tenure_months'],
            'requested_loan_type': credit_score['requested_loan_type'],
            'age': age_from_date_of_birth(kyc_record['date_of_birth']),
        })
        features = compute_feature_set(raw_inputs)
        result = predict_default_risk(features, credit_score['score'])
        saved_assessment = save_risk_assessment(
            user_id=user_id,
            credit_score_id=credit_score['id'],
            default_risk_probability=result['default_risk_probability'],
            risk_tier=result['risk_tier']['label'],
        )
        result['risk_assessment_id'] = str(saved_assessment['id'])
        return jsonify(result), 200
    except ValueError as error:
        return jsonify({'msg': str(error)}), 400
    except Exception as error:
        return jsonify({'msg': f'Risk assessment error: {error}'}), 500
