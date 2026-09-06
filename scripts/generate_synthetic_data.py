"""Generate a reproducible, non-circular synthetic loan-default dataset."""

from pathlib import Path

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT_DIR / 'data' / 'synthetic_loan_data.csv'
N = 5000


def generate_synthetic_dataset(n: int = N) -> pd.DataFrame:
    """Produce realistic feature distributions and noisy default labels."""
    np.random.seed(42)
    data = []
    for _ in range(n):
        age = np.random.randint(21, 65)
        employment_type = np.random.choice(
            ['govt_salaried', 'private_salaried', 'self_employed', 'business'],
            p=[0.15, 0.45, 0.25, 0.15],
        )
        monthly_income = np.random.lognormal(mean=10.8, sigma=0.5)
        foir = np.clip(np.random.normal(35, 15), 0, 95)
        credit_utilization = np.clip(np.random.normal(35, 20), 0, 100)
        payment_history_score = np.clip(np.random.normal(75, 20), 0, 100)
        employment_stability_score = np.clip(np.random.normal(55, 25), 0, 100)
        debt_burden_score = np.clip(np.random.normal(65, 20), 0, 100)
        inquiry_pressure_score = np.clip(np.random.normal(70, 20), 0, 100)
        loan_to_income_ratio = np.clip(np.random.exponential(2.5), 0.1, 15)
        requested_loan_type = np.random.choice(['home', 'personal', 'education', 'car'])
        creditworthiness_score = np.clip(np.random.normal(650, 120), 300, 900)

        # This noisy generating process deliberately differs from LoanSphere's
        # deterministic credit-score and future verdict business rules.
        logit = (
            -3.0
            + 0.045 * (foir - 35)
            + 0.025 * (credit_utilization - 35)
            - 0.030 * (payment_history_score - 50)
            - 0.015 * (employment_stability_score - 50)
            - 0.010 * (creditworthiness_score - 650) / 10
            + 0.12 * np.log1p(loan_to_income_ratio)
            + np.random.normal(0, 0.6)
        )
        default_probability = 1 / (1 + np.exp(-logit))
        data.append({
            'age': age,
            'employment_type': employment_type,
            'monthly_income': monthly_income,
            'foir': foir,
            'credit_utilization': credit_utilization,
            'payment_history_score': payment_history_score,
            'employment_stability_score': employment_stability_score,
            'debt_burden_score': debt_burden_score,
            'inquiry_pressure_score': inquiry_pressure_score,
            'loan_to_income_ratio': loan_to_income_ratio,
            'requested_loan_type': requested_loan_type,
            'creditworthiness_score': creditworthiness_score,
            'defaulted': np.random.binomial(1, default_probability),
        })
    return pd.DataFrame(data)


if __name__ == '__main__':
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    dataset = generate_synthetic_dataset()
    dataset.to_csv(OUTPUT_PATH, index=False)
    print(f'Generated {len(dataset)} records. Default rate: {dataset.defaulted.mean():.2%}')
