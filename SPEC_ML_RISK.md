# LoanSphere — ML Default Risk Model Spec

Follow SPEC_DESIGN_SYSTEM.md for all styling.
Depends on SPEC_FEATURES.md for feature computation and SPEC_CREDIT_SCORE.md
for the creditworthiness score, which is itself one input feature to this model.

---

## 1. Why this module exists and how it differs from Credit Score

The Creditworthiness Score (previous spec) is a deterministic, explainable
formula. This module is genuinely different: a trained ML classifier that
predicts **probability of default** — a separate signal, not a re-derivation
of the same score under a different name.

**Critical design rule**: this model does NOT predict "approved/review/rejected"
directly. Those business decisions belong to the Verdict Engine (next spec),
which combines this model's risk probability with the creditworthiness score
and hard business rules. This model's only job is to output a single number:
the estimated probability (0.0–1.0) that this applicant would default.

---

## 2. Model Architecture

**Ensemble: Logistic Regression + Decision Tree, soft-voting average**

```python
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import VotingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

def build_model():
    lr = LogisticRegression(max_iter=1000, class_weight='balanced')
    dt = DecisionTreeClassifier(max_depth=5, min_samples_leaf=20, class_weight='balanced')

    ensemble = VotingClassifier(
        estimators=[('logistic', lr), ('tree', dt)],
        voting='soft'  # averages predicted probabilities, not just class votes
    )

    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('ensemble', ensemble)
    ])
    return pipeline
```

Why this combination: Logistic Regression is the industry-standard baseline
for credit risk (fast, well-calibrated, linear relationships). The Decision
Tree captures non-linear threshold effects (e.g. a FOIR jump past 55% being
disproportionately risky). Averaging their probabilities is more robust than
either alone, and both are fast enough to train and run without a GPU.

---

## 3. Model Input Features

| Feature | Source | Encoding |
|---------|--------|----------|
| creditworthiness_score | credit_scores table | numeric, scaled |
| foir | feature_set | numeric, scaled |
| credit_utilization | feature_set | numeric, scaled |
| payment_history_score | feature_set | numeric, scaled |
| employment_stability_score | feature_set | numeric, scaled |
| debt_burden_score | feature_set | numeric, scaled |
| inquiry_pressure_score | feature_set | numeric, scaled |
| loan_to_income_ratio | feature_set | numeric, scaled |
| age | feature_set | numeric, scaled |
| employment_type | feature_set | one-hot encoded (4 categories) |
| requested_loan_type | feature_set | one-hot encoded (4 categories) |

Note: `kyc_verified` is intentionally NOT a model input. KYC is a compliance
gate handled separately by the Verdict Engine, not a risk signal — per the
architecture correction we agreed on. Mixing compliance and risk in one
model muddies both.

---

## 4. Synthetic Training Data Generation

