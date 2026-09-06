# LoanSphere — Creditworthiness Score Module Spec

Follow SPEC_DESIGN_SYSTEM.md for all styling.
Depends on SPEC_FEATURES.md — this module imports compute_feature_set()
rather than recalculating anything itself.

Do NOT call this a "CIBIL Score Predictor" anywhere in code, UI copy, or
docs. Call it the "LoanSphere Creditworthiness Score" — a project-specific,
explainable 0-900 scoring system inspired by industry FOIR standards, not a
prediction of a user's actual CIBIL score.

---

## 1. Why this module exists

This gives the user a transparent, explainable score (0-900, same range as
CIBIL so it feels familiar) built from a weighted formula over the features
computed in SPEC_FEATURES.md. It is deterministic and rule-based —
NOT machine learning. The ML model lives in a separate module (SPEC_ML_RISK.md)
that predicts default risk probability as a different, complementary signal.

**KYC is not a factor in this score.** A user with unverified KYC can still
see their creditworthiness score — KYC only gates whether they can proceed
to apply for an actual loan later (Loan Advisor module).

---

## 2. Scoring Formula

Final score = weighted sum of 5 components, each individually scored 0-100,
then scaled to the 300-900 range.

| Component | Weight | Feature source |
|-----------|--------|------------------|
| FOIR | 30% | feature_set['foir'] |
| Payment history | 25% | feature_set['payment_history_score'] |
| Credit utilization | 15% | feature_set['credit_utilization'] |
| Employment stability | 15% | feature_set['employment_stability_score'] |
| Debt burden | 10% | feature_set['debt_burden_score'] |
| Inquiry pressure | 5% | feature_set['inquiry_pressure_score'] |

### 2.1 Component scoring functions (all continuous, no cliff edges)

```python
def score_foir(foir):
    # Piecewise linear: lower FOIR = higher score
    if foir <= 20:
        return 100
    elif foir >= 70:
        return 0
    else:
        return round(100 - ((foir - 20) / 50) * 100, 2)

def score_utilization(utilization_pct):
    # Lower utilization = higher score. 30% is the healthy threshold.
    if utilization_pct <= 10:
        return 100
    elif utilization_pct >= 90:
        return 0
    else:
        return round(100 - ((utilization_pct - 10) / 80) * 100, 2)

# payment_history_score, employment_stability_score, debt_burden_score,
# inquiry_pressure_score are already 0-100 from SPEC_FEATURES.md —
# use them directly, no further transformation needed.
```

### 2.2 Final score calculation

```python
def calculate_creditworthiness_score(feature_set: dict) -> dict:
    foir_score = score_foir(feature_set['foir'])
    utilization_score = score_utilization(feature_set['credit_utilization'])
    payment_score = feature_set['payment_history_score']
    employment_score = feature_set['employment_stability_score']
    debt_score = feature_set['debt_burden_score']
    inquiry_score = feature_set['inquiry_pressure_score']

    weighted_sum = (
        foir_score * 0.30 +
        payment_score * 0.25 +
        utilization_score * 0.15 +
        employment_score * 0.15 +
        debt_score * 0.10 +
        inquiry_score * 0.05
    )

    # Scale 0-100 weighted sum to 300-900 range
    final_score = round(300 + (weighted_sum / 100) * 600)

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


def get_score_band(score):
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
```

---

## 3. Plain English Explanation Generator

The panel and users should see WHY they got their score, not just a number.

```python
def generate_score_explanation(component_breakdown: dict) -> list:
    explanations = []

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
```

---

## 4. Database Schema Addition

```sql
CREATE TABLE credit_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    requested_loan_amount FLOAT,
    requested_tenure_months INT,
    requested_loan_type VARCHAR(20),
    score INT,
    band VARCHAR(20),
    component_breakdown JSONB,
    explanation JSONB,
    computed_at TIMESTAMP DEFAULT NOW()
);
```

Each score computation is stored as a new row (not upserted) — this creates
a history the user can look back on, and gives you real data to show
"score improved over time" type visualizations if you want to extend this
later.

---

## 5. Backend Route

### `app/routes/credit_score.py`

