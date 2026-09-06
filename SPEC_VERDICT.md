# LoanSphere — Verdict Engine + Bank Eligibility Engine Spec

Follow SPEC_DESIGN_SYSTEM.md for all styling.
Depends on: SPEC_KYC.md, SPEC_FEATURES.md, SPEC_CREDIT_SCORE.md, SPEC_ML_RISK.md.
This is the final module in the assessment pipeline — everything before
this point produces signals; this module makes the decision.

---

## 1. Why this module exists

This is where the four separate signals — KYC status, creditworthiness
score, ML default risk, and hard business rules — combine into one final,
explainable recommendation. It is deliberately kept separate from the ML
model: the ML model only ever outputs a risk probability, never a verdict.
Business rules and thresholds belong here, in code that's easy for anyone
(including your panel) to read and audit — not buried inside a trained model.

**Full pipeline recap:**
```
KYC status (gate) + Creditworthiness Score (0-900) + Default Risk Probability
    → Verdict Engine → Approved / Review / Rejected + reasoning
    → Bank Eligibility Engine → list of banks the user qualifies for
```

---

## 2. Verdict Decision Logic

### Step 1 — KYC gate (checked first, short-circuits everything else)

```python
def check_kyc_gate(kyc_status):
    if kyc_status != 'verified':
        return {
            "gate_passed": False,
            "verdict": "kyc_required",
            "message": "Complete KYC verification before applying for a loan."
        }
    return {"gate_passed": True}
```

If KYC gate fails, the engine stops here — do not compute a verdict at all.
The frontend should never even show a verdict page without KYC verified;
this is a backend safety check in case the frontend gate is bypassed.

### Step 2 — Combine score and risk into a verdict

```python
def determine_verdict(creditworthiness_score, default_risk_probability, foir):
    """
    Combines all three signals. None of these thresholds are arbitrary —
    they mirror RBI's general FOIR guidance (50% caution threshold) and a
    2-sigma-style split on the synthetic model's risk distribution.
    """
    if creditworthiness_score >= 700 and default_risk_probability < 0.15 and foir < 45:
        verdict = "approved"
    elif creditworthiness_score < 500 or default_risk_probability >= 0.35 or foir >= 65:
        verdict = "rejected"
    else:
        verdict = "review"

    return verdict
```

### Step 3 — Confidence framing (NOT the same as ML confidence)

Do not present a single "confidence %" number to the user. Instead present
the two underlying numbers plainly:

```python
def build_verdict_response(verdict, creditworthiness_score, band, default_risk_probability, risk_tier, foir, reasoning, suggestions):
    return {
        "verdict": verdict,  # approved | review | rejected
        "creditworthiness_score": creditworthiness_score,
        "score_band": band,
        "estimated_default_risk_probability": default_risk_probability,
        "risk_tier": risk_tier,
        "foir": foir,
        "reasoning": reasoning,
        "suggested_adjustments": suggestions
    }
```

### Step 4 — Reasoning generator

```python
def generate_verdict_reasoning(verdict, creditworthiness_score, default_risk_probability, foir, payment_history_score):
    reasons = []

    if verdict == "approved":
        reasons.append(f"Creditworthiness score of {creditworthiness_score} exceeds the approval threshold of 700.")
        reasons.append(f"Estimated default risk of {default_risk_probability*100:.1f}% is within acceptable limits.")
        reasons.append(f"FOIR of {foir}% indicates manageable financial obligations.")
    elif verdict == "rejected":
        if creditworthiness_score < 500:
            reasons.append(f"Creditworthiness score of {creditworthiness_score} is below the minimum threshold of 500.")
        if default_risk_probability >= 0.35:
            reasons.append(f"Estimated default risk of {default_risk_probability*100:.1f}% exceeds the acceptable limit of 35%.")
        if foir >= 65:
            reasons.append(f"FOIR of {foir}% is too high — existing and proposed obligations exceed safe limits.")
    else:  # review
        reasons.append(f"Creditworthiness score of {creditworthiness_score} and estimated risk of {default_risk_probability*100:.1f}% fall in a borderline range requiring manual review.")
        if foir >= 45:
            reasons.append(f"FOIR of {foir}% is on the higher side and is a contributing factor.")
        if payment_history_score < 70:
            reasons.append("Payment history has some inconsistencies that a human underwriter should review.")

    return reasons

def generate_suggestions(foir, feature_set, requested_loan_amount, requested_tenure_months):
    suggestions = []
    if foir >= 45:
        # Suggest a longer tenure to reduce EMI and thus FOIR
        longer_tenure = min(requested_tenure_months + 24, 360)
        suggestions.append(f"Increasing your tenure to {longer_tenure} months would reduce your monthly EMI and improve your FOIR.")
    if feature_set['credit_utilization'] > 50:
        suggestions.append("Reducing your credit card outstanding balances would improve your score.")
    if feature_set['debt_burden_score'] < 50:
        suggestions.append("Paying off or consolidating existing loans would strengthen your application.")
    return suggestions
```

