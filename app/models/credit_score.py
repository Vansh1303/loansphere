"""
LoanSphere Creditworthiness Score Model
A project-specific, explainable 0-900 scoring system inspired by industry
FOIR standards. Deterministic and rule-based.
"""

import json
from typing import Dict, Any, List, Optional
from app.db.db import get_connection, release_connection
from app.models.feature_engineering import compute_feature_set


def score_foir(foir: float) -> float:
    """Piecewise linear: lower FOIR = higher score."""
    if foir <= 20:
        return 100.0
    elif foir >= 70:
        return 0.0
    else:
        return round(100.0 - ((foir - 20.0) / 50.0) * 100.0, 2)


def score_utilization(utilization_pct: float) -> float:
    """Lower utilization = higher score. 30% is the healthy threshold."""
    if utilization_pct <= 10:
        return 100.0
    elif utilization_pct >= 90:
        return 0.0
    else:
        return round(100.0 - ((utilization_pct - 10.0) / 80.0) * 100.0, 2)


def get_score_band(score: int) -> Dict[str, str]:
    """Return band label and theme color token for a given score (300-900)."""
    if score >= 750:
        return {"label": "Excellent", "color": "success"}
    elif score >= 650:
        return {"label": "Good", "color": "success"}
    elif score >= 550:
        return {"label": "Fair", "color": "warning"}
    elif score >= 400:
        return {"label": "Poor", "color": "danger"}
    else:
        return {"label": "Very poor", "color": "danger"}


def calculate_creditworthiness_score(feature_set: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate creditworthiness score from features computed by feature_engineering.py.
    Formula: weighted sum of 6 components (0-100), scaled to 300-900 range.
    """
    foir_score = score_foir(feature_set['foir'])
    utilization_score = score_utilization(feature_set['credit_utilization'])
    payment_score = float(feature_set['payment_history_score'])
    employment_score = float(feature_set['employment_stability_score'])
    debt_score = float(feature_set['debt_burden_score'])
    inquiry_score = float(feature_set['inquiry_pressure_score'])

    weighted_sum = (
        foir_score * 0.30 +
        payment_score * 0.25 +
        utilization_score * 0.15 +
        employment_score * 0.15 +
        debt_score * 0.10 +
        inquiry_score * 0.05
    )

    # Scale 0-100 weighted sum to 300-900 range
    final_score = round(300 + (weighted_sum / 100.0) * 600)

    band = get_score_band(final_score)

    return {
        "score": final_score,
        "band": band,
        "component_breakdown": {
            "foir": {"raw_value": feature_set['foir'], "component_score": foir_score, "weight": 30},
            "payment_history": {"raw_value": feature_set['payment_history_score'], "component_score": payment_score, "weight": 25},
            "credit_utilization": {"raw_value": feature_set['credit_utilization'], "component_score": utilization_score, "weight": 15},
            "employment_stability": {"raw_value": feature_set['employment_stability_score'], "component_score": employment_score, "weight": 15},
            "debt_burden": {"raw_value": feature_set['debt_burden_score'], "component_score": debt_score, "weight": 10},
            "inquiry_pressure": {"raw_value": feature_set['inquiry_pressure_score'], "component_score": inquiry_score, "weight": 5},
        }
    }


def generate_score_explanation(component_breakdown: Dict[str, Any]) -> List[str]:
    """Generate human-readable explanations for why the user received this score."""
    explanations: List[str] = []

    foir = component_breakdown['foir']['raw_value']
    if foir < 30:
        explanations.append(f"Your FOIR of {foir}% is healthy and well within safe lending limits.")
    elif foir < 50:
        explanations.append(f"Your FOIR of {foir}% is moderate — reducing existing obligations would improve your score.")
    else:
        explanations.append(f"Your FOIR of {foir}% is high, which significantly lowers your score.")

    payment = component_breakdown['payment_history']['raw_value']
    if payment >= 90:
        explanations.append("Your payment history shows strong reliability with minimal missed payments.")
    elif payment >= 60:
        explanations.append("Your payment history has some missed payments affecting your score.")
    else:
        explanations.append("Your payment history has significant issues — defaults or settlements are heavily impacting your score.")

    employment = component_breakdown['employment_stability']['raw_value']
    if employment >= 70:
        explanations.append("Your employment stability is a strong positive factor.")
    else:
        explanations.append("A longer employment history would improve your stability score.")

    utilization = component_breakdown['credit_utilization']['raw_value']
    if utilization < 30:
        explanations.append(f"Your credit utilization of {utilization}% is in the ideal range.")
    else:
        explanations.append(f"Your credit utilization of {utilization}% is on the higher side — keeping it under 30% is recommended.")

    return explanations


def save_credit_score(
    user_id: str,
    requested_loan_amount: float,
    requested_tenure_months: int,
    requested_loan_type: str,
    score: int,
    band: str,
    component_breakdown: Dict[str, Any],
    explanation: List[str]
) -> Dict[str, Any]:
    """Persist a newly calculated credit score entry to the database."""
    conn = get_connection()
    if not conn:
        raise RuntimeError("Database connection not available")

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO credit_scores (
                    user_id, requested_loan_amount, requested_tenure_months, requested_loan_type,
                    score, band, component_breakdown, explanation, computed_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s::jsonb, %s::jsonb, NOW()
                )
                RETURNING id, user_id, requested_loan_amount, requested_tenure_months, requested_loan_type,
                          score, band, component_breakdown, explanation, computed_at
                """,
                (
                    user_id,
                    float(requested_loan_amount),
                    int(requested_tenure_months),
                    str(requested_loan_type).strip().lower(),
                    int(score),
                    str(band),
                    json.dumps(component_breakdown),
                    json.dumps(explanation)
                )
            )
            row = cursor.fetchone()
            colnames = [desc[0] for desc in cursor.description]
            result = dict(zip(colnames, row))
            conn.commit()

            if result.get('computed_at'):
                result['computed_at'] = result['computed_at'].isoformat()
            if isinstance(result.get('component_breakdown'), str):
                result['component_breakdown'] = json.loads(result['component_breakdown'])
            if isinstance(result.get('explanation'), str):
                result['explanation'] = json.loads(result['explanation'])

            result['band'] = get_score_band(result['score'])
            return result
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        release_connection(conn)


def get_latest_credit_score(user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the most recently computed credit score for a user."""
    conn = get_connection()
    if not conn:
        raise RuntimeError("Database connection not available")

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id, requested_loan_amount, requested_tenure_months, requested_loan_type,
                       score, band, component_breakdown, explanation, computed_at
                FROM credit_scores
                WHERE user_id = %s
                ORDER BY computed_at DESC
                LIMIT 1
                """,
                (user_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            colnames = [desc[0] for desc in cursor.description]
            result = dict(zip(colnames, row))

            if result.get('computed_at'):
                result['computed_at'] = result['computed_at'].isoformat()
            if isinstance(result.get('component_breakdown'), str):
                result['component_breakdown'] = json.loads(result['component_breakdown'])
            if isinstance(result.get('explanation'), str):
                result['explanation'] = json.loads(result['explanation'])

            result['band'] = get_score_band(result['score'])
            return result
    finally:
        release_connection(conn)
