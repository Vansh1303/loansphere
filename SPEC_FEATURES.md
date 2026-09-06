# LoanSphere — Feature Engineering Module Spec

Follow SPEC_DESIGN_SYSTEM.md for all styling on any UI in this spec.

This module has NO user-facing page of its own. It is a shared backend
library that both the Credit Score module and the ML Risk module import
from, so that both systems compute derived features identically. This
avoids the two systems disagreeing on what "FOIR" or "utilization" means.

---

## 1. Why this module exists

Without a shared feature store, the rule-based credit score and the ML risk
model could end up computing FOIR or utilization slightly differently,
producing inconsistent results that are hard to explain to the panel. This
module is the single source of truth for every derived financial metric in
LoanSphere.

---

## 2. Raw Inputs (collected once, on the "Financial Profile" page)

| Field | Type | Notes |
|-------|------|-------|
| monthly_income | Float | Gross monthly income |
| employment_type | Enum | govt_salaried / private_salaried / self_employed / business |
| employment_start_date | Date | Used to compute stability in years |
| existing_emis_monthly | Float | Sum of all current EMI obligations |
| existing_loans_count | Int | Number of active loans |
| credit_card_limit_total | Float | Sum of all credit card limits |
| credit_card_outstanding_total | Float | Sum of all credit card balances |
| on_time_payments_pct | Float (0-100) | Self-declared % of on-time payments over last 24 months |
| missed_payments_count_12m | Int | Number of missed payments in last 12 months |
| defaults_count | Int | Number of loan defaults ever |
| settlements_count | Int | Number of settled/written-off accounts |
| credit_history_length_years | Float | Years since first credit account opened |
| hard_inquiries_6m | Int | Number of loan/credit applications in last 6 months |
| requested_loan_amount | Float | For the specific loan being evaluated |
| requested_tenure_months | Int | 12-360 |
| requested_loan_type | Enum | home / personal / education / car |
| age | Int | From KYC date_of_birth |

**UI note**: These self-declared credit history fields should carry an
explicit disclaimer in the UI: "This information is self-declared. In a
production system, this would be verified against credit bureau records
(CIBIL/Experian)." Place this note directly under the Payment History
section header.

---

## 3. Derived Features (computed by this module)

### 3.1 EMI calculation

```python
def calculate_emi(principal, annual_rate_pct, tenure_months):
    r = (annual_rate_pct / 12) / 100
    if r == 0:
        return principal / tenure_months
    emi = principal * r * (1 + r) ** tenure_months / ((1 + r) ** tenure_months - 1)
    return round(emi, 2)
```

Use a default annual interest rate per loan type if not otherwise specified:
- home: 8.5%
- personal: 12.5%
- education: 9.5%
- car: 10.5%

### 3.2 FOIR (Fixed Obligation to Income Ratio)

```python
def calculate_foir(existing_emis_monthly, new_emi, monthly_income):
    if monthly_income <= 0:
        return 100.0
    foir = ((existing_emis_monthly + new_emi) / monthly_income) * 100
    return round(min(foir, 100.0), 2)
```

### 3.3 Credit utilization ratio

```python
def calculate_utilization(credit_card_outstanding_total, credit_card_limit_total):
    if credit_card_limit_total <= 0:
        return 0.0
    return round((credit_card_outstanding_total / credit_card_limit_total) * 100, 2)
```

### 3.4 Employment stability score (0-100, continuous)

```python
def calculate_employment_stability(employment_start_date, employment_type):
    from datetime import date
    years = (date.today() - employment_start_date).days / 365.25

    # Continuous curve: stability rises with years, plateaus after 7 years
    base_score = min(100, (years / 7) * 100)

    # Small supporting adjustment for employment type stability
    type_adjustment = {
        "govt_salaried": 5,
        "private_salaried": 0,
        "self_employed": -5,
        "business": -8
    }.get(employment_type, 0)

    return round(max(0, min(100, base_score + type_adjustment)), 2)
```

### 3.5 Debt burden ratio

```python
def calculate_debt_burden(existing_loans_count, existing_emis_monthly, monthly_income):
    loan_count_penalty = min(existing_loans_count * 8, 40)
    emi_ratio = (existing_emis_monthly / monthly_income * 100) if monthly_income > 0 else 100
    score = 100 - loan_count_penalty - min(emi_ratio, 60)
    return round(max(0, score), 2)
```

### 3.6 Payment history score

```python
def calculate_payment_history_score(on_time_payments_pct, missed_payments_count_12m, defaults_count, settlements_count):
    score = on_time_payments_pct
    score -= missed_payments_count_12m * 5
    score -= defaults_count * 20
    score -= settlements_count * 15
    return round(max(0, min(100, score)), 2)
```

### 3.7 Inquiry pressure score

```python
def calculate_inquiry_pressure(hard_inquiries_6m):
    # More inquiries = higher pressure = worse score
    score = 100 - (hard_inquiries_6m * 15)
    return round(max(0, min(100, score)), 2)
```

### 3.8 Loan to income ratio

```python
def calculate_loan_to_income_ratio(requested_loan_amount, monthly_income):
    annual_income = monthly_income * 12
    if annual_income <= 0:
        return 99.0
    return round(requested_loan_amount / annual_income, 2)
```

---

## 4. The Feature Store Function

