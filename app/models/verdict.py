"""Auditable business rules for LoanSphere's final loan recommendation."""


def check_kyc_gate(kyc_status):
    """Stop the assessment pipeline until KYC is verified."""
    if kyc_status != 'verified':
        return {
            "gate_passed": False,
            "verdict": "kyc_required",
            "message": "Complete KYC verification before applying for a loan.",
        }
    return {"gate_passed": True}


def determine_verdict(creditworthiness_score, default_risk_probability, foir):
    """Make the sole approved/review/rejected decision from business rules."""
    if creditworthiness_score >= 700 and default_risk_probability < 0.15 and foir < 45:
        return "approved"
    if creditworthiness_score < 500 or default_risk_probability >= 0.35 or foir >= 65:
        return "rejected"
    return "review"


def generate_verdict_reasoning(verdict, creditworthiness_score, default_risk_probability, foir, payment_history_score):
    """Provide concise, user-facing explanations for the business-rule outcome."""
    reasons = []
    if verdict == "approved":
        reasons.append(f"Creditworthiness score of {creditworthiness_score} exceeds the approval threshold of 700.")
        reasons.append(f"Estimated default risk of {default_risk_probability * 100:.1f}% is within acceptable limits.")
        reasons.append(f"FOIR of {foir}% indicates manageable financial obligations.")
    elif verdict == "rejected":
        if creditworthiness_score < 500:
            reasons.append(f"Creditworthiness score of {creditworthiness_score} is below the minimum threshold of 500.")
        if default_risk_probability >= 0.35:
            reasons.append(f"Estimated default risk of {default_risk_probability * 100:.1f}% exceeds the acceptable limit of 35%.")
        if foir >= 65:
            reasons.append(f"FOIR of {foir}% is too high — existing and proposed obligations exceed safe limits.")
    else:
        reasons.append(f"Creditworthiness score of {creditworthiness_score} and estimated risk of {default_risk_probability * 100:.1f}% fall in a borderline range requiring manual review.")
        if foir >= 45:
            reasons.append(f"FOIR of {foir}% is on the higher side and is a contributing factor.")
        if payment_history_score < 70:
            reasons.append("Payment history has some inconsistencies that a human underwriter should review.")
    return reasons


def generate_suggestions(foir, feature_set, requested_loan_amount, requested_tenure_months):
    """Suggest only practical adjustments relevant to the current application."""
    suggestions = []
    if foir >= 45:
        longer_tenure = min(requested_tenure_months + 24, 360)
        suggestions.append(f"Increasing your tenure to {longer_tenure} months would reduce your monthly EMI and improve your FOIR.")
    if feature_set['credit_utilization'] > 50:
        suggestions.append("Reducing your credit card outstanding balances would improve your score.")
    if feature_set['debt_burden_score'] < 50:
        suggestions.append("Paying off or consolidating existing loans would strengthen your application.")
    return suggestions
