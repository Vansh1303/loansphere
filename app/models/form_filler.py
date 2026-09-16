"""
Bank Form Auto-Filler — core logic for generating pre-filled official
bank application PDFs from the user's KYC and financial profile data.

Supports two PDF types:
  - overlay:  flat/non-fillable PDFs — inserts text at fixed (x, y) coords
  - acroform: fillable PDFs with AcroForm widgets — sets widget values
"""

import os
import uuid

import fitz  # PyMuPDF

from app.data.bank_form_mappings import BANK_FORM_MAPPINGS
from app.models.kyc import get_kyc_record
from app.models.feature_engineering import get_financial_profile


# ── PDF fill functions ────────────────────────────────────────────────


def overlay_fill_pdf(template_path, output_path, field_positions):
    """Fill a flat (non-fillable) PDF by overlaying text at fixed coordinates.

    Args:
        template_path: path to the blank official PDF template
        output_path:   path to write the filled PDF
        field_positions: list of dicts, each with keys:
            page (int), x (float), y (float), text (str), font_size (int, default 9)
    """
    doc = fitz.open(template_path)
    for field in field_positions:
        page = doc[field["page"]]
        page.insert_text(
            (field["x"], field["y"]),
            field["text"],
            fontsize=field.get("font_size", 9),
            fontname="helv",
        )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    doc.close()


def fill_form_pdf(template_path, output_path, field_values):
    """Fill a PDF that has native AcroForm widgets.

    Args:
        template_path: path to the fillable PDF template
        output_path:   path to write the filled PDF
        field_values:  dict mapping widget field_name → value string
    """
    doc = fitz.open(template_path)
    for page in doc:
        for widget in page.widgets():
            field_name = widget.field_name
            if field_name in field_values:
                widget.field_value = str(field_values[field_name])
                widget.update()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    doc.close()


# ── Data assembly ─────────────────────────────────────────────────────


def assemble_fill_data(user_id, requested_loan_amount, requested_tenure_months, requested_loan_type):
    """Build a flat dict of all values needed to fill a bank form.

    Combines KYC identity data with the financial profile and the
    specific loan request parameters.  Keys in this dict correspond
    to the ``source`` values used in BANK_FORM_MAPPINGS field maps.
    """
    kyc = get_kyc_record(user_id)
    profile = get_financial_profile(user_id)

    if not kyc:
        raise ValueError("KYC record not found — cannot fill bank form.")
    if not profile:
        raise ValueError("Financial profile not found — cannot fill bank form.")

    return {
        "full_name": kyc.get("full_name", ""),
        "pan_number": kyc.get("pan_number", ""),
        "date_of_birth": str(kyc.get("date_of_birth", "")),
        "aadhaar_masked": kyc.get("aadhaar_number_masked", ""),
        "bank_account_number": kyc.get("bank_account_number", ""),
        "bank_ifsc": kyc.get("bank_ifsc", ""),
        "mobile": "",  # not stored in KYC table — user can write manually
        "monthly_income": str(profile.get("monthly_income", "")),
        "employment_type": str(profile.get("employment_type", "")).replace("_", " ").title(),
        "requested_loan_amount": str(requested_loan_amount),
        "requested_tenure_months": str(requested_tenure_months),
        "requested_loan_type": str(requested_loan_type).title(),
    }


# ── Form generation orchestrator ─────────────────────────────────────


def generate_filled_form(bank_name, loan_type, fill_data, output_dir="static/generated"):
    """Generate a pre-filled PDF for a specific bank + loan type.

    Returns:
        str: relative path to the generated PDF (servable as a static file)

    Raises:
        ValueError: if no template is configured for the bank + loan type
    """
    key = (bank_name, loan_type)
    if key not in BANK_FORM_MAPPINGS:
        raise ValueError(f"No form template configured for {bank_name} — {loan_type}")

    config = BANK_FORM_MAPPINGS[key]
    template_path = config["template_path"]

    output_filename = f"{bank_name}_{loan_type}_{uuid.uuid4().hex[:8]}.pdf"
    output_path = os.path.join(output_dir, output_filename)

    if config["fill_type"] == "overlay":
        field_positions = []
        for field in config["field_map"]:
            value = fill_data.get(field["source"], "")
            field_positions.append({
                "page": field["page"],
                "x": field["x"],
                "y": field["y"],
                "text": str(value),
                "font_size": field.get("font_size", 9),
            })
        overlay_fill_pdf(template_path, output_path, field_positions)
    else:
        # AcroForm fillable PDF
        field_values = {
            f["field_name"]: fill_data.get(f["source"], "")
            for f in config["field_map"]
        }
        fill_form_pdf(template_path, output_path, field_values)

    return output_path