---

## 3. Bank Eligibility Engine

This is a **separate, rule-based layer** that runs only after a verdict of
"approved" or "review" — rejected applicants see no bank list. It filters a
static table of bank criteria against the applicant's profile.

### `app/data/bank_criteria.py`

```python
BANK_CRITERIA = [
    {
        "bank_name": "SBI",
        "loan_types": ["home", "personal", "education", "car"],
        "min_monthly_income": 25000,
        "max_foir": 50,
        "min_age": 21,
        "max_age": 70,
        "max_loan_amount": {"home": 7500000, "personal": 2000000, "education": 1500000, "car": 1000000},
        "min_credit_score": 650,
        "eligible_employment_types": ["govt_salaried", "private_salaried", "self_employed", "business"]
    },
    {
        "bank_name": "HDFC Bank",
        "loan_types": ["home", "personal", "car"],
        "min_monthly_income": 30000,
        "max_foir": 55,
        "min_age": 23,
        "max_age": 65,
        "max_loan_amount": {"home": 10000000, "personal": 4000000, "car": 1500000},
        "min_credit_score": 700,
        "eligible_employment_types": ["private_salaried", "self_employed", "business"]
    },
    {
        "bank_name": "ICICI Bank",
        "loan_types": ["home", "personal", "education", "car"],
        "min_monthly_income": 35000,
        "max_foir": 50,
        "min_age": 25,
        "max_age": 65,
        "max_loan_amount": {"home": 10000000, "personal": 3000000, "education": 2000000, "car": 1200000},
        "min_credit_score": 680,
        "eligible_employment_types": ["govt_salaried", "private_salaried", "business"]
    },
    {
        "bank_name": "Bank of Baroda",
        "loan_types": ["home", "personal", "education"],
        "min_monthly_income": 20000,
        "max_foir": 55,
        "min_age": 21,
        "max_age": 70,
        "max_loan_amount": {"home": 5000000, "personal": 1500000, "education": 2000000},
        "min_credit_score": 600,
        "eligible_employment_types": ["govt_salaried", "private_salaried", "self_employed", "business"]
    },
    {
        "bank_name": "Axis Bank",
        "loan_types": ["home", "personal", "car"],
        "min_monthly_income": 30000,
        "max_foir": 50,
        "min_age": 23,
        "max_age": 60,
        "max_loan_amount": {"home": 8000000, "personal": 2500000, "car": 1000000},
        "min_credit_score": 680,
        "eligible_employment_types": ["private_salaried", "business"]
    }
]
```

### `app/models/bank_eligibility.py`

```python
from app.data.bank_criteria import BANK_CRITERIA

def get_eligible_banks(loan_type, monthly_income, foir, age, credit_score, employment_type, requested_amount):
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
            "max_eligible_amount": bank['max_loan_amount'][loan_type]
        })

    return eligible
```

Each bank's criteria is deliberately independent and editable — this table
is easy to extend with more banks later without touching any model or
verdict logic.

---

## 4. Database Schema Addition

```sql
CREATE TABLE verdicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    credit_score_id UUID REFERENCES credit_scores(id),
    risk_assessment_id UUID REFERENCES risk_assessments(id),
    verdict VARCHAR(20),
    reasoning JSONB,
    suggested_adjustments JSONB,
    eligible_banks JSONB,
    requested_loan_amount FLOAT,
    requested_tenure_months INT,
    requested_loan_type VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 5. Backend Route

### `app/routes/verdict.py`

**POST /api/verdict/generate**
```json
Request:
{
  "requested_loan_amount": 500000,
  "requested_tenure_months": 60,
  "requested_loan_type": "home"
}

