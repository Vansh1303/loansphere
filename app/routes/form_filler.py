"""Authenticated endpoints for generating pre-filled bank application PDFs."""

import json

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.data.bank_form_mappings import BANK_FORM_MAPPINGS
from app.db.db import get_connection, release_connection
from app.models.form_filler import assemble_fill_data, generate_filled_form

form_filler_bp = Blueprint("form_filler", __name__)


# ── Helpers ───────────────────────────────────────────────────────────


def _fetch_verdict(verdict_id, user_id):
    """Return the verdict row as a dict, or None if not found / not owned."""
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, verdict, eligible_banks,
                       requested_loan_amount, requested_tenure_months,
                       requested_loan_type
                FROM verdicts
                WHERE id = %s AND user_id = %s
                """,
                (verdict_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [desc[0] for desc in cur.description]
            return dict(zip(cols, row))
    except Exception as e:
        print(f"Error fetching verdict: {e}")
        return None
    finally:
        release_connection(conn)


def _save_filled_form(user_id, verdict_id, bank_name, loan_type, file_path):
    """Persist a record of the generated form."""
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO filled_forms (user_id, verdict_id, bank_name, loan_type, file_path)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (user_id, verdict_id, bank_name, loan_type, file_path),
            )
            form_id = cur.fetchone()[0]
        conn.commit()
        return str(form_id)
    except Exception as e:
        conn.rollback()
        print(f"Error saving filled form: {e}")
        return None
    finally:
        release_connection(conn)


# ── Routes ────────────────────────────────────────────────────────────


@form_filler_bp.route("/forms/generate", methods=["POST"])
@jwt_required()
def generate_form():
    """Generate a pre-filled official bank application PDF.

    Request JSON:
        verdict_id (str): UUID of the verdict that established eligibility
        bank_name  (str): name of the bank (must be in verdict's eligible list)
        loan_type  (str): loan type matching the verdict
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    verdict_id = data.get("verdict_id")
    bank_name = data.get("bank_name", "").strip()
    loan_type = data.get("loan_type", "").strip().lower()

    if not verdict_id or not bank_name or not loan_type:
        return jsonify({"msg": "verdict_id, bank_name, and loan_type are required."}), 400

    # 1. Fetch and validate verdict ownership
    verdict = _fetch_verdict(verdict_id, user_id)
    if not verdict:
        return jsonify({"msg": "Verdict not found or does not belong to this user."}), 404

    # 2. Confirm bank is in the verdict's eligible_banks list
    eligible_banks = verdict.get("eligible_banks") or []
    # eligible_banks is stored as JSONB — may already be a list of dicts
    if isinstance(eligible_banks, str):
        eligible_banks = json.loads(eligible_banks)

    eligible_bank_names = [b.get("bank_name", "") for b in eligible_banks if isinstance(b, dict)]
    if bank_name not in eligible_bank_names:
        return jsonify({
            "msg": f"{bank_name} is not in your eligible banks for this verdict."
        }), 400

    # 3. Confirm we have a template for this bank + loan type
    if (bank_name, loan_type) not in BANK_FORM_MAPPINGS:
        return jsonify({
            "msg": f"No form template is configured for {bank_name} — {loan_type}."
        }), 400

    try:
        # 4. Assemble fill data and generate the PDF
        fill_data = assemble_fill_data(
            user_id,
            verdict.get("requested_loan_amount"),
            verdict.get("requested_tenure_months"),
            verdict.get("requested_loan_type"),
        )
        output_path = generate_filled_form(bank_name, loan_type, fill_data)

        # 5. Persist the record
        form_id = _save_filled_form(user_id, verdict_id, bank_name, loan_type, output_path)

        download_url = "/" + output_path.replace("\\", "/")
        return jsonify({
            "form_id": form_id,
            "download_url": download_url,
            "bank_name": bank_name,
            "loan_type": loan_type,
        }), 200

    except ValueError as e:
        return jsonify({"msg": str(e)}), 400
    except Exception as e:
        return jsonify({"msg": f"Form generation error: {e}"}), 500


@form_filler_bp.route("/forms/available-templates", methods=["GET"])
@jwt_required()
def available_templates():
    """Return the list of bank + loan type combos that have a working template."""
    available = [
        {"bank_name": bank, "loan_type": lt}
        for (bank, lt) in BANK_FORM_MAPPINGS.keys()
    ]
    return jsonify({"available": available}), 200