**Critical principle**: do NOT generate labels using the same rules the
model is meant to learn (that's circular and teaches nothing). Instead,
generate each feature with realistic random distributions, then compute a
default probability using a DIFFERENT, noisier formula than either the
credit score or verdict engine use — so the model has to learn genuine
statistical relationships rather than memorize a rule.

### `scripts/generate_synthetic_data.py`

```python
import numpy as np
import pandas as pd

np.random.seed(42)
N = 5000

def generate_synthetic_dataset(n=N):
    data = []
    for _ in range(n):
        age = np.random.randint(21, 65)
        employment_type = np.random.choice(
            ['govt_salaried', 'private_salaried', 'self_employed', 'business'],
            p=[0.15, 0.45, 0.25, 0.15]
        )
        monthly_income = np.random.lognormal(mean=10.8, sigma=0.5)  # realistic income skew
        foir = np.clip(np.random.normal(35, 15), 0, 95)
        credit_utilization = np.clip(np.random.normal(35, 20), 0, 100)
        payment_history_score = np.clip(np.random.normal(75, 20), 0, 100)
        employment_stability_score = np.clip(np.random.normal(55, 25), 0, 100)
        debt_burden_score = np.clip(np.random.normal(65, 20), 0, 100)
        inquiry_pressure_score = np.clip(np.random.normal(70, 20), 0, 100)
        loan_to_income_ratio = np.clip(np.random.exponential(2.5), 0.1, 15)
        requested_loan_type = np.random.choice(['home', 'personal', 'education', 'car'])
        creditworthiness_score = np.clip(np.random.normal(650, 120), 300, 900)

        # Underlying TRUE default probability model — deliberately different
        # from both the credit score formula and any rule the verdict engine
        # will use, with realistic non-linear relationships and noise.
        logit = (
            -3.0
            + 0.045 * (foir - 35)                      # higher FOIR -> more risk
            + 0.025 * (credit_utilization - 35)         # higher utilization -> more risk
            - 0.030 * (payment_history_score - 50)      # better history -> less risk
            - 0.015 * (employment_stability_score - 50) # more stable -> less risk
            - 0.010 * (creditworthiness_score - 650) / 10
            + 0.12 * np.log1p(loan_to_income_ratio)      # bigger loan relative to income -> more risk
            + np.random.normal(0, 0.6)                   # noise so it's not perfectly learnable
        )
        default_probability_true = 1 / (1 + np.exp(-logit))
        defaulted = np.random.binomial(1, default_probability_true)

        data.append({
            "age": age, "employment_type": employment_type, "monthly_income": monthly_income,
            "foir": foir, "credit_utilization": credit_utilization,
            "payment_history_score": payment_history_score,
            "employment_stability_score": employment_stability_score,
            "debt_burden_score": debt_burden_score,
            "inquiry_pressure_score": inquiry_pressure_score,
            "loan_to_income_ratio": loan_to_income_ratio,
            "requested_loan_type": requested_loan_type,
            "creditworthiness_score": creditworthiness_score,
            "defaulted": defaulted
        })

    return pd.DataFrame(data)

if __name__ == "__main__":
    df = generate_synthetic_dataset()
    df.to_csv("data/synthetic_loan_data.csv", index=False)
    print(f"Generated {len(df)} records. Default rate: {df['defaulted'].mean():.2%}")
```

This produces a realistic ~8-15% default rate (typical for subprime-inclusive
lending portfolios) with genuine, noisy, non-circular relationships between
features and outcomes.

---

## 5. Training Script

### `scripts/train_risk_model.py`

```python
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report

df = pd.read_csv("data/synthetic_loan_data.csv")
df = pd.get_dummies(df, columns=['employment_type', 'requested_loan_type'])

X = df.drop(columns=['defaulted'])
y = df['defaulted']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

from app.models.risk_model import build_model
model = build_model()
model.fit(X_train, y_train)

probs = model.predict_proba(X_test)[:, 1]
auc = roc_auc_score(y_test, probs)
print(f"Test AUC: {auc:.3f}")
print(classification_report(y_test, model.predict(X_test)))

joblib.dump(model, "app/models/risk_model.pkl")
joblib.dump(list(X.columns), "app/models/risk_model_columns.pkl")
```

Run this once during setup: `python scripts/generate_synthetic_data.py && python scripts/train_risk_model.py`

A reasonable AUC on this synthetic data will land around 0.72-0.82 — report
this honestly, don't inflate it. An AUC in this range is realistic and
defensible for a college project; claiming 0.95+ on synthetic credit data
would look suspicious to anyone who understands the domain.

---

## 6. Inference Function

### `app/models/risk_model.py`

```python
import joblib
import pandas as pd

_model = None
_columns = None

def load_risk_model():
    global _model, _columns
    if _model is None:
        _model = joblib.load("app/models/risk_model.pkl")
        _columns = joblib.load("app/models/risk_model_columns.pkl")
    return _model, _columns

def predict_default_risk(feature_set: dict, creditworthiness_score: int) -> dict:
    model, columns = load_risk_model()

    row = {
        "age": feature_set['age'],
        "monthly_income": feature_set.get('monthly_income', 0),
        "foir": feature_set['foir'],
        "credit_utilization": feature_set['credit_utilization'],
        "payment_history_score": feature_set['payment_history_score'],
        "employment_stability_score": feature_set['employment_stability_score'],
        "debt_burden_score": feature_set['debt_burden_score'],
        "inquiry_pressure_score": feature_set['inquiry_pressure_score'],
        "loan_to_income_ratio": feature_set['loan_to_income_ratio'],
        "creditworthiness_score": creditworthiness_score,
    }
    for col in columns:
        if col.startswith('employment_type_'):
            row[col] = 1 if col == f"employment_type_{feature_set['employment_type']}" else 0
        elif col.startswith('requested_loan_type_'):
            row[col] = 1 if col == f"requested_loan_type_{feature_set['requested_loan_type']}" else 0

    input_df = pd.DataFrame([row])[columns]
    risk_probability = model.predict_proba(input_df)[0, 1]

    return {
        "default_risk_probability": round(float(risk_probability), 4),
        "risk_percentage": round(float(risk_probability) * 100, 1),
        "risk_tier": get_risk_tier(risk_probability)
    }

def get_risk_tier(probability):
    if probability < 0.10:
        return {"label": "Low risk", "color": "success"}
    elif probability < 0.25:
        return {"label": "Moderate risk", "color": "warning"}
    else:
        return {"label": "High risk", "color": "danger"}
```

**Language rule**: always present this as "Estimated default risk: 16%" or
"Model probability: 0.16" — never as "84% confidence" of approval. Risk
probability and confidence are different concepts; don't conflate them
anywhere in UI copy, API responses, or the report.

---

## 7. Database Schema Addition

```sql
CREATE TABLE risk_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    credit_score_id UUID REFERENCES credit_scores(id),
    default_risk_probability FLOAT,
    risk_tier VARCHAR(20),
    model_version VARCHAR(20) DEFAULT 'v1',
    computed_at TIMESTAMP DEFAULT NOW()
);
```

---

## 8. Backend Route

### `app/routes/risk_assessment.py`

**POST /api/risk/assess**
```json
Request:
{
  "credit_score_id": "uuid-of-existing-credit-score-record"
}

Response (200):
{
  "default_risk_probability": 0.16,
  "risk_percentage": 16.0,
  "risk_tier": { "label": "Moderate risk", "color": "warning" }
}
```

Logic: fetch the credit_scores row by ID, verify it belongs to the
authenticated user, re-fetch the user's financial_profiles data, recompute
feature_set via feature_engineering.py, then call predict_default_risk().
Save to risk_assessments table.

This route is typically called internally by the Verdict Engine, not
directly by the frontend — but expose it as a real endpoint anyway for
transparency and so the report can document it as a distinct API.

---

## 9. What to tell Antigravity

> "Implement the ML Default Risk Model for LoanSphere exactly as described
> in SPEC_ML_RISK.md. This includes:
> 1. scripts/generate_synthetic_data.py to generate 5000 realistic synthetic
>    loan records with noisy, non-circular relationships between features
>    and default outcomes
> 2. scripts/train_risk_model.py to train a soft-voting ensemble of
>    LogisticRegression and DecisionTreeClassifier, saving the model and
>    column list as pickle files
> 3. app/models/risk_model.py with load_risk_model, predict_default_risk,
>    and get_risk_tier functions
> 4. The risk_assessments table in database/schema.sql
> 5. app/routes/risk_assessment.py with POST /api/risk/assess, JWT protected
> 6. Run the data generation and training scripts once during setup and
>    commit the resulting .pkl files to the repo so the model doesn't need
>    retraining on every deployment
> 7. Never present the risk probability as a 'confidence' score — always
>    frame it explicitly as 'estimated default risk probability'"

---

## 10. Testing Checklist

- [ ] Training script runs and prints a test AUC between roughly 0.70-0.85
- [ ] A low-FOIR, high-payment-history, stable-employment applicant gets a
      risk probability under 10%
- [ ] A high-FOIR, multiple-defaults applicant gets a risk probability over 30%
- [ ] predict_default_risk returns a value between 0.0 and 1.0 always
- [ ] Model and column pickle files load correctly without errors on Flask startup
- [ ] risk_tier boundaries match Section 6 exactly (10%, 25%)
