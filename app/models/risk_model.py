"""ML default-risk model loading, inference, and persistence helpers."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import pandas as pd
from sklearn.ensemble import VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from app.db.db import get_connection, release_connection


MODEL_DIR = Path(__file__).resolve().parent
MODEL_PATH = MODEL_DIR / 'risk_model.pkl'
COLUMNS_PATH = MODEL_DIR / 'risk_model_columns.pkl'

_model = None
_columns = None
logger = logging.getLogger(__name__)


def build_model() -> Pipeline:
    """Build the specified soft-voting Logistic Regression / Decision Tree ensemble."""
    logistic_regression = LogisticRegression(max_iter=1000, class_weight='balanced')
    decision_tree = DecisionTreeClassifier(
        max_depth=5,
        min_samples_leaf=20,
        class_weight='balanced',
        random_state=42,
    )
    ensemble = VotingClassifier(
        estimators=[('logistic', logistic_regression), ('tree', decision_tree)],
        voting='soft',
    )
    return Pipeline([('scaler', StandardScaler()), ('ensemble', ensemble)])


def load_risk_model() -> Tuple[Any, List[str]]:
    """Load trained artifacts on first use, avoiding work during Flask startup."""
    global _model, _columns
    if _model is None or _columns is None:
        if not MODEL_PATH.exists() or not COLUMNS_PATH.exists():
            raise RuntimeError(
                'Risk-model artifacts are missing. Run scripts/generate_synthetic_data.py '
                'and scripts/train_risk_model.py.'
            )
        _model = joblib.load(MODEL_PATH)
        _columns = joblib.load(COLUMNS_PATH)
    return _model, _columns


def get_risk_tier(probability: float) -> Dict[str, str]:
    """Map a default probability to its presentation tier."""
    if probability < 0.10:
        return {'label': 'Low risk', 'color': 'success'}
    if probability < 0.25:
        return {'label': 'Moderate risk', 'color': 'warning'}
    return {'label': 'High risk', 'color': 'danger'}


def predict_default_risk(feature_set: Dict[str, Any], creditworthiness_score: int) -> Dict[str, Any]:
    """Return a trained-model estimate of default risk, never an approval verdict."""
    if feature_set.get('age') is None:
        raise ValueError('Age is required to estimate default risk.')

    model, columns = load_risk_model()
    row = {
        'age': int(feature_set['age']),
        'monthly_income': float(feature_set.get('monthly_income', 0)),
        'foir': float(feature_set['foir']),
        'credit_utilization': float(feature_set['credit_utilization']),
        'payment_history_score': float(feature_set['payment_history_score']),
        'employment_stability_score': float(feature_set['employment_stability_score']),
        'debt_burden_score': float(feature_set['debt_burden_score']),
        'inquiry_pressure_score': float(feature_set['inquiry_pressure_score']),
        'loan_to_income_ratio': float(feature_set['loan_to_income_ratio']),
        'creditworthiness_score': int(creditworthiness_score),
    }
    for column in columns:
        if column.startswith('employment_type_'):
            row[column] = int(column == f"employment_type_{feature_set['employment_type']}")
        elif column.startswith('requested_loan_type_'):
            row[column] = int(column == f"requested_loan_type_{feature_set['requested_loan_type']}")

    input_frame = pd.DataFrame([row]).reindex(columns=columns, fill_value=0)
    feature_dict = input_frame.to_dict(orient='records')[0]
    logger.debug('Risk model input feature dict: %s', feature_dict)
    print(f'[DEBUG] Risk model input features: {feature_dict}')
    probability = float(model.predict_proba(input_frame)[0, 1])
    return {
        'default_risk_probability': round(probability, 4),
        'risk_percentage': round(probability * 100, 1),
        'risk_tier': get_risk_tier(probability),
    }


def save_risk_assessment(
    user_id: str,
    credit_score_id: str,
    default_risk_probability: float,
    risk_tier: str,
) -> Dict[str, Any]:
    """Persist an auditable risk assessment linked to the scored application."""
    connection = get_connection()
    if not connection:
        raise RuntimeError('Database connection not available')

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                INSERT INTO risk_assessments (
                    user_id, credit_score_id, default_risk_probability, risk_tier
                ) VALUES (%s, %s, %s, %s)
                RETURNING id, user_id, credit_score_id, default_risk_probability,
                          risk_tier, model_version, computed_at
                ''',
                (user_id, credit_score_id, default_risk_probability, risk_tier),
            )
            row = cursor.fetchone()
            result = dict(zip([column[0] for column in cursor.description], row))
            connection.commit()
            if result.get('computed_at'):
                result['computed_at'] = result['computed_at'].isoformat()
            return result
    except Exception:
        connection.rollback()
        raise
    finally:
        release_connection(connection)