Response (200):
{
  "verdict": "approved",
  "creditworthiness_score": 742,
  "score_band": { "label": "Good", "color": "success" },
  "estimated_default_risk_probability": 0.12,
  "risk_tier": { "label": "Low risk", "color": "success" },
  "foir": 32.5,
  "reasoning": [
    "Creditworthiness score of 742 exceeds the approval threshold of 700.",
    "Estimated default risk of 12.0% is within acceptable limits.",
    "FOIR of 32.5% indicates manageable financial obligations."
  ],
  "suggested_adjustments": [],
  "eligible_banks": [
    { "bank_name": "SBI", "max_eligible_amount": 7500000 },
    { "bank_name": "Bank of Baroda", "max_eligible_amount": 5000000 }
  ]
}
```

If KYC gate fails:
```json
Response (403):
{
  "verdict": "kyc_required",
  "message": "Complete KYC verification before applying for a loan."
}
```

Full route logic order:
1. Check KYC gate — if fails, return 403 immediately
2. Fetch financial profile — if missing, return 400 asking user to complete it
3. Call compute_feature_set() from feature_engineering.py
4. Call calculate_creditworthiness_score() from credit_score.py, save to credit_scores
5. Call predict_default_risk() from risk_model.py, save to risk_assessments
6. Call determine_verdict(), generate_verdict_reasoning(), generate_suggestions()
7. If verdict is "approved" or "review", call get_eligible_banks()
8. Save everything to verdicts table, return full response

---

## 6. Frontend

### `frontend/loan-advisor.html`

Gated behind KYC verification (redirect to /kyc with message if not verified).

**Layout:**

1. **Request form** (if no verdict yet computed for this session):
   - Requested loan amount, tenure, loan type — same fields as Credit Score page
   - Button: "Get loan verdict"

2. **Verdict result view:**
   - Large verdict badge at top: "Approved" (green) / "Under review" (amber) / "Not eligible" (red)
   - Two-column stat row: Creditworthiness score (with band) | Estimated default risk (with tier)
   - FOIR shown as a small stat
   - "Why this verdict" section — bulleted reasoning list
   - "How to improve" section — bulleted suggested_adjustments (only shown if non-empty)
   - **If verdict is approved or review**: "Eligible banks" section — a card per bank showing bank name and max eligible amount, each with a "Proceed with this bank" button (this button links to the Bank Forms module — implement as a placeholder link for now, actual bank-form auto-fill is a separate future spec)
   - **If verdict is rejected**: no bank section, show a supportive message: "You don't currently qualify based on the criteria above. Review the suggestions to improve your eligibility."

### `static/js/loan-advisor.js`

- On submit, POST to `/api/verdict/generate`
- Handle the 403 kyc_required response by redirecting to `/kyc`
- Handle the 400 missing-financial-profile response by redirecting to `/financial-profile`
- Render verdict badge, stats, reasoning, suggestions, and bank cards per the layout above

---

## 7. What to tell Antigravity

> "Implement the Verdict Engine and Bank Eligibility Engine for LoanSphere
> exactly as described in SPEC_VERDICT.md. This includes:
> 1. app/models/verdict.py with check_kyc_gate, determine_verdict,
>    generate_verdict_reasoning, and generate_suggestions functions
> 2. app/data/bank_criteria.py with the BANK_CRITERIA list for 5 banks
> 3. app/models/bank_eligibility.py with get_eligible_banks function
> 4. The verdicts table in database/schema.sql
> 5. app/routes/verdict.py with POST /api/verdict/generate, JWT protected,
>    following the exact route logic order in Section 5
> 6. frontend/loan-advisor.html and static/js/loan-advisor.js following
>    SPEC_DESIGN_SYSTEM.md, gated behind KYC verification
> 7. The ML risk model NEVER outputs a verdict directly — only this module's
>    business rules in determine_verdict() decide approved/review/rejected"

---

## 8. Testing Checklist

- [ ] User without verified KYC → POST /api/verdict/generate returns 403 kyc_required
- [ ] User with verified KYC but no financial profile → returns 400
- [ ] High score + low risk + low FOIR → verdict = approved, eligible_banks non-empty
- [ ] Low score + high risk + high FOIR → verdict = rejected, eligible_banks empty
- [ ] Borderline values → verdict = review, reasoning explains why
- [ ] Eligible banks list correctly excludes banks where loan_type isn't offered
- [ ] Eligible banks list correctly excludes banks where requested_amount exceeds max_loan_amount
- [ ] Rejected verdict shows supportive message, no bank cards
- [ ] Suggested adjustments only appear when genuinely relevant (empty array when score is very high)
