"""Authenticated endpoint for LoanSphere's final loan recommendation."""

import json
from datetime import date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.db.db import get_connection, release_connection
from app.models.bank_eligibility import get_eligible_banks
from app.models.credit_score import calculate_creditworthiness_score, generate_score_explanation, save_credit_score
from app.models.feature_engineering import compute_feature_set, get_financial_profile
from app.models.kyc import get_kyc_record
from app.models.risk_model import predict_default_risk, save_risk_assessment
from app.models.verdict import (
    check_kyc_gate,
    determine_verdict,
    generate_suggestions,
    generate_verdict_reasoning,
)


verdict_bp = Blueprint('verdict', __name__)
VALID_LOAN_TYPES = {'home', 'personal', 'education', 'car'}


def age_from_date_of_birth(date_of_birth):
    """Return a precise age from a KYC date of birth."""
    if isinstance(date_of_birth, str):
        date_of_birth = date.fromisoformat(date_of_birth)
    today = date.today()
    return today.year - date_of_birth.year - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))


def save_verdict(user_id, credit_score_id, risk_assessment_id, verdict, reasoning, suggestions,
                 eligible_banks, requested_amount, requested_tenure, requested_loan_type):
    """Persist the complete, auditable assessment outcome. Returns the verdict id."""
    connection = get_connection()
    if not connection:
        raise RuntimeError('Database connection not available')
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                INSERT INTO verdicts (
                    user_id, credit_score_id, risk_assessment_id, verdict, reasoning,
                    suggested_adjustments, eligible_banks, requested_loan_amount,
                    requested_tenure_months, requested_loan_type
                ) VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s)
                RETURNING id
                ''',
                (
                    user_id, credit_score_id, risk_assessment_id, verdict,
                    json.dumps(reasoning), json.dumps(suggestions), json.dumps(eligible_banks),
                    requested_amount, requested_tenure, requested_loan_type,
                ),
            )
            verdict_id = cursor.fetchone()[0]
        connection.commit()
        return str(verdict_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        release_connection(connection)


@verdict_bp.route('/verdict/generate', methods=['POST'])
@jwt_required()
def generate_verdict():
    """Generate score and risk signals, then make a rules-only loan verdict."""
    user_id = get_jwt_identity()

    # 1. KYC gate: never calculate any downstream signal until this passes.
    kyc_record = get_kyc_record(user_id)
    kyc_gate = check_kyc_gate(kyc_record.get('kyc_status') if kyc_record else None)
    if not kyc_gate['gate_passed']:
        return jsonify({
            'verdict': kyc_gate['verdict'],
            'message': kyc_gate['message'],
        }), 403

    try:
        # 2. Financial profile must exist before an assessment can be built.
        profile = get_financial_profile(user_id)
        if not profile:
            return jsonify({
                'msg': 'Financial profile not found. Please complete your financial profile first.',
            }), 400

        data = request.get_json(silent=True) or {}
        requested_amount = data.get('requested_loan_amount')
        requested_tenure = data.get('requested_tenure_months')
        requested_loan_type = data.get('requested_loan_type')

        if requested_amount is None:
            return jsonify({'msg': 'Requested loan amount is required'}), 400
        try:
            requested_amount = float(requested_amount)
            if requested_amount <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({'msg': 'Requested loan amount must be greater than zero'}), 400

        if requested_tenure is None:
            return jsonify({'msg': 'Requested tenure is required'}), 400
        try:
            requested_tenure = int(requested_tenure)
            if requested_tenure <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({'msg': 'Requested tenure must be greater than zero'}), 400

        loan_type = str(requested_loan_type or '').strip().lower()
        if loan_type not in VALID_LOAN_TYPES:
            return jsonify({'msg': 'Requested loan type must be home, personal, education, or car'}), 400
        if not kyc_record.get('date_of_birth'):
            return jsonify({'msg': 'Date of birth is required to estimate default risk.'}), 400

        # 3. Construct the shared features once for both score and risk models.
        raw_inputs = dict(profile)
        raw_inputs.update({
            'requested_loan_amount': requested_amount,
            'requested_tenure_months': requested_tenure,
            'requested_loan_type': loan_type,
            'age': age_from_date_of_birth(kyc_record['date_of_birth']),
        })
        features = compute_feature_set(raw_inputs)

        # 4. Compute and persist the creditworthiness score.
        score_result = calculate_creditworthiness_score(features)
        score_explanation = generate_score_explanation(score_result['component_breakdown'])
        saved_score = save_credit_score(
            user_id=user_id,
            requested_loan_amount=requested_amount,
            requested_tenure_months=requested_tenure,
            requested_loan_type=loan_type,
            score=score_result['score'],
            band=score_result['band']['label'],
            component_breakdown=score_result['component_breakdown'],
            explanation=score_explanation,
        )

        # 5. ML supplies only a probability and tier; it never decides the verdict.
        risk_result = predict_default_risk(features, score_result['score'])
        saved_risk = save_risk_assessment(
            user_id=user_id,
            credit_score_id=saved_score['id'],
            default_risk_probability=risk_result['default_risk_probability'],
            risk_tier=risk_result['risk_tier']['label'],
        )

        # 6. The Verdict Engine's transparent business rules make the decision.
        verdict = determine_verdict(
            score_result['score'], risk_result['default_risk_probability'], features['foir'],
        )
        reasoning = generate_verdict_reasoning(
            verdict, score_result['score'], risk_result['default_risk_probability'],
            features['foir'], features['payment_history_score'],
        )
        suggestions = generate_suggestions(features['foir'], features, requested_amount, requested_tenure)

        # 7. Only positive or review outcomes receive bank recommendations.
        eligible_banks = []
        if verdict in {'approved', 'review'}:
            eligible_banks = get_eligible_banks(
                loan_type=loan_type,
                monthly_income=features['monthly_income'],
                foir=features['foir'],
                age=features['age'],
                credit_score=score_result['score'],
                employment_type=features['employment_type'],
                requested_amount=requested_amount,
            )

        # 8. Persist the final outcome and return the complete decision context.
        verdict_id = save_verdict(
            user_id, saved_score['id'], saved_risk['id'], verdict, reasoning, suggestions,
            eligible_banks, requested_amount, requested_tenure, loan_type,
        )
        return jsonify({
            'verdict_id': verdict_id,
            'verdict': verdict,
            'creditworthiness_score': score_result['score'],
            'score_band': score_result['band'],
            'estimated_default_risk_probability': risk_result['default_risk_probability'],
            'risk_tier': risk_result['risk_tier'],
            'foir': features['foir'],
            'reasoning': reasoning,
            'suggested_adjustments': suggestions,
            'eligible_banks': eligible_banks,
        }), 200
    except ValueError as error:
        return jsonify({'msg': str(error)}), 400
    except Exception as error:
        return jsonify({'msg': f'Verdict generation error: {error}'}), 500
