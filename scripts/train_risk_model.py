"""Train and save the LoanSphere default-risk classifier."""

from pathlib import Path
import sys

import joblib
import pandas as pd
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.models.risk_model import COLUMNS_PATH, MODEL_PATH, build_model


if __name__ == '__main__':
    dataset = pd.read_csv(ROOT_DIR / 'data' / 'synthetic_loan_data.csv')
    dataset = pd.get_dummies(dataset, columns=['employment_type', 'requested_loan_type'])
    features = dataset.drop(columns=['defaulted'])
    target = dataset['defaulted']

    x_train, x_test, y_train, y_test = train_test_split(
        features, target, test_size=0.2, random_state=42, stratify=target
    )
    model = build_model()
    model.fit(x_train, y_train)

    probabilities = model.predict_proba(x_test)[:, 1]
    auc = roc_auc_score(y_test, probabilities)
    print(f'Test AUC: {auc:.3f}')
    print(classification_report(y_test, model.predict(x_test), zero_division=0))

    joblib.dump(model, MODEL_PATH)
    joblib.dump(list(features.columns), COLUMNS_PATH)
    print(f'Saved model to {MODEL_PATH}')
