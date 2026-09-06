import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import unittest
from datetime import date, timedelta
from flask_jwt_extended import create_access_token
from app import create_app
from app.db.db import get_connection, release_connection
from app.models.feature_engineering import (
    calculate_emi,
    get_default_rate,
    calculate_foir,
    calculate_utilization,
    calculate_employment_stability,
    calculate_debt_burden,
    calculate_payment_history_score,
    calculate_inquiry_pressure,
    calculate_loan_to_income_ratio,
    compute_feature_set,
    save_financial_profile,
    get_financial_profile
)


class TestFeatureEngineering(unittest.TestCase):

    def test_calculate_emi(self):
        # Principal: 500,000, 8.5% annual rate, 60 months
        emi = calculate_emi(500000, 8.5, 60)
        self.assertAlmostEqual(emi, 10258.27, places=1)

        # 0% interest rate
        emi_zero = calculate_emi(120000, 0, 12)
        self.assertEqual(emi_zero, 10000.0)

        # 0 tenure edge case
        self.assertEqual(calculate_emi(50000, 10, 0), 0.0)

    def test_default_rates(self):
        self.assertEqual(get_default_rate('home'), 8.5)
        self.assertEqual(get_default_rate('personal'), 12.5)
        self.assertEqual(get_default_rate('education'), 9.5)
        self.assertEqual(get_default_rate('car'), 10.5)
        self.assertEqual(get_default_rate('unknown'), 10.5)

    def test_calculate_foir(self):
        # Income=50000, no existing EMIs, new EMI=10258.27 -> FOIR ~ 20.52%
        foir = calculate_foir(0, 10258.27, 50000)
        self.assertEqual(foir, 20.52)

        # Income=0 edge case -> 100.0
        self.assertEqual(calculate_foir(5000, 5000, 0), 100.0)

        # FOIR exceeds 100 -> capped at 100.0
        self.assertEqual(calculate_foir(30000, 30000, 50000), 100.0)

    def test_calculate_utilization(self):
        # Outstanding=25000, Limit=100000 -> 25.0%
        util = calculate_utilization(25000, 100000)
        self.assertEqual(util, 25.0)

        # 0 limit -> 0.0
        self.assertEqual(calculate_utilization(1000, 0), 0.0)

    def test_calculate_employment_stability(self):
        # Employment start date 10 years ago -> capped near 100 (plus type adjustment)
        start_10y = date.today() - timedelta(days=3652)

        govt_score = calculate_employment_stability(start_10y, 'govt_salaried')
        self.assertEqual(govt_score, 100.0)  # min(100, 100 + 5) = 100.0

        pvt_score = calculate_employment_stability(start_10y, 'private_salaried')
        self.assertEqual(pvt_score, 100.0)   # min(100, 100 + 0) = 100.0

        self_emp_score = calculate_employment_stability(start_10y, 'self_employed')
        self.assertEqual(self_emp_score, 95.0)  # 100 - 5 = 95.0

        biz_score = calculate_employment_stability(start_10y, 'business')
        self.assertEqual(biz_score, 92.0)   # 100 - 8 = 92.0

        # String date input handling
        score_from_str = calculate_employment_stability(start_10y.isoformat(), 'private_salaried')
        self.assertEqual(score_from_str, 100.0)

    def test_calculate_debt_burden(self):
        # 0 loans, 0 EMIs, 50k income -> 100.0
        self.assertEqual(calculate_debt_burden(0, 0, 50000), 100.0)

        # 2 loans (penalty: 16), 10k EMI (ratio: 20%) -> 100 - 16 - 20 = 64.0
        self.assertEqual(calculate_debt_burden(2, 10000, 50000), 64.0)

    def test_calculate_payment_history_score(self):
        # Base 100, 3 defaults alone -> drops by 60 points (100 - 3*20 = 40.0)
        score_3_defaults = calculate_payment_history_score(100, 0, 3, 0)
        self.assertEqual(score_3_defaults, 40.0)

        # Additional missed payments and settlements
        # 100 - (2*5=10) - (1*20=20) - (1*15=15) = 55.0
        score_mixed = calculate_payment_history_score(100, 2, 1, 1)
        self.assertEqual(score_mixed, 55.0)

    def test_calculate_inquiry_pressure(self):
        # 0 inquiries -> 100
        self.assertEqual(calculate_inquiry_pressure(0), 100.0)
        # 2 inquiries -> 100 - 30 = 70.0
        self.assertEqual(calculate_inquiry_pressure(2), 70.0)

    def test_calculate_loan_to_income_ratio(self):
        # 500k loan, 50k monthly income (600k annual) -> 500000 / 600000 = 0.83
        self.assertEqual(calculate_loan_to_income_ratio(500000, 50000), 0.83)
        # 0 income -> 99.0
        self.assertEqual(calculate_loan_to_income_ratio(500000, 0), 99.0)

    def test_compute_feature_set(self):
        start_date = (date.today() - timedelta(days=3652)).isoformat()
        raw_inputs = {
            'requested_loan_amount': 500000,
            'requested_tenure_months': 60,
            'requested_loan_type': 'home',
            'monthly_income': 50000,
            'existing_emis_monthly': 0,
            'employment_start_date': start_date,
            'employment_type': 'private_salaried',
            'credit_card_outstanding_total': 5000,
            'credit_card_limit_total': 50000,
            'existing_loans_count': 0,
            'on_time_payments_pct': 100,
            'missed_payments_count_12m': 0,
            'defaults_count': 0,
            'settlements_count': 0,
            'credit_history_length_years': 4.5,
            'hard_inquiries_6m': 1,
            'age': 28
        }

        features = compute_feature_set(raw_inputs)
        expected_keys = {
            "foir", "credit_utilization", "employment_stability_score",
            "debt_burden_score", "payment_history_score", "inquiry_pressure_score",
            "loan_to_income_ratio", "new_emi", "credit_history_length_years",
            "age", "employment_type", "requested_loan_type"
        }
        self.assertTrue(expected_keys.issubset(features.keys()))
        self.assertEqual(features['foir'], 20.52)
        self.assertEqual(features['credit_utilization'], 10.0)
        self.assertEqual(features['employment_stability_score'], 100.0)
        self.assertEqual(features['inquiry_pressure_score'], 85.0)
        self.assertEqual(features['age'], 28)


class TestFinancialProfileRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

        # Create test users in DB: one verified, one unverified
        conn = get_connection()
        with conn.cursor() as cur:
            # Verified user
            cur.execute(
                """
                INSERT INTO users (email, password_hash, full_name)
                VALUES ('verified_fe_test@example.com', 'hash123', 'Verified Tester')
                ON CONFLICT (email) DO UPDATE SET full_name = EXCLUDED.full_name
                RETURNING id;
                """
            )
            cls.verified_user_id = str(cur.fetchone()[0])

            # Unverified user
            cur.execute(
                """
                INSERT INTO users (email, password_hash, full_name)
                VALUES ('unverified_fe_test@example.com', 'hash123', 'Unverified Tester')
                ON CONFLICT (email) DO UPDATE SET full_name = EXCLUDED.full_name
                RETURNING id;
                """
            )
            cls.unverified_user_id = str(cur.fetchone()[0])

            # Set up KYC for verified user
            cur.execute(
                """
                INSERT INTO kyc_records (
                    user_id, pan_number, pan_verified, aadhaar_format_valid,
                    bank_account_number, bank_ifsc, bank_verified, full_name,
                    date_of_birth, kyc_status
                ) VALUES (
                    %s, 'ABCDE1234A', TRUE, TRUE, '1234567890', 'SBIN0001234', TRUE, 'Verified Tester', '1995-01-01', 'verified'
                )
                ON CONFLICT (user_id) DO UPDATE SET kyc_status = 'verified';
                """,
                (cls.verified_user_id,)
            )

            # Ensure unverified user has no verified KYC
            cur.execute(
                """
                INSERT INTO kyc_records (
                    user_id, pan_number, pan_verified, aadhaar_format_valid,
                    bank_account_number, bank_ifsc, bank_verified, full_name,
                    date_of_birth, kyc_status
                ) VALUES (
                    %s, 'ABCDE1234B', FALSE, FALSE, '1234567891', 'SBIN0001234', FALSE, 'Unverified Tester', '1995-01-01', 'not_started'
                )
                ON CONFLICT (user_id) DO UPDATE SET kyc_status = 'not_started';
                """,
                (cls.unverified_user_id,)
            )
            conn.commit()
        release_connection(conn)

        with cls.app.app_context():
            cls.verified_token = create_access_token(identity=cls.verified_user_id)
            cls.unverified_token = create_access_token(identity=cls.unverified_user_id)

    @classmethod
    def tearDownClass(cls):
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM users WHERE id IN (%s, %s)",
                (cls.verified_user_id, cls.unverified_user_id)
            )
            conn.commit()
        release_connection(conn)

    def test_unverified_user_gated_403(self):
        # GET should be blocked with 403
        res_get = self.client.get(
            '/api/financial-profile',
            headers={'Authorization': f'Bearer {self.unverified_token}'}
        )
        self.assertEqual(res_get.status_code, 403)
        self.assertFalse(res_get.get_json().get('kyc_verified', True))

        # POST should also be blocked with 403
        res_post = self.client.post(
            '/api/financial-profile',
            headers={'Authorization': f'Bearer {self.unverified_token}'},
            json={
                'monthly_income': 60000,
                'employment_type': 'private_salaried',
                'employment_start_date': '2020-01-01'
            }
        )
        self.assertEqual(res_post.status_code, 403)

    def test_verified_user_crud(self):
        # Save valid profile
        payload = {
            'monthly_income': 75000.0,
            'employment_type': 'private_salaried',
            'employment_start_date': '2019-06-15',
            'existing_emis_monthly': 8000.0,
            'existing_loans_count': 1,
            'credit_card_limit_total': 150000.0,
            'credit_card_outstanding_total': 20000.0,
            'on_time_payments_pct': 99.0,
            'missed_payments_count_12m': 0,
            'defaults_count': 0,
            'settlements_count': 0,
            'credit_history_length_years': 5.0,
            'hard_inquiries_6m': 1
        }

        save_res = self.client.post(
            '/api/financial-profile',
            headers={'Authorization': f'Bearer {self.verified_token}'},
            json=payload
        )
        self.assertEqual(save_res.status_code, 200)
        data = save_res.get_json()
        self.assertIn('profile', data)
        self.assertEqual(data['profile']['monthly_income'], 75000.0)

        # Retrieve profile via GET
        get_res = self.client.get(
            '/api/financial-profile',
            headers={'Authorization': f'Bearer {self.verified_token}'}
        )
        self.assertEqual(get_res.status_code, 200)
        get_data = get_res.get_json()
        retrieved_profile = get_data.get('profile')
        self.assertIsNotNone(retrieved_profile)
        self.assertEqual(retrieved_profile['monthly_income'], 75000.0)
        self.assertEqual(retrieved_profile['employment_type'], 'private_salaried')
        self.assertEqual(retrieved_profile['existing_emis_monthly'], 8000.0)
        self.assertEqual(retrieved_profile['existing_loans_count'], 1)
        self.assertEqual(retrieved_profile['credit_card_limit_total'], 150000.0)
        self.assertEqual(retrieved_profile['credit_card_outstanding_total'], 20000.0)
        self.assertEqual(retrieved_profile['on_time_payments_pct'], 99.0)

    def test_frontend_page_route(self):
        res = self.client.get('/financial-profile')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('Financial profile', html)
        self.assertIn('This information is self-declared. In a production system, this would be verified against credit bureau records (CIBIL/Experian).', html)
        self.assertIn('Save financial profile', html)


if __name__ == '__main__':
    unittest.main()
