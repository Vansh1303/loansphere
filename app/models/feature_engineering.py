"""
Feature Engineering Module for LoanSphere
Shared backend library for computing derived financial metrics identically
across the Credit Score and ML Risk modules.
"""

from datetime import date, datetime
from typing import Dict, Any, Optional
from app.db.db import get_connection, release_connection

DEFAULT_RATES: Dict[str, float] = {
    "home": 8.5,
    "personal": 12.5,
    "education": 9.5,
    "car": 10.5,
}


def get_default_rate(loan_type: str) -> float:
    """Return default annual interest rate percentage for a given loan type."""
    if not loan_type:
        return 10.5
    return DEFAULT_RATES.get(str(loan_type).strip().lower(), 10.5)


def calculate_emi(principal: float, annual_rate_pct: float, tenure_months: int) -> float:
    """Calculate Equated Monthly Installment (EMI)."""
    if tenure_months <= 0:
        return 0.0
    r = (annual_rate_pct / 12.0) / 100.0
    if r == 0:
        return round(float(principal) / float(tenure_months), 2)
    emi = float(principal) * r * ((1.0 + r) ** tenure_months) / (((1.0 + r) ** tenure_months) - 1.0)
    return round(emi, 2)


def calculate_foir(existing_emis_monthly: float, new_emi: float, monthly_income: float) -> float:
    """Calculate Fixed Obligation to Income Ratio (FOIR) percentage capped at 100.0."""
    if monthly_income <= 0:
        return 100.0
    foir = ((float(existing_emis_monthly) + float(new_emi)) / float(monthly_income)) * 100.0
    return round(min(foir, 100.0), 2)


def calculate_utilization(credit_card_outstanding_total: float, credit_card_limit_total: float) -> float:
    """Calculate revolving credit utilization percentage."""
    if credit_card_limit_total <= 0:
        return 0.0
    return round((float(credit_card_outstanding_total) / float(credit_card_limit_total)) * 100.0, 2)


def calculate_employment_stability(employment_start_date, employment_type: str) -> float:
    """
    Continuous curve: stability rises with years, plateaus after 7 years.
    Applies adjustment based on employment type.
    """
    if isinstance(employment_start_date, str):
        employment_start_date = date.fromisoformat(employment_start_date)
    elif isinstance(employment_start_date, datetime):
        employment_start_date = employment_start_date.date()

    years = max(0.0, (date.today() - employment_start_date).days / 365.25)

    # Continuous curve: stability rises with years, plateaus after 7 years
    base_score = min(100.0, (years / 7.0) * 100.0)

    # Small supporting adjustment for employment type stability
    type_adjustment = {
        "govt_salaried": 5,
        "private_salaried": 0,
        "self_employed": -5,
        "business": -8
    }.get(employment_type, 0)

    return round(max(0.0, min(100.0, base_score + type_adjustment)), 2)


def calculate_debt_burden(existing_loans_count: int, existing_emis_monthly: float, monthly_income: float) -> float:
    """Calculate debt burden score (0-100)."""
    loan_count_penalty = min(int(existing_loans_count) * 8, 40)
    emi_ratio = (float(existing_emis_monthly) / float(monthly_income) * 100.0) if monthly_income > 0 else 100.0
    score = 100.0 - loan_count_penalty - min(emi_ratio, 60.0)
    return round(max(0.0, score), 2)


def calculate_payment_history_score(
    on_time_payments_pct: float,
    missed_payments_count_12m: int,
    defaults_count: int,
    settlements_count: int
) -> float:
    """Calculate payment history score (0-100)."""
    score = float(on_time_payments_pct)
    score -= int(missed_payments_count_12m) * 5
    score -= int(defaults_count) * 20
    score -= int(settlements_count) * 15
    return round(max(0.0, min(100.0, score)), 2)