### `app/models/feature_engineering.py`

This is the single function both Credit Score and ML Risk modules call:

```python
def compute_feature_set(raw_inputs: dict) -> dict:
    """
    Takes raw_inputs dict matching Section 2 fields.
    Returns a complete feature dict used by both scoring systems.
    """
    new_emi = calculate_emi(
        raw_inputs['requested_loan_amount'],
        get_default_rate(raw_inputs['requested_loan_type']),
        raw_inputs['requested_tenure_months']
    )

    features = {
        "foir": calculate_foir(
            raw_inputs['existing_emis_monthly'], new_emi, raw_inputs['monthly_income']
        ),
        "credit_utilization": calculate_utilization(
            raw_inputs['credit_card_outstanding_total'], raw_inputs['credit_card_limit_total']
        ),
        "employment_stability_score": calculate_employment_stability(
            raw_inputs['employment_start_date'], raw_inputs['employment_type']
        ),
        "debt_burden_score": calculate_debt_burden(
            raw_inputs['existing_loans_count'], raw_inputs['existing_emis_monthly'], raw_inputs['monthly_income']
        ),
        "payment_history_score": calculate_payment_history_score(
            raw_inputs['on_time_payments_pct'], raw_inputs['missed_payments_count_12m'],
            raw_inputs['defaults_count'], raw_inputs['settlements_count']
        ),
        "inquiry_pressure_score": calculate_inquiry_pressure(
            raw_inputs['hard_inquiries_6m']
        ),
        "loan_to_income_ratio": calculate_loan_to_income_ratio(
            raw_inputs['requested_loan_amount'], raw_inputs['monthly_income']
        ),
        "new_emi": new_emi,
        "credit_history_length_years": raw_inputs['credit_history_length_years'],
        "age": raw_inputs['age'],
        "employment_type": raw_inputs['employment_type'],
        "requested_loan_type": raw_inputs['requested_loan_type'],
    }
    return features
```

---

## 5. Database Schema Addition

```sql
CREATE TABLE financial_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    monthly_income FLOAT,
    employment_type VARCHAR(30),
    employment_start_date DATE,
    existing_emis_monthly FLOAT DEFAULT 0,
    existing_loans_count INT DEFAULT 0,
    credit_card_limit_total FLOAT DEFAULT 0,
    credit_card_outstanding_total FLOAT DEFAULT 0,
    on_time_payments_pct FLOAT DEFAULT 100,
    missed_payments_count_12m INT DEFAULT 0,
    defaults_count INT DEFAULT 0,
    settlements_count INT DEFAULT 0,
    credit_history_length_years FLOAT DEFAULT 0,
    hard_inquiries_6m INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

Loan-specific request fields (requested_loan_amount, tenure, type) are NOT
stored here — they're passed per-request from the Credit Score / Loan
Advisor forms since they vary per application, not per user profile.

---

## 6. Backend Route

### `app/routes/financial_profile.py`

**POST /api/financial-profile** — save/update the user's financial profile
**GET /api/financial-profile** — retrieve it (used to pre-fill forms later)

Both JWT protected. Standard CRUD, no AI logic here — this route only
persists raw inputs. Feature computation happens on-demand in the Credit
Score and ML Risk modules, not at save time, since requested_loan_amount
and tenure vary per application.

---

## 7. Frontend

### `frontend/financial-profile.html`

A form page, gated behind KYC verification (redirect to /kyc if not
verified — reuse the `require_kyc_verified` pattern from SPEC_KYC.md).

Sections (each with a 15px section header per design spec):
1. **Income & employment** — monthly income, employment type, employment start date
2. **Existing obligations** — existing EMIs, existing loans count, credit card limit/outstanding
3. **Payment history** *(with the disclaimer note from Section 2 above)* — on-time %, missed payments, defaults, settlements, credit history length, hard inquiries

Submit button: "Save financial profile"

This page does not show a score — it just collects data. The Credit Score
page (next spec) is where the user requests a specific loan amount/tenure
and sees their computed score.

---

## 8. What to tell Antigravity

> "Implement the feature engineering module for LoanSphere exactly as
> described in SPEC_FEATURES.md. This includes:
> 1. The financial_profiles table in database/schema.sql
> 2. app/models/feature_engineering.py with all the calculation functions
>    in Section 3 and the compute_feature_set function in Section 4
> 3. app/routes/financial_profile.py with POST and GET /api/financial-profile,
>    JWT protected
> 4. frontend/financial-profile.html and static/js/financial-profile.js
>    following SPEC_DESIGN_SYSTEM.md, gated behind KYC verification
> 5. This module has no scoring logic of its own — it only collects raw
>    inputs and exposes the compute_feature_set function for other modules
>    to import and use"

---

## 9. Testing Checklist

- [ ] Save a financial profile with valid data → GET returns the same data
- [ ] compute_feature_set with income=50000, no existing EMIs, loan=500000,
      tenure=60 → FOIR should be a reasonable value (verify manually with
      EMI formula)
- [ ] compute_feature_set with employment_start_date 10 years ago →
      employment_stability_score should be capped near 100 (plus type adjustment)
- [ ] compute_feature_set with 3 defaults → payment_history_score drops
      significantly (by 60 points from defaults alone)
- [ ] Financial profile page redirects to /kyc if KYC not verified
