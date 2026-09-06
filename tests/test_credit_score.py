import os
import sys
import unittest
from unittest.mock import patch

from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.credit_score import (
    calculate_creditworthiness_score,
    generate_score_explanation,
    score_foir,
    score_utilization,
)
from app.routes.credit_score import credit_score_bp


def feature_set(**overrides):
    """Return a complete, favorable baseline feature set for score tests."""
    features = {
        'foir': 25.0,
        'credit_utilization': 20.0,
        'payment_history_score': 100.0,
        'employment_stability_score': 100.0,
        'debt_burden_score': 100.0,
        'inquiry_pressure_score': 100.0,
    }
    features.update(overrides)
    return features


class TestCreditScoreModel(unittest.TestCase):
    def test_strong_profile_is_excellent(self):
        result = calculate_creditworthiness_score(feature_set())

        self.assertGreaterEqual(result['score'], 750)
        self.assertEqual(result['band']['label'], 'Excellent')

    def test_risky_profile_is_poor_or_very_poor(self):
        result = calculate_creditworthiness_score(feature_set(
            foir=65.0,
            credit_utilization=90.0,
            payment_history_score=40.0,
            employment_stability_score=10.0,
            debt_burden_score=20.0,
            inquiry_pressure_score=70.0,
        ))

        self.assertLess(result['score'], 500)
        self.assertIn(result['band']['label'], {'Poor', 'Very poor'})

    def test_component_weights_sum_to_100(self):
        result = calculate_creditworthiness_score(feature_set())

        self.assertEqual(
            sum(component['weight'] for component in result['component_breakdown'].values()),
            100,
        )

    def test_nearby_foir_values_change_smoothly(self):
        score_at_29 = score_foir(29.0)
        score_at_31 = score_foir(31.0)

        self.assertAlmostEqual(score_at_29 - score_at_31, 4.0)
        self.assertLess(abs(score_at_29 - score_at_31), 10.0)

    def test_explanations_have_four_clear_entries(self):
        result = calculate_creditworthiness_score(feature_set())
        explanations = generate_score_explanation(result['component_breakdown'])

        self.assertEqual(len(explanations), 4)
        self.assertTrue(all(isinstance(explanation, str) and explanation for explanation in explanations))

    def test_component_functions_respect_bounds(self):
        self.assertEqual(score_foir(20), 100.0)
        self.assertEqual(score_foir(70), 0.0)
        self.assertEqual(score_utilization(10), 100.0)
        self.assertEqual(score_utilization(90), 0.0)


class TestCreditScoreRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config['JWT_SECRET_KEY'] = 'credit-score-test-secret-with-at-least-32-bytes'
        JWTManager(cls.app)
        cls.app.register_blueprint(credit_score_bp, url_prefix='/api')
        cls.client = cls.app.test_client()

        with cls.app.app_context():
            cls.token = create_access_token(identity='00000000-0000-0000-0000-000000000001')

    def auth_headers(self):
        return {'Authorization': f'Bearer {self.token}'}

    @patch('app.routes.credit_score.get_financial_profile', return_value=None)
    def test_calculate_requires_financial_profile(self, _get_financial_profile):
        response = self.client.post(
            '/api/credit-score/calculate',
            headers=self.auth_headers(),
            json={
                'requested_loan_amount': 500000,
                'requested_tenure_months': 60,
                'requested_loan_type': 'home',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Financial profile not found', response.get_json()['msg'])


if __name__ == '__main__':
    unittest.main()