def calculate_inquiry_pressure(hard_inquiries_6m: int) -> float:
    """Calculate inquiry pressure score (0-100). More inquiries = higher pressure = worse score."""
    score = 100.0 - (int(hard_inquiries_6m) * 15)
    return round(max(0.0, min(100.0, score)), 2)


def calculate_loan_to_income_ratio(requested_loan_amount: float, monthly_income: float) -> float:
    """Calculate loan to annual income ratio."""
    annual_income = float(monthly_income) * 12.0
    if annual_income <= 0:
        return 99.0
    return round(float(requested_loan_amount) / annual_income, 2)


def compute_feature_set(raw_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Takes raw_inputs dict matching Section 2 fields.
    Returns a complete feature dict used by both scoring systems.
    """
    loan_type = raw_inputs['requested_loan_type']
    annual_rate_pct = get_default_rate(loan_type)

    new_emi = calculate_emi(
        float(raw_inputs['requested_loan_amount']),
        annual_rate_pct,
        int(raw_inputs['requested_tenure_months'])
    )

    features = {
        "foir": calculate_foir(
            float(raw_inputs.get('existing_emis_monthly', 0.0)),
            new_emi,
            float(raw_inputs['monthly_income'])
        ),
        "credit_utilization": calculate_utilization(
            float(raw_inputs.get('credit_card_outstanding_total', 0.0)),
            float(raw_inputs.get('credit_card_limit_total', 0.0))
        ),
        "employment_stability_score": calculate_employment_stability(
            raw_inputs['employment_start_date'],
            raw_inputs['employment_type']
        ),
        "debt_burden_score": calculate_debt_burden(
            int(raw_inputs.get('existing_loans_count', 0)),
            float(raw_inputs.get('existing_emis_monthly', 0.0)),
            float(raw_inputs['monthly_income'])
        ),
        "payment_history_score": calculate_payment_history_score(
            float(raw_inputs.get('on_time_payments_pct', 100.0)),
            int(raw_inputs.get('missed_payments_count_12m', 0)),
            int(raw_inputs.get('defaults_count', 0)),
            int(raw_inputs.get('settlements_count', 0))
        ),
        "inquiry_pressure_score": calculate_inquiry_pressure(
            int(raw_inputs.get('hard_inquiries_6m', 0))
        ),
        "loan_to_income_ratio": calculate_loan_to_income_ratio(
            float(raw_inputs['requested_loan_amount']),
            float(raw_inputs['monthly_income'])
        ),
        "new_emi": new_emi,
        "credit_history_length_years": float(raw_inputs.get('credit_history_length_years', 0.0)),
        "age": int(raw_inputs['age']) if raw_inputs.get('age') is not None else None,
        "employment_type": raw_inputs['employment_type'],
        "requested_loan_type": raw_inputs['requested_loan_type'],
    }
    return features


def save_financial_profile(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Persist or update raw financial profile in financial_profiles table."""
    conn = get_connection()
    if not conn:
        raise RuntimeError("Database connection not available")

    monthly_income = float(data.get('monthly_income', 0.0))
    employment_type = str(data.get('employment_type', '')).strip()
    employment_start_date = data.get('employment_start_date')
    if isinstance(employment_start_date, datetime):
        employment_start_date = employment_start_date.date()
    elif isinstance(employment_start_date, str):
        employment_start_date = date.fromisoformat(employment_start_date.strip())

    existing_emis_monthly = float(data.get('existing_emis_monthly') or 0.0)
    existing_loans_count = int(data.get('existing_loans_count') or 0)
    credit_card_limit_total = float(data.get('credit_card_limit_total') or 0.0)
    credit_card_outstanding_total = float(data.get('credit_card_outstanding_total') or 0.0)
    on_time_payments_pct = float(data.get('on_time_payments_pct') if data.get('on_time_payments_pct') is not None else 100.0)
    missed_payments_count_12m = int(data.get('missed_payments_count_12m') or 0)
    defaults_count = int(data.get('defaults_count') or 0)
    settlements_count = int(data.get('settlements_count') or 0)
    credit_history_length_years = float(data.get('credit_history_length_years') or 0.0)
    hard_inquiries_6m = int(data.get('hard_inquiries_6m') or 0)

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO financial_profiles (
                    user_id, monthly_income, employment_type, employment_start_date,
                    existing_emis_monthly, existing_loans_count,
                    credit_card_limit_total, credit_card_outstanding_total,
                    on_time_payments_pct, missed_payments_count_12m,
                    defaults_count, settlements_count,
                    credit_history_length_years, hard_inquiries_6m,
                    updated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    NOW()
                )
                ON CONFLICT (user_id) DO UPDATE SET
                    monthly_income = EXCLUDED.monthly_income,
                    employment_type = EXCLUDED.employment_type,
                    employment_start_date = EXCLUDED.employment_start_date,
                    existing_emis_monthly = EXCLUDED.existing_emis_monthly,
                    existing_loans_count = EXCLUDED.existing_loans_count,
                    credit_card_limit_total = EXCLUDED.credit_card_limit_total,
                    credit_card_outstanding_total = EXCLUDED.credit_card_outstanding_total,
                    on_time_payments_pct = EXCLUDED.on_time_payments_pct,
                    missed_payments_count_12m = EXCLUDED.missed_payments_count_12m,
                    defaults_count = EXCLUDED.defaults_count,
                    settlements_count = EXCLUDED.settlements_count,
                    credit_history_length_years = EXCLUDED.credit_history_length_years,
                    hard_inquiries_6m = EXCLUDED.hard_inquiries_6m,
                    updated_at = NOW()
                RETURNING id, user_id, monthly_income, employment_type, employment_start_date,
                          existing_emis_monthly, existing_loans_count,
                          credit_card_limit_total, credit_card_outstanding_total,
                          on_time_payments_pct, missed_payments_count_12m,
                          defaults_count, settlements_count,
                          credit_history_length_years, hard_inquiries_6m,
                          created_at, updated_at
                """,
                (
                    user_id, monthly_income, employment_type, employment_start_date,
                    existing_emis_monthly, existing_loans_count,
                    credit_card_limit_total, credit_card_outstanding_total,
                    on_time_payments_pct, missed_payments_count_12m,
                    defaults_count, settlements_count,
                    credit_history_length_years, hard_inquiries_6m
                )
            )
            row = cursor.fetchone()
            colnames = [desc[0] for desc in cursor.description]
            result = dict(zip(colnames, row))
            conn.commit()

            # Format dates/timestamps for JSON serialization
            if result.get('employment_start_date'):
                result['employment_start_date'] = result['employment_start_date'].isoformat()
            if result.get('created_at'):
                result['created_at'] = result['created_at'].isoformat()
            if result.get('updated_at'):
                result['updated_at'] = result['updated_at'].isoformat()
            return result
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        release_connection(conn)


def get_financial_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve raw financial profile for a user."""
    conn = get_connection()
    if not conn:
        raise RuntimeError("Database connection not available")

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, user_id, monthly_income, employment_type, employment_start_date,
                       existing_emis_monthly, existing_loans_count,
                       credit_card_limit_total, credit_card_outstanding_total,
                       on_time_payments_pct, missed_payments_count_12m,
                       defaults_count, settlements_count,
                       credit_history_length_years, hard_inquiries_6m,
                       created_at, updated_at
                FROM financial_profiles
                WHERE user_id = %s
                """,
                (user_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            colnames = [desc[0] for desc in cursor.description]
            result = dict(zip(colnames, row))

            if result.get('employment_start_date'):
                result['employment_start_date'] = result['employment_start_date'].isoformat()
            if result.get('created_at'):
                result['created_at'] = result['created_at'].isoformat()
            if result.get('updated_at'):
                result['updated_at'] = result['updated_at'].isoformat()
            return result
    finally:
        release_connection(conn)