**POST /api/credit-score/calculate**
```json
Request:
{
  "requested_loan_amount": 500000,
  "requested_tenure_months": 60,
  "requested_loan_type": "home"
}

Response (200):
{
  "score": 742,
  "band": { "label": "Good", "color": "success" },
  "component_breakdown": { ... },
  "explanation": [
    "Your FOIR of 32% is healthy and well within safe lending limits.",
    "Your payment history shows strong reliability with minimal missed payments.",
    "Your employment stability is a strong positive factor.",
    "Your credit utilization of 24% is in the ideal range."
  ]
}
```

Logic: fetch the user's `financial_profiles` row, merge with the request
body's loan-specific fields, call `compute_feature_set()` from
feature_engineering.py, then `calculate_creditworthiness_score()`. Save the
result to `credit_scores` table. Return 400 if no financial profile exists
yet — instruct the user to complete their financial profile first.

**GET /api/credit-score/latest** — returns the most recent score for the
logged in user, or `{ "score": null }` if none computed yet.

---

## 6. Frontend

### `frontend/credit-score.html`

Gated behind: financial profile must exist (not KYC — score can be seen
without KYC, KYC only gates loan application later).

**Layout:**

1. **If no score yet computed**: show a small form —
   - Requested loan amount (number input)
   - Requested tenure (number input, months)
   - Requested loan type (select: Home / Personal / Education / Car)
   - Button: "Calculate score"

2. **After calculation — score display:**
   - Large score number (32px, band color) with band label badge next to it
   - Score ring/gauge visual (simple SVG arc, 300-900 range, colored by band) — see widget guidance below
   - "Why this score" section — bulleted list from the explanation array
   - Component breakdown table — 6 rows, each showing: component name, raw value, contribution score, weight%
   - Button: "Recalculate" (goes back to the form, e.g. for a different loan amount)

**Score gauge**: build a simple semi-circular SVG gauge (0 at left, 900 at
right, needle or filled arc pointing to current score) using the design
system's color tokens for the band coloring. Keep it flat, no gradients —
use a single flat-colored arc for the "filled" portion of the gauge (the
color matching the band: green/amber/red) and a light gray arc for the
remainder.

### `static/js/credit-score.js`

- On load, call `GET /api/credit-score/latest` — if a score exists, show
  the score display directly. If not, show the calculation form.
- On submit, POST to `/api/credit-score/calculate`
- Render component breakdown as a simple table
- Render the explanation array as a bulleted list under a "Why this score" heading

---

## 7. What to tell Antigravity

> "Implement the Creditworthiness Score module for LoanSphere exactly as
> described in SPEC_CREDIT_SCORE.md. This includes:
> 1. The credit_scores table in database/schema.sql
> 2. app/models/credit_score.py with score_foir, score_utilization,
>    calculate_creditworthiness_score, get_score_band, and
>    generate_score_explanation functions — this module imports
>    compute_feature_set from app/models/feature_engineering.py, it does
>    not duplicate any calculation logic
> 3. app/routes/credit_score.py with POST /api/credit-score/calculate and
>    GET /api/credit-score/latest, JWT protected
> 4. frontend/credit-score.html and static/js/credit-score.js following
>    SPEC_DESIGN_SYSTEM.md, including a simple flat-colored SVG score gauge
> 5. Never refer to this as a CIBIL score predictor anywhere — always
>    'LoanSphere Creditworthiness Score'"

---

## 8. Testing Checklist

- [ ] User with no financial profile → calculate returns 400 with a clear message
- [ ] User with FOIR=25%, strong payment history, stable employment →
      score should land in 750+ (Excellent) range
- [ ] User with FOIR=65%, 2 defaults, low employment stability → score
      should land below 500 (Poor/Very poor)
- [ ] Component breakdown weights sum to exactly 100% (30+25+15+15+10+5)
- [ ] Two nearby FOIR values (e.g. 29% and 31%) produce close scores, not a
      dramatic jump — confirms piecewise linear scoring works correctly
- [ ] Explanation array always has at least 4 entries and reads as plain,
      grammatically correct English
- [ ] Score gauge visually reflects the band color correctly
