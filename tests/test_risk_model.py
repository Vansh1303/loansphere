import os
import sys
import unittest
from unittest.mock import patch

from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.risk_model import get_risk_tier, predict_default_risk
from app.routes.risk_assessment import risk_assessment_bp


def risk_features(**overrides):
    features = {
        'age': 30,
        'monthly_income': 100000,
        'foir': 15,
        'credit_utilization': 10,
        'payment_history_score': 98,
        'employment_stability_score': 90,
        'debt_burden_score': 90,
        'inquiry_pressure_score': 95,
        'loan_to_income_ratio': 0.5,
        'employment_type': 'private_salaried',
        'requested_loan_type': 'home',
    }
    features.update(overrides)
    return features


class TestRiskModel(unittest.TestCase):
    def test_low_risk_profile_is_below_ten_percent(self):
        result = predict_default_risk(risk_features(), 800)

        self.assertLess(result['default_risk_probability'], 0.10)
        self.assertEqual(result['risk_tier']['label'], 'Low risk')

    def test_high_risk_profile_is_above_thirty_percent(self):
        result = predict_default_risk(risk_features(
            monthly_income=30000,
            foir=80,
            credit_utilization=90,
            payment_history_score=20,
            employment_stability_score=10,
            debt_burden_score=20,
            inquiry_pressure_score=20,
            loan_to_income_ratio=10,
            employment_type='self_employed',
            requested_loan_type='personal',
        ), 400)

        self.assertGreater(result['default_risk_probability'], 0.30)
        self.assertEqual(result['risk_tier']['label'], 'High risk')

    def test_risk_tier_boundaries(self):
        self.assertEqual(get_risk_tier(0.0999)['label'], 'Low risk')
        self.assertEqual(get_risk_tier(0.10)['label'], 'Moderate risk')
        self.assertEqual(get_risk_tier(0.2499)['label'], 'Moderate risk')
        self.assertEqual(get_risk_tier(0.25)['label'], 'High risk')


class TestRiskAssessmentRoute(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['JWT_SECRET_KEY'] = 'risk-assessment-test-secret-with-at-least-32-bytes'
        JWTManager(cls.app)
        cls.app.register_blueprint(risk_assessment_bp, url_prefix='/api')
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            cls.token = create_access_token(identity='00000000-0000-0000-0000-000000000001')

    @patch('app.routes.risk_assessment.save_risk_assessment', return_value={'id': 'assessment-1'})
    @patch('app.routes.risk_assessment.predict_default_risk', return_value={
        'default_risk_probability': 0.16,
        'risk_percentage': 16.0,
        'risk_tier': {'label': 'Moderate risk', 'color': 'warning'},
    })
    @patch('app.routes.risk_assessment.get_kyc_record', return_value={'date_of_birth': '1995-01-01'})
    @patch('app.routes.risk_assessment.get_financial_profile', return_value={
        'monthly_income': 75000,
        'employment_type': 'private_salaried',
        'employment_start_date': '2019-06-15',
        'existing_emis_monthly': 8000,
        'existing_loans_count': 1,
        'credit_card_limit_total': 150000,
        'credit_card_outstanding_total': 20000,
        'on_time_payments_pct': 99,
        'missed_payments_count_12m': 0,
        'defaults_count': 0,
        'settlements_count': 0,
        'credit_history_length_years': 5,
        'hard_inquiries_6m': 1,
    })
    @patch('app.routes.risk_assessment.get_user_credit_score', return_value={
        'id': 'score-1',
        'requested_loan_amount': 500000,
        'requested_tenure_months': 60,
        'requested_loan_type': 'home',
        'score': 742,
    })
    def test_assess_returns_risk_probability(
        self, _score, _profile, _kyc, _predict, _save
    ):
        response = self.client.post(
            '/api/risk/assess',
            headers={'Authorization': f'Bearer {self.token}'},
            json={'credit_score_id': 'score-1'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['default_risk_probability'], 0.16)
        self.assertEqual(response.get_json()['risk_tier']['label'], 'Moderate risk')


if __name__ == '__main__':
    unittest.main()
