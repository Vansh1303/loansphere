"""Rule-based matching of applicants to each bank's published criteria."""

from app.data.bank_criteria import BANK_CRITERIA


def get_eligible_banks(loan_type, monthly_income, foir, age, credit_score, employment_type, requested_amount):
    """Return banks whose independent criteria are all met by the applicant."""
    eligible = []
    for bank in BANK_CRITERIA:
        if loan_type not in bank['loan_types']:
            continue
        if monthly_income < bank['min_monthly_income']:
            continue
        if foir > bank['max_foir']:
            continue
        if not (bank['min_age'] <= age <= bank['max_age']):
            continue
        if credit_score < bank['min_credit_score']:
            continue
        if employment_type not in bank['eligible_employment_types']:
            continue
        if requested_amount > bank['max_loan_amount'].get(loan_type, 0):
            continue

        eligible.append({
            "bank_name": bank['bank_name'],
            "max_eligible_amount": bank['max_loan_amount'][loan_type],
            "blank_form_url": bank.get('blank_form_url', '#'),
        })

    return eligible
